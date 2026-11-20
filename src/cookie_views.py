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
    rows = cookie_admin.table(database, catalogue, central, site,entry['profile'] if owner is not None else 'basic')
    extra=[]
    if owner is not None:
        import cookie_policy
        extra = cookie_policy.normalize(state['owners'][owner]['sites'][domain].get('bypass_cookies', []))
    def explain(metadata,match,action,reset_id=None,profile='basic'):
        metadata['mode_default_action']=None
        if owner is not None and aggressive.settings(entry)['aggressive'] and match['kind']=='exact' and match['value'] in aggressive.GENERIC_COOKIES:
            site_choices=cookie_admin.concrete(site)
            if reset_id is not None:site_choices['rules']=[rule for rule in site_choices['rules'] if rule['id']!=reset_id]
            explicit=next((rule for rule in cookie_admin.resolve(cookie_admin.concrete(central),site_choices,profile)
                           if cookie_admin._matches(rule['match'],match)),None)
            inherited_explicit=next((rule for rule in cookie_admin.resolve(cookie_admin.concrete(central),None,profile)
                                     if cookie_admin._matches(rule['match'],match)),None)
            metadata['effective_action']=explicit['action'] if explicit else 'shared'
            metadata['mode_default_action']=None if inherited_explicit else 'shared'
            metadata['core_precedence']='Aggressive caching can share this generic anonymous session cookie. Known CMS authentication, private routes and explicit Private choices still take precedence.'
        if owner is not None and match['kind']=='exact' and match['value'] in aggressive.session_names(entry):
            metadata['core_precedence']='Aggressive caching shares this opaque Joomla cookie without checking session state. Known login markers and private routes remain active. An explicit Private choice passes matching requests.'
        for name in extra:
            pattern={'kind':'prefix' if name.endswith('*') else 'exact','value':name.removesuffix('*')}
            if cookie_admin._matches(pattern,match):
                metadata['effective_action']='private'
                metadata['core_precedence']='This website’s additional bypass cookie rule '+name+' takes precedence over the table choice.'
                break
    for row in rows:
        for profile,metadata in row['profile_actions'].items():
            explain(metadata,row['match'],metadata['action'],profile=profile)
            explain(metadata['reset_metadata'],row['reset_match'],metadata['inherited_action'],row['id'],profile)
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
