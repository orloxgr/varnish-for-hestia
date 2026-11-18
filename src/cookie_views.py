"""Native Hestia scope adapter; common cookie data never contains credentials."""
import cookie_admin
import cookie_database
from cookie_catalogue import load_catalogue
import aggressive


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
    rows = cookie_admin.table(database, catalogue, central, site)
    extra=[]
    profile=None
    if owner is not None:
        import cookie_policy
        extra = cookie_policy.normalize(state['owners'][owner]['sites'][domain].get('bypass_cookies', []))
        profile=state['owners'][owner]['sites'][domain]['profile']
    def explain(metadata,match,action):
        if owner is not None and aggressive.settings(entry)['aggressive'] and match['kind']=='exact' and match['value'] in aggressive.GENERIC_COOKIES:
            explicit=next((rule for rule in cookie_admin.resolve(cookie_admin.concrete(central),cookie_admin.concrete(site))
                           if cookie_admin._matches(rule['match'],match)),None)
            if explicit is None:
                metadata['effective_action']='shared'
                metadata['core_precedence']='Aggressive caching shares this generic anonymous session cookie. Known CMS authentication, private routes and explicit Private choices still take precedence.'
        cart=next((entry for entry in catalogue['policies'] if entry['consumers']['varnishCart'] and
                   cookie_admin._matches(entry['match'],match)),None)
        if cart:
            metadata['core_precedence']='Reviewed WooCommerce rule '+cart['id']+' takes precedence over the table choice. '
            if profile=='basic':
                metadata['effective_action']='private'
                metadata['core_precedence']+='Basic passes this cart/session request to the application.'
            elif action=='private':
                metadata['effective_action']='private'
                metadata['core_precedence']='The explicit Private choice passes the entire cart/session request. The built-in privacy guard remains in effect.'
            else:
                metadata['effective_action']='application-contract'
                metadata['core_precedence']+='Basic passes this cart/session request. UltraCache shares only an approved ESI parent with private fragments; without that application contract it also passes.'
        for name in extra:
            pattern={'kind':'prefix' if name.endswith('*') else 'exact','value':name.removesuffix('*')}
            if cookie_admin._matches(pattern,match):
                metadata['effective_action']='private'
                metadata['core_precedence']='This website’s additional bypass cookie rule '+name+' takes precedence over the table choice.'
                break
    for row in rows:
        explain(row,row['match'],row['action'])
        explain(row['reset_metadata'],row['reset_match'],row['inherited_action'])
    return {'ok': True, 'service_installed': True, 'cookie_policy_view': True,
            'cookie_scope': 'central' if owner is None else 'site', 'domain': domain,
            'cookie_policies': cookie_admin.concrete(central if owner is None else site),
            'cookie_policy_rows': rows,
            'cookie_policy_saved': False,
            'cookie_legacy_choices': sum(rule['action']=='automatic' for rule in (site if owner is not None else central)['rules']),
            'cookie_integration': integration,
            'cookie_integration_notice': None if owner is None else state['owners'][owner]['sites'][domain].get('cookie_integration_notice'),
            'cookie_profile': None if owner is None else state['owners'][owner]['sites'][domain]['profile']}
