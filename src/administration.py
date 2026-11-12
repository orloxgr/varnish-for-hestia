"""Administrator inventory and one-transaction bulk cache changes."""
import json
import re
import server_settings
import browser_cache
import profile_settings


def mutate(state, payload, kind):
    """Resolve and validate the entire selection before changing any choices."""
    owners = state['owners']
    operation = payload.get('operation')
    permitted = ['enable-sites', 'disable-sites', 'enable-accounts', 'disable-accounts']
    if kind == 'varnish':
        permitted.append('set-profile')
    if operation not in permitted or payload.get('scope') not in ('selected', 'all'):
        raise ValueError('Invalid bulk operation or scope')
    if operation == 'set-profile':
        from vcl import PROFILES
        if payload.get('profile') not in PROFILES:
            raise ValueError('Invalid Varnish profile')
    accounts, targets = payload.get('accounts', []), payload.get('targets', [])
    if not isinstance(accounts, list) or not isinstance(targets, list):
        raise ValueError('Expected account and site selections')
    selected_accounts, selected_sites = set(), set()
    for name in accounts:
        if not isinstance(name, str) or name not in owners:
            raise ValueError('Unknown account')
        selected_accounts.add(name)
    for row in targets:
        if not isinstance(row, dict):
            raise ValueError('Invalid site selection')
        name, domain = row.get('owner'), row.get('domain')
        if (not isinstance(name, str) or name not in owners or
                not isinstance(domain, str) or domain not in owners[name]['sites']):
            raise ValueError('Site does not belong to the selected account')
        selected_sites.add((name, domain))
    account_operation = operation.endswith('-accounts')
    if account_operation and selected_sites and payload['scope'] != 'all':
        raise ValueError('Select account checkboxes for an account operation')
    if payload['scope'] == 'all':
        selected_accounts = set(owners)
    if account_operation:
        if not selected_accounts:
            raise ValueError('Select at least one account')
        for name in selected_accounts:
            owners[name]['enabled'] = operation == 'enable-accounts'
        return {'accounts': len(selected_accounts), 'sites': 0}
    selected_sites.update((name, domain) for name in selected_accounts
                          for domain in owners[name]['sites'])
    if not selected_sites:
        raise ValueError('Select at least one website')
    for name, domain in selected_sites:
        site = owners[name]['sites'][domain]
        if operation == 'set-profile':
            site['profile'] = payload['profile']
        else:
            site['enabled'] = operation == 'enable-sites'
    return {'accounts': len({name for name, _ in selected_sites}), 'sites': len(selected_sites)}


def overview(state, config, kind):
    accounts = []
    for name, owner in sorted(state['owners'].items()):
        allowed = (owner['package'] not in config.get('denied_packages', []) and
                   (config.get('allowed_packages') is None or owner['package'] in config['allowed_packages']))
        sites = []
        for domain, site in sorted(owner['sites'].items()):
            active = owner['enabled'] and allowed and not owner['suspended'] and site['enabled'] and not site['suspended']
            row = {'domain': domain, 'aliases': site['aliases'], 'enabled': site['enabled'],
                   'suspended': site['suspended'], 'active': active}
            if kind == 'varnish':
                row.update(profile=site['profile'], routing_active=site['settings'].get('routing_active', False))
                row['active'] = active and row['routing_active']
            sites.append(row)
        accounts.append({'owner': name, 'package': owner['package'], 'enabled': owner['enabled'],
                         'suspended': owner['suspended'], 'allowed': allowed, 'sites': sites})
    return {'ok': True, 'admin': True, 'service_installed': True, 'accounts': accounts,
            'server_settings': server_settings.choices(state),
            'hosting_timeouts': state.get('hosting_timeouts'),
            'browser_cache': browser_cache.defaults(state), 'profile_settings': profile_settings.choices(state), 'memory_budget_mb': config.get('memory_mb'),
            'total_accounts': len(accounts), 'total_sites': sum(len(row['sites']) for row in accounts)}


def request(hestia, action, payload, kind):
    import service
    def show_default(result, config):
        if result['server_settings']['first_byte_timeout_seconds'] is None and not result.get('hosting_timeouts'):
            native = service.admin(config, 'param.show', 'first_byte_timeout', required=False)
            match = re.search(rb'Value is:\s*([0-9]+(?:\.[0-9]+)?)', native.stdout)
            result['service_first_byte_timeout_seconds'] = float(match[1]) if match else None
        return result
    if action not in ('admin-inventory', 'admin-bulk', 'admin-server-settings', 'admin-memory', 'admin-memory-size', 'admin-browser-cache', 'admin-profile-settings'):
        raise ValueError('Invalid administrator action')
    if action in ('admin-memory', 'admin-memory-size'):
        restarted = False
        if action == 'admin-memory-size':
            from cache_size import resize
            config, restarted = resize(payload.get('memory_mb'))
        else:
            config = service.settings()
        state = json.loads((service.STORE/'applied.json').read_text())
        result = overview(state, config, kind)
        if action == 'admin-memory':
            result['memory'] = server_settings.memory(config)
        else:
            result.update(memory_size_saved=True, service_restarted=restarted)
        return show_default(result, config)
    changed = {}
    def mutation(state, config):
        if action == 'admin-server-settings':
            server_settings.change(state, payload)
        elif action == 'admin-browser-cache':
            browser_cache.change(state, payload)
        elif action == 'admin-profile-settings':
            profile_settings.change(state, payload)
        else:
            changed.update(mutate(state, payload, kind))
    state, config, _ = service.reconcile(hestia, mutation if action in ('admin-bulk', 'admin-server-settings', 'admin-browser-cache', 'admin-profile-settings') else None)
    result = overview(state, config, kind)
    show_default(result, config)
    if action == 'admin-server-settings':
        result['server_settings_saved'] = True
    if action in ('admin-browser-cache', 'admin-profile-settings'):
        result['policy_settings_saved'] = True
    if changed:
        result['changed'] = changed
    return result
