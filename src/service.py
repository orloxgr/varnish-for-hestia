"""Manage a single native Varnish instance, scoped VCL and Hestia routing."""
import datetime
import copy
import grp
import hashlib
import http.client
import json
from pathlib import Path
import re
import secrets
import subprocess
import time

from files import write, write_json
import transaction
import base64
from inventory import collect
from registry import desired_state, locked_store
import routing
import browser_cache
import hosting_timeouts
import profile_settings
import progress
import cookie_policy
import cookie_admin
import cookie_bridge
import cookie_control
import cookie_execution
import aggressive
import cache_behavior
import cms_inventory
import legacy_cms
from vcl import render, PROFILES

CONFIG = Path('/etc/varnish-for-hestia')
STORE = Path('/var/lib/varnish-for-hestia')
ACTIVE = CONFIG / 'active.vcl'


def verify_native_unit():
    result = subprocess.run(['systemctl', 'show', 'varnish', '-p', 'ExecStart', '-p', 'ExecReload', '-p', 'Type'],
                            capture_output=True, text=True, timeout=None)
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if (result.returncode or values.get('Type') != 'exec' or
            str(ACTIVE) not in values.get('ExecStart', '') or
            str(CONFIG / 'admin.secret') not in values.get('ExecStart', '') or
            str(ACTIVE) not in values.get('ExecReload', '')):
        raise RuntimeError('The effective native unit no longer uses the addon configuration')


class ApplyRolledBack(RuntimeError):
    pass


def settings():
    result = json.loads((CONFIG / 'settings.json').read_text())
    if not result.get('installed'):
        raise ValueError('Install the Varnish service addon first')
    if (STORE/'restore.json').exists():
        raise ValueError('Finish the pending restore with the README restore command')
    if (STORE / 'install.json').exists():
        raise ValueError('Finish the pending installation with the README install command')
    ports = [result.get('listen_port'), result.get('admin_port')]
    if any(type(port) is not int or not 1 <= port <= 65535 for port in ports) or ports[0] == ports[1]:
        raise ValueError('Use distinct valid native TCP ports')
    from cache_size import recover
    if recover():
        result = json.loads((CONFIG / 'settings.json').read_text())
    verify_native_unit()
    return result


def admin(config, *args, required=True):
    from cli import command
    result = command(config['admin_port'], CONFIG / 'admin.secret', args)
    if result.returncode and required:
        # Compiler messages can quote source containing other tenants' tokens.
        # They must never be echoed to a panel owner or a shared log.
        raise RuntimeError('Varnish operation failed; existing configuration retained')
    return result


def vcls(config):
    rows = json.loads(admin(config, 'vcl.list', '-j').stdout)
    return [row for row in rows if isinstance(row, dict) and 'name' in row]


def wait_healthy(config, timeout=None):
    from cli import AuthenticationError
    while True:
        body = None
        try:
            body = admin(config, 'status').stdout
        except AuthenticationError:
            raise RuntimeError('The native Varnish administrator credential is not active') from None
        except (OSError, RuntimeError, subprocess.SubprocessError):
            pass
        if body and b'running' in body:
            return
        if body and b'stopped' in body:
            raise RuntimeError('The native Varnish child is stopped')
        state = subprocess.run(['systemctl', 'is-active', 'varnish'], capture_output=True, text=True)
        if state.stdout.strip() in ('failed', 'inactive', 'deactivating', 'unknown'):
            raise RuntimeError('Varnish did not become healthy') from None
        time.sleep(.2)


def purge(config, site):
    if not re.fullmatch(r'[0-9a-f]{32}', site['id']):
        raise ValueError('Invalid site scope')
    admin(config, 'ban', 'obj.http.X-HVH-Site', '==', site['id'])


def prune(config, keep_names):
    # Only our generations are discarded; native reloads/other admin programs
    # are left alone. Busy generations can remain until the next reconciliation.
    rows = vcls(config)
    keep = set(keep_names)
    for row in rows:
        name = row['name']
        if row['status'] == 'active' or name in keep or not name.startswith('hvh_gen_'):
            continue
        admin(config, 'vcl.discard', name, required=False)
    used = {row['name'] for row in vcls(config)} | keep
    for file in (CONFIG / 'generations').glob('hvh_gen_*.vcl'):
        if file.stem not in used and not file.is_symlink():
            file.unlink()


