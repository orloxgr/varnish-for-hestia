"""Administrator profile additions; site additions and private boundaries remain."""
import copy
from fragments import validate

PROFILES = ('general', 'wordpress', 'woocommerce', 'ultracache')


def choices(state):
    result = copy.deepcopy(state.get('profile_settings', {}))
    if not isinstance(result, dict) or set(result) - {'default_profile', 'rules'}:
        raise ValueError('Invalid profile settings')
    default = result.get('default_profile', 'general')
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


def change(state, payload):
    result = choices(state)
    profile = payload.get('profile')
    if profile not in PROFILES:
        raise ValueError('Choose a profile')
    result['default_profile'] = payload.get('default_profile', result['default_profile'])
    result['rules'][profile] = {key: payload.get(key, '') for key in ('custom_recv', 'custom_backend_response')}
    state['profile_settings'] = choices({'profile_settings': result})
