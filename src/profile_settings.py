"""Administrator profile additions; site additions and private boundaries remain."""
import copy
from fragments import validate

PROFILES = ('basic', 'ultracache')


def choices(state):
    result = copy.deepcopy(state.get('profile_settings', {}))
    if not isinstance(result, dict) or set(result) - {'default_profile', 'rules'}:
        raise ValueError('Invalid profile settings')
    default = result.get('default_profile', 'basic')
    rules = result.get('rules', {})
    if default not in PROFILES or not isinstance(rules, dict) or set(rules) - set(PROFILES):
        raise ValueError('Invalid profile selection')
    for profile in PROFILES:
        row = rules.setdefault(profile, {'custom_recv': '', 'custom_backend_response': ''})
        if not isinstance(row, dict) or set(row) != {'custom_recv', 'custom_backend_response'}:
            raise ValueError('Invalid profile rules')
        validate(row['custom_recv'], 'recv')
        validate(row['custom_backend_response'], 'backend_response')
    return {'default_profile': default, 'rules': rules}


def consolidate(state):
    """Fold the three former presets into Basic, retaining their effective VCL.

    This runs once when saved state is reconciled. The renderer and panel accept
    only the two current presets; no alternative runtime policy is retained.
    """
    former = ('general', 'wordpress', 'woocommerce')
    settings = state.get('profile_settings', {})
    rules = settings.get('rules', {})
    if (not any(key in rules for key in former) and
            settings.get('default_profile') not in former and
            not any(site.get('profile') in former for owner in
                    [*state.get('owners', {}).values(), *state.get('retired', [])]
                    for site in [*owner.get('sites', {}).values(), *owner.get('retired_sites', [])])):
        return
    if set(rules) - set((*PROFILES, *former)):
        raise ValueError('Invalid saved profile rules')
    for owner in [*state.get('owners', {}).values(), *state.get('retired', [])]:
        for site in [*owner.get('sites', {}).values(), *owner.get('retired_sites', [])]:
            old = site.get('profile')
            if old not in former:
                continue
            for key, stage in [('custom_recv', 'recv'), ('custom_backend_response', 'backend_response')]:
                central = validate(rules.get(old, {}).get(key, ''), stage)
                local = validate(site.get(key, ''), stage)
                site[key] = '\n'.join(part for part in (central, local) if part)
            site['profile'] = 'basic'
    state['profile_settings'] = choices({'profile_settings': {
        'default_profile': 'basic' if settings.get('default_profile', 'basic') in former
                           else settings.get('default_profile', 'basic'),
        'rules': {key: row for key, row in rules.items() if key in PROFILES}}})


def change(state, payload):
    result = choices(state)
    profile = payload.get('profile')
    if profile not in PROFILES:
        raise ValueError('Choose a profile')
    result['default_profile'] = payload.get('default_profile', result['default_profile'])
    result['rules'][profile] = {key: payload.get(key, '') for key in ('custom_recv', 'custom_backend_response')}
    state['profile_settings'] = choices({'profile_settings': result})
