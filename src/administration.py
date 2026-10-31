"""Administrator inventory and one-transaction bulk cache changes."""


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
            'total_accounts': len(accounts), 'total_sites': sum(len(row['sites']) for row in accounts)}


def request(hestia, action, payload, kind):
    from service import reconcile
    changed = {}
    def mutation(state, config):
        changed.update(mutate(state, payload, kind))
    state, config, _ = reconcile(hestia, mutation if action == 'admin-bulk' else None)
    result = overview(state, config, kind)
    if changed:
        result['changed'] = changed
    return result
