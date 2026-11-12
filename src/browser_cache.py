"""Headers for files served directly by Nginx, independent of Varnish TTL."""
import copy
import json
import re

DEFAULTS = dict(enabled=True, static_seconds=2592000, versioned_seconds=31536000, versioned_paths=[])
PROFILE_PATHS = {'ultracache': ['/wp-content/uploads/ultracache/css-bundles/bundle-*-{hash}.css']}


def pattern(value):
    if (not isinstance(value, str) or not value.startswith('/') or '{hash}' not in value or
            not re.fullmatch(r'[A-Za-z0-9/_.{}*\-]+', value) or
            any(part in ('.', '..') for part in value.split('/')) or '**' in value or
            '{' in value.replace('{hash}', '') or '}' in value.replace('{hash}', '')):
        raise ValueError('Use an absolute literal URL path with {hash} and optional * within a path segment')
    return re.escape(value).replace(r'\*', '[^/]*').replace(r'\{hash\}', '[0-9a-fA-F]+')


def validate(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULTS) or type(value['enabled']) is not bool:
        raise ValueError('Invalid browser cache settings')
    for key in ('static_seconds', 'versioned_seconds'):
        if type(value[key]) is not int or value[key] < 0:
            raise ValueError('Browser cache lifetimes must be nonnegative whole seconds')
    if not isinstance(value['versioned_paths'], list):
        raise ValueError('Versioned paths must be a list')
    for path in value['versioned_paths']:
        pattern(path)
    result = copy.deepcopy(value)
    result['versioned_paths'] = list(dict.fromkeys(result['versioned_paths']))
    return result


def defaults(state):
    return validate(state.get('browser_cache', DEFAULTS))


def selected(site, state):
    result = defaults(state) if site.get('browser_cache') is None else validate(site['browser_cache'])
    result['versioned_paths'] = list(dict.fromkeys(result['versioned_paths'] + PROFILE_PATHS.get(site['profile'], [])))
    return result


def from_payload(payload):
    paths = payload.get('versioned_paths', '')
    if not isinstance(paths, str):
        raise ValueError('Enter one versioned path per line')
    return validate(dict(enabled=payload.get('browser_enabled'), static_seconds=payload.get('static_seconds'),
                         versioned_seconds=payload.get('versioned_seconds'),
                         versioned_paths=[p.strip() for p in paths.splitlines() if p.strip()]))


def change(state, payload, site=None):
    if site is not None and payload.get('inherit_browser_cache') is True:
        site.pop('browser_cache', None)
    else:
        (state if site is None else site)['browser_cache'] = from_payload(payload)


def control(seconds, immutable=False):
    return ('public, max-age=' + str(seconds) + (', immutable' if immutable else '')) if seconds else 'no-cache'


def template(text, site, state, suffix):
    if not re.fullmatch(r'[0-9a-f]{32}', site['id']) or suffix not in ('tpl', 'stpl'):
        raise ValueError('Invalid browser cache scope')
    name = '$hvb_' + site['id'] + '_' + suffix
    choice = selected(site, state)
    lines = ['map "$request_method:$status:$uri" ' + name + ' {', '    default "";']
    if choice['enabled']:
        prefix = '~^(?:GET|HEAD):(?:200|206|304):'
        for path in choice['versioned_paths']:
            lines.append('    ' + json.dumps(prefix + pattern(path) + '$') + ' ' +
                         json.dumps(control(choice['versioned_seconds'], True)) + ';')
        lines.append('    ' + json.dumps(prefix) + ' ' + json.dumps(control(choice['static_seconds'])) + ';')
    lines.append('}')
    headers = 'expires off;\n            add_header_inherit merge;\n            etag on;\n            if_modified_since exact;\n            add_header Cache-Control ' + name + ';'
    if text.count('expires max;') != 1:
        raise ValueError('Managed static routing does not contain the browser cache insertion point')
    return '\n'.join(lines) + '\n' + text.replace('expires max;', headers)
