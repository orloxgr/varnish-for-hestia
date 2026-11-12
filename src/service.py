"""Manage a single native Varnish instance, scoped VCL and Hestia routing."""
import datetime
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


def apply(state, previous, inventory, config, changes=None):
    if changes is None:
        changes = routing.plan(state, inventory, config)
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
    acceptable_active = (old_name in ('boot', base_name, name) or old_name.startswith(base_name + '_') or
                         old_name.startswith('hvh_reload_'))
    needs_activation = active_bytes != program.encode() or not acceptable_active
    candidate = CONFIG / 'generations' / (name + '.vcl')
    if needs_activation and name not in {row['name'] for row in rows}:
        write(candidate, program, 0o640, grp.getgrnam('varnish').gr_gid)
        try:
            admin(config, 'vcl.load', name, str(candidate))
        except Exception:
            candidate.unlink(missing_ok=True)
            raise ApplyRolledBack('VCL compilation failed; current service retained') from None
    routing_undo = None
    try:
        if needs_activation:
            admin(config, 'vcl.use', name)
        route_result, routing_undo = routing.apply(changes, routing.apache_config(inventory, config['origin_port']))
        old_sites = {site['id']: site for owner in (previous or {}).get('owners', {}).values() for site in owner['sites'].values()}
        old_rules = profile_settings.choices(previous or {})['rules']
        new_rules = profile_settings.choices(state)['rules']
        current_ids = set()
        invalidated = 0
        for owner in state['owners'].values():
            for site in owner['sites'].values():
                current_ids.add(site['id'])
                old = old_sites.get(site['id'])
                if old and (any(old[key] != site[key] for key in ('enabled', 'profile', 'custom_recv', 'custom_backend_response')) or
                            old.get('bypass_cookies', []) != site.get('bypass_cookies', []) or
                            old['settings'].get('routing_active') != site['settings'].get('routing_active') or
                            old_rules[old['profile']] != new_rules[site['profile']]):
                    purge(config, site); invalidated += 1
        for sid in set(old_sites) - current_ids:
            purge(config, old_sites[sid]); invalidated += 1
        if active_bytes != program.encode():
            write(ACTIVE, program, 0o640, grp.getgrnam('varnish').gr_gid)
    except Exception:
        try:
            if routing_undo is not None:
                routing.rollback(*routing_undo)
        finally:
            if needs_activation:
                admin(config, 'vcl.use', old_name)
                admin(config, 'vcl.discard', name, required=False)
            write(ACTIVE, active_bytes, 0o640, grp.getgrnam('varnish').gr_gid)
        raise ApplyRolledBack('Apply failed; previous Varnish and web settings were restored') from None
    prune(config, [name, old_name])
    return dict(route_result, vcl_activated=needs_activation, invalidated_sites=invalidated, generation=digest)


def transaction_paths():
    return [ACTIVE, STORE/'desired.json', STORE/'applied.json']


def recover_pending(config_override=None):
    from cache_size import recover
    recover()
    record = transaction.read(STORE, transaction_paths())
    if record is None:
        return False
    transaction.restore_files(record)
    extra = record['extra']
    before = base64.b64decode(extra['apache']) if extra['apache'] is not None else None
    routing.rollback(extra['routes'], before)
    # After a reboot the old management generation name need not exist. The
    # restored active.vcl is the durable source of truth in either case.
    routing.run('systemctl', 'restart', 'varnish')
    wait_healthy(settings() if config_override is None else config_override)
    transaction.finish(STORE)
    return True


def reconcile(hestia, mutation=None, config_override=None):
    # Only root-side installation code supplies the override while the public
    # bridge remains unavailable until installation commits.
    recover_pending(config_override)
    config = settings() if config_override is None else config_override
    inventory = collect(hestia)
    with locked_store(STORE) as desired_path:
        old = json.loads(desired_path.read_text()) if desired_path.exists() else None
        state = desired_state(old, inventory, 'varnish')
        hosting_timeouts.refresh(state)
        browser_cache.defaults(state)
        if mutation:
            mutation(state, config)
        applied_path = STORE / 'applied.json'
        previous = json.loads(applied_path.read_text()) if applied_path.exists() else None
        changes = routing.plan(state, inventory, config)
        render(state, config)
        apache = routing.APACHE.read_bytes() if routing.APACHE.exists() else None
        transaction.begin(STORE, transaction_paths(), {'routes': changes,
                          'apache': base64.b64encode(apache).decode() if apache is not None else None})
        try:
            result = apply(state, previous, inventory, config, changes=changes)
            if old != state:
                write_json(desired_path, state)
            if previous != state:
                write_json(applied_path, state)
        except ApplyRolledBack:
            transaction.finish(STORE)
            raise
        except Exception:
            recover_pending(config_override)
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
        elif action == 'token':
            value = payload.get('password')
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{12,}', value):
                raise ValueError('Purge tokens need at least 12 letters, digits, underscore or hyphen')
            owner['sites'][domain]['token'] = value
    if action not in ('status', 'credentials', 'toggle-account', 'toggle-site', 'configure-site', 'configure-cookies', 'configure-browser-cache', 'token', 'flush'):
        raise ValueError('Unsupported Varnish action')
    if action in ('credentials', 'toggle-site', 'configure-site', 'configure-cookies', 'configure-browser-cache', 'token', 'flush') and not isinstance(domain, str):
        raise ValueError('Select a site')
    state, config, result = reconcile(hestia, mutate)
    owner = state['owners'][owner_name]
    if domain is not None and domain not in owner['sites']:
        raise ValueError('Domain is not owned by this account')
    response = {'ok': True, 'owner': owner_name, 'enabled': owner['enabled'],
                'allowed': owner['package'] not in config.get('denied_packages', []) and
                           (config.get('allowed_packages') is None or owner['package'] in config['allowed_packages']),
                'sites': [{'domain': name, 'aliases': site['aliases'], 'suspended': site['suspended'],
                           'enabled': site['enabled'], 'profile': site['profile'],
                           'custom_recv': site['custom_recv'], 'custom_backend_response': site['custom_backend_response'],
                           'bypass_cookies': site.get('bypass_cookies', []),
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
