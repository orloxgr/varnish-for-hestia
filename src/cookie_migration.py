"""Convert old owner exclusions to ordinary visible cookie-policy choices."""
import hashlib

import cookie_policy
import cookie_admin

SOURCE = 'Imported from legacy website cookie bypass settings.'


def migrate_site(site):
    """Normal reconciliation owns persistence; no visitor-time fallback exists.

    Saved editor choices win independently per profile. An imported wider
    prefix remains useful outside a newer narrow choice; ordinary specificity
    handles that overlap. Site rules retain the usual precedence over central
    rules. No central choice is copied or frozen into a site snapshot.
    """
    if 'bypass_cookies' not in site:
        return False
    names = cookie_policy.normalize(site['bypass_cookies'])
    if not names:
        del site['bypass_cookies']
        return True
    choices = cookie_admin.normalize(site.get('cookie_policies'))
    explicit = {profile: cookie_admin.project(choices, profile)['rules'] for profile in cookie_admin.PROFILES}
    identities = {rule['id'] for rule in choices['rules']}
    for name in names:
        match = dict(kind='prefix' if name.endswith('*') else 'exact', value=name.removesuffix('*'))
        actions = {profile: None if any(cookie_admin._matches(rule['match'], match)
                     for rule in explicit[profile]) else 'private' for profile in cookie_admin.PROFILES}
        if not any(actions.values()):
            continue
        same = next((rule for rule in choices['rules'] if rule['match'] == match), None)
        if same:
            for profile, action in actions.items():
                if action is not None:
                    same['actions'][profile] = action
            same['description'] = (same['description']+' '+SOURCE).strip()
        else:
            identity = 'legacy-bypass:'+hashlib.sha256((match['kind']+':'+match['value']).encode()).hexdigest()
            while identity in identities:
                identity += ':import'
            identities.add(identity)
            choices['rules'].append(dict(id=identity, match=match, description=SOURCE, actions=actions))
    # Validate completely before replacing either saved field.
    normalized = cookie_admin.normalize(choices)
    site['cookie_policies'] = normalized
    del site['bypass_cookies']
    return True


def migrate_state(state):
    for owner in state['owners'].values():
        for site in owner['sites'].values():
            migrate_site(site)
