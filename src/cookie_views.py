"""Native Hestia scope adapter; common cookie data never contains credentials."""
import cookie_admin
import cookie_database
from cookie_catalogue import load_catalogue


def view(state, owner=None, domain=None):
    central = cookie_admin.normalize(state.get('cookie_policies'))
    site = None
    if owner is not None:
        if domain not in state['owners'][owner]['sites']:
            raise ValueError('Domain is not owned by this account')
        site = cookie_admin.normalize(state['owners'][owner]['sites'][domain].get('cookie_policies'))
    database = cookie_database.database()
    integration = None
    if owner is not None:
        import cookie_control
        entry = state['owners'][owner]['sites'][domain]
        integration = cookie_control.integration(entry.get('cookie_integration'), domain, entry.get('aliases', []))
    catalogue = load_catalogue()
    rows = cookie_admin.table(database, catalogue, central, site,entry['profile'] if owner is not None else 'basic')
    for row in rows:
        for profile,metadata in row['profile_actions'].items():
            metadata['mode_default_action']=None
            metadata['reset_metadata']['mode_default_action']=None
        active=entry['profile'] if owner is not None else 'basic'
        row.update(row['profile_actions'][active])
    return {'ok': True, 'service_installed': True, 'cookie_policy_view': True,
            'cookie_scope': 'central' if owner is None else 'site', 'domain': domain,
            'cookie_policies': cookie_admin.concrete(central if owner is None else site),
            'cookie_policy_rows': rows,
            'cookie_policy_saved': False,
            'cookie_legacy_choices': sum(any(a=='automatic' for a in rule['actions'].values()) for rule in (site if owner is not None else central)['rules']),
            'cookie_integration': integration,
            'cookie_integration_notice': None if owner is None else state['owners'][owner]['sites'][domain].get('cookie_integration_notice'),
            'cookie_profile': None if owner is None else state['owners'][owner]['sites'][domain]['profile']}