def apply(state, previous, inventory, config, changes=None, cookie_ops=None, journal=None):
    if changes is None:
        progress.stage('Preparing managed proxy routes')
        changes = routing.plan(state, inventory, config)
    progress.stage('Rendering the Varnish policy')
    program = render(state, config)
    digest = hashlib.sha256(program.encode()).hexdigest()
    base_name = 'hvh_gen_' + digest[:32]
    rows = vcls(config)
    reusable = [row['name'] for row in rows if row['status'] in ('active', 'available') and
                (row['name'] == base_name or row['name'].startswith(base_name + '_'))]
    name = reusable[-1] if reusable else base_name + '_' + secrets.token_hex(4)
    while not reusable and name in {row['name'] for row in rows}:
        name = base_name + '_' + secrets.token_hex(4)
    old_name = next(row['name'] for row in rows if row['status'] == 'active')
    active_bytes = ACTIVE.read_bytes()
    # Our immutable generation names identify the complete rendered program.
    # A boot/external reload name has no such identity, and restored disk bytes
    # cannot prove what is running. Adopt the compiled managed generation once;
    # subsequent reconciliations reuse its digest name. Do not dump runtime VCL:
    # native vcl.show can truncate a valid multi-site program (CLIS_TRUNCATED).
    needs_activation = not (old_name == base_name or old_name.startswith(base_name + '_'))
    if not needs_activation:
        name = old_name
    candidate = CONFIG / 'generations' / (name + '.vcl')
    if needs_activation and name not in {row['name'] for row in rows}:
        write(candidate, program, 0o640, grp.getgrnam('varnish').gr_gid)
        try:
            progress.stage('Compiling candidate VCL with native Varnish')
            admin(config, 'vcl.load', name, str(candidate))
        except Exception:
            candidate.unlink(missing_ok=True)
            raise ApplyRolledBack('VCL compilation failed; current service retained') from None
    routing_undo = None
    try:
        if cookie_ops:
            progress.stage('Applying connected WordPress cookie policies')
            cookie_bridge.commit(cookie_ops, lambda: journal())
        if journal:
            journal(local_started=True)
        if needs_activation:
            progress.stage('Activating the compiled VCL')
            admin(config, 'vcl.use', name)
        route_result, routing_undo = routing.apply(changes, routing.apache_config(inventory, config['origin_port']))
        old_sites = {site['id']: site for owner in (previous or {}).get('owners', {}).values() for site in owner['sites'].values()}
        old_profiles = copy.deepcopy(previous or {})
        profile_settings.consolidate(old_profiles)
        old_rules = profile_settings.choices(old_profiles)['rules']
        old_site_rules = {site['id']: old_rules[site['profile']]
                          for owner in old_profiles.get('owners', {}).values()
                          for site in owner['sites'].values()}
        new_rules = profile_settings.choices(state)['rules']
        progress.stage('Checking which site caches need invalidation')
        current_ids = set()
        invalidated = 0
        execution = cookie_execution.projections()
        for owner in state['owners'].values():
            for site in owner['sites'].values():
                current_ids.add(site['id'])
                old = old_sites.get(site['id'])
                if old and (any(old[key] != site[key] for key in ('enabled', 'profile', 'custom_recv', 'custom_backend_response')) or
                            old.get('bypass_cookies', []) != site.get('bypass_cookies', []) or
                            cache_behavior.execution(old) != cache_behavior.execution(site) or
                            any(operation['site_id'] == site['id'] and operation['base_digest'] != operation['target_digest']
                                for operation in (cookie_ops or [])) or
                            state.get('cookie_defaults_digest') != (previous or {}).get('cookie_defaults_digest') or
                            execution((previous or {}).get('cookie_policies'), old.get('cookie_policies')) !=
                            execution(state.get('cookie_policies'), site.get('cookie_policies')) or
                            old['settings'].get('routing_active') != site['settings'].get('routing_active') or
                            old_site_rules[site['id']] != new_rules[site['profile']]):
                    purge(config, site); invalidated += 1
        for sid in set(old_sites) - current_ids:
            purge(config, old_sites[sid]); invalidated += 1
        if active_bytes != program.encode():
            write(ACTIVE, program, 0o640, grp.getgrnam('varnish').gr_gid)
    except Exception as failure:
        try:
            if routing_undo is not None:
                routing.rollback(*routing_undo)
        finally:
            if needs_activation:
                admin(config, 'vcl.use', old_name)
                admin(config, 'vcl.discard', name, required=False)
            write(ACTIVE, active_bytes, 0o640, grp.getgrnam('varnish').gr_gid)
        # A failed route rollback must retain the native recovery phase. Only
        # clear it after routes, runtime VCL and durable source were restored.
        if journal:
            journal(local_started=False)
        error = ApplyRolledBack('Apply failed; previous Varnish and web settings were restored')
        if isinstance(failure, cookie_control.ControlError):
            error.cookie_control_error = failure
        raise error from None
    progress.stage('Removing unused addon VCL generations')
    prune(config, [name, old_name])
    return dict(route_result, vcl_activated=needs_activation, invalidated_sites=invalidated, generation=digest)


def transaction_paths():
    return [ACTIVE, STORE/'desired.json', STORE/'applied.json']


def record_cookie_rollback(operations):
    preserved=cookie_bridge.preserved_newer(operations)
    if preserved:
        write_json(STORE/'last-cookie-rollback.json',{'preserved':preserved,
            'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    return preserved


def recover_pending(config_override=None, cookie_report=None):
    from cache_size import recover
    recover()
    record = transaction.read(STORE, transaction_paths())
    if record is None:
        return False
    extra = record['extra']
    def persist():
        write_json(STORE/'apply.json', record)
    cookie_bridge.rollback(extra.get('cookie_operations', []), persist)
    preserved=record_cookie_rollback(extra.get('cookie_operations', []))
    if cookie_report is not None:cookie_report.extend(preserved)
    transaction.restore_files(record)
    legacy_cms.restore(extra.get('cms_resolver'))
    before = base64.b64decode(extra['apache']) if extra['apache'] is not None else None
    if extra.get('local_started', True):
        routing.rollback(extra['routes'], before)
        # A remote-only failure never requires restarting native services.
        # After a reboot the old management generation name need not exist.
        routing.run('systemctl', 'restart', 'varnish')
        wait_healthy(settings() if config_override is None else config_override)
    transaction.finish(STORE)
    return True


def reconcile(hestia, mutation=None, config_override=None, cookie_scope=None, cms_scope=None):
    # Only root-side installation code supplies the override while the public
    # bridge remains unavailable until installation commits.
    recover_pending(config_override)
    config = settings() if config_override is None else config_override
    inventory = collect(hestia)
    with locked_store(STORE) as desired_path:
        old = json.loads(desired_path.read_text()) if desired_path.exists() else None
        state = desired_state(old, inventory, 'varnish')
        cookie_bridge.reconcile_inventory(state)
        progress.stage('Reading native Nginx timeout settings')
        hosting_timeouts.refresh(state)
        browser_cache.defaults(state)
        if mutation:
            mutation(state, config)
        changed_cms=cms_inventory.changed_roots(state,inventory)
        effective_cms_scope='all' if cms_scope=='all' else changed_cms | set(cms_scope or [])
        if effective_cms_scope:
            progress.stage('Detecting CMS installations and configured private routes')
            cms_inventory.refresh(state,inventory,hestia,effective_cms_scope)
        applied_path = STORE / 'applied.json'
        previous = json.loads(applied_path.read_text()) if applied_path.exists() else None
        progress.stage('Preparing managed proxy routes')
        changes = routing.plan(state, inventory, config)
        render(state, config)
        force_sites = {state['owners'][owner]['sites'][domain]['id'] for owner, domain in (cookie_scope or [])} if cookie_scope != 'all' else set()
        cookie_ops = cookie_bridge.plan(state, previous, force=cookie_scope == 'all', force_sites=force_sites)
        cookie_bridge.inspect(cookie_ops)
        apache = routing.APACHE.read_bytes() if routing.APACHE.exists() else None
        extra = {'routes': changes, 'cookie_operations': cookie_ops, 'local_started': False,
                 'cms_resolver':legacy_cms.snapshot(),
                 'apache': base64.b64encode(apache).decode() if apache is not None else None}
        transaction.begin(STORE, transaction_paths(), extra)
        def journal(**updates):
            extra.update(updates)
            record = transaction.read(STORE, transaction_paths())
            record['extra'] = extra
            write_json(STORE/'apply.json', record)
        try:
            cookie_bridge.prepare(cookie_ops, journal)
            result = apply(state, previous, inventory, config, changes=changes, cookie_ops=cookie_ops, journal=journal)
            legacy_cms.retire()
            progress.stage('Committing desired and applied configuration')
            if old != state:
                write_json(desired_path, state)
            if previous != state:
                write_json(applied_path, state)
        except ApplyRolledBack as failure:
            cookie_bridge.rollback(cookie_ops, journal)
            legacy_cms.restore(extra.get('cms_resolver'))
            transaction.finish(STORE)
            if record_cookie_rollback(cookie_ops):
                original=getattr(failure,'cookie_control_error',failure)
                raise cookie_control.ControlError(str(original)+' A newer WordPress policy was preserved while aborting this change.') from None
            if hasattr(failure, 'cookie_control_error'):
                raise failure.cookie_control_error from None
            raise
        except Exception as failure:
            preserved=[]
            recover_pending(config_override,cookie_report=preserved)
            if preserved:
                cause=str(failure) if isinstance(failure,cookie_control.ControlError) else 'The change failed.'
                raise cookie_control.ControlError(cause+' A newer WordPress policy was preserved while aborting this change.') from None
            raise
        transaction.finish(STORE)
        write_json(STORE / 'last-run.json', {'ok': True, 'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), **result})
        return state, config, result


def request(hestia, owner_name, action, payload):
    domain = payload.get('domain')
    def mutate(state, config):
        owner = state['owners'][owner_name]
        if domain is not None and domain not in owner['sites']:
            raise ValueError('Domain is not owned by this account')
        if action in ('toggle-account', 'toggle-site'):
            if not isinstance(payload.get('enabled'), bool):
                raise ValueError('Expected an enable/disable choice')
            if action == 'toggle-account':
                owner['enabled'] = payload['enabled']
            else:
                owner['sites'][domain]['enabled'] = payload['enabled']
        elif action == 'configure-site':
            site = owner['sites'][domain]
            if payload.get('profile') not in PROFILES:
                raise ValueError('Invalid Varnish profile')
            site.update(profile=payload['profile'], custom_recv=payload.get('custom_recv', ''),
                        custom_backend_response=payload.get('custom_backend_response', ''))
        elif action == 'configure-cookies':
            from cookie_policy import normalize
            if not isinstance(payload.get('bypass_cookies'), str):
                raise ValueError('Cookie rules must be text, one per line')
            owner['sites'][domain]['bypass_cookies'] = normalize(payload['bypass_cookies'])
        elif action == 'configure-browser-cache':
            browser_cache.change(state, payload, owner['sites'][domain])
        elif action == 'configure-cache-policy':
            cache_behavior.change(owner['sites'][domain],payload)
        elif action == 'configure-cookie-policies':
            owner['sites'][domain]['cookie_policies'] = cookie_admin.normalize(payload.get('cookie_policies'))
            if 'cookie_integration' in payload:
                import cookie_control
                site = owner['sites'][domain]
                try:
                    site['cookie_integration'] = cookie_control.integration(payload['cookie_integration'], domain, site.get('aliases', []))
                    site.pop('cookie_integration_notice',None)
                except ValueError as error:
                    raise cookie_admin.CookieChoiceError(str(error)) from None
        elif action == 'token':
            value = payload.get('password')
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{12,}', value):
                raise ValueError('Purge tokens need at least 12 letters, digits, underscore or hyphen')
            owner['sites'][domain]['token'] = value
    if action not in ('status', 'credentials', 'toggle-account', 'toggle-site', 'configure-site', 'configure-cookies', 'configure-browser-cache', 'configure-cache-policy', 'refresh-cms', 'token', 'flush', 'cookie-policies', 'configure-cookie-policies'):
        raise ValueError('Unsupported Varnish action')
    if action in ('credentials', 'toggle-site', 'configure-site', 'configure-cookies', 'configure-browser-cache', 'configure-cache-policy', 'refresh-cms', 'token', 'flush', 'cookie-policies', 'configure-cookie-policies') and not isinstance(domain, str):
        raise ValueError('Select a site')
    if action == 'configure-cookie-policies':
        state, config, result = reconcile(hestia, mutate, cookie_scope={(owner_name,domain)})
    elif action in ('configure-cache-policy','refresh-cms'):
        state, config, result = reconcile(hestia, mutate, cms_scope={(owner_name,domain)})
    else:
        state, config, result = reconcile(hestia, mutate)
    owner = state['owners'][owner_name]
    if domain is not None and domain not in owner['sites']:
        raise ValueError('Domain is not owned by this account')
    if action in ('cookie-policies', 'configure-cookie-policies'):
        from cookie_views import view
        response = view(state, owner_name, domain)
        response['cookie_policy_saved'] = action == 'configure-cookie-policies'
        return response
    response = {'ok': True, 'owner': owner_name, 'enabled': owner['enabled'],
                'allowed': owner['package'] not in config.get('denied_packages', []) and
                           (config.get('allowed_packages') is None or owner['package'] in config['allowed_packages']),
                'sites': [{'domain': name, 'aliases': site['aliases'], 'suspended': site['suspended'],
                           'enabled': site['enabled'], 'profile': site['profile'],
                           'custom_recv': site['custom_recv'], 'custom_backend_response': site['custom_backend_response'],
                           'bypass_cookies': site.get('bypass_cookies', []),
                           **aggressive.settings(site),
                           'custom_private_paths':site.get('custom_private_paths',[]),
                           'cms_installations':site.get('cms_installations',[]),
                           'cms_discovery':site.get('cms_discovery'),
                           'browser_cache': browser_cache.selected(site, state),
                           'browser_cache_override': site.get('browser_cache'),
                           'routing_active': site['settings'].get('routing_active', False)}
                          for name, site in sorted(owner['sites'].items())]}
    if action == 'credentials':
        response['connection'] = {'host': '127.0.0.1', 'port': config['listen_port'],
                                  'domain': domain, 'token': owner['sites'][domain]['token'],
                                  'header': 'X-Hestia-Varnish-Token', 'ultracache_header': 'X-UltraCache-Token'}
    if action == 'flush':
        purge(config, owner['sites'][domain]); response['purged'] = True
    return response
