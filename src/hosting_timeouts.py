"""Follow native Nginx allowances; Apache is Hestia's direct Varnish origin."""
import re
import subprocess
from decimal import Decimal

KEYS = ('connect', 'read', 'send')


def duration(value):
    value = re.sub(r'\s+', '', value.strip().strip('"\''))
    if value.isdecimal():
        return int(value) * 1000
    parts = list(re.finditer(r'([0-9]+)(ms|s|m|h|d|w|M|y)', value))
    if not parts or ''.join(p[0] for p in parts) != value:
        raise ValueError('Invalid native Nginx timeout')
    units = dict(ms=1, s=1000, m=60000, h=3600000, d=86400000, w=604800000, M=2592000000, y=31536000000)
    return sum(int(p[1]) * units[p[2]] for p in parts)


def validate(value):
    if (not isinstance(value, dict) or set(value) != set(KEYS) or
            any(type(v) is not int or v < 0 for v in value.values())):
        raise ValueError('Invalid native proxy timeouts')
    return dict(value)


def discover(dump):
    files = re.split(r'(?m)^# configuration file (/.+):\s*\n', dump)
    if len(files) == 1:
        raise ValueError('The loaded Nginx configuration could not be inspected')
    found = {key: [] for key in KEYS}
    for path, content in zip(files[1::2], files[2::2]):
        # Avoid feeding generated allowances back into the next calculation.
        # Native included files still appear separately in nginx -T.
        if '# Managed by varnish-for-hestia' in content or re.search(r'upstream hvh_(?:http|https)_', content):
            continue
        for match in re.finditer(r'(?m)^\s*proxy_(connect|read|send)_timeout\s+([^;]+);\s*(?:#.*)?$', content):
            found[match[1]].append(duration(match[2]))
    return {key: max(values) if values else 60000 for key, values in found.items()}


def refresh(state):
    result = subprocess.run(['nginx', '-T'], capture_output=True, text=True, timeout=None)
    if result.returncode:
        raise RuntimeError('Native Nginx timeout discovery failed; current configuration retained')
    state['hosting_timeouts'] = discover(result.stdout)


def seconds(value):
    return format(Decimal(value) / 1000, 'f') + 's'


def backend(state, first_byte):
    values = state.get('hosting_timeouts')
    if values is None:
        return '' if first_byte is None else ' .first_byte_timeout = ' + format(Decimal(str(first_byte)), 'f') + 's;'
    values = validate(values)
    # No Webuzo HTTPS origin bridge here: Apache is the direct backend.
    wait = seconds(values['read']) if first_byte is None else format(Decimal(str(first_byte)), 'f') + 's'
    return (' .connect_timeout = ' + seconds(values['connect']) + '; .first_byte_timeout = ' + wait +
            '; .between_bytes_timeout = ' + seconds(values['read']) + ';')


def frontend(state):
    values = validate(state['hosting_timeouts'])
    from server_settings import choices
    override = choices(state)['first_byte_timeout_seconds']
    wait = values['read'] if override is None else max(values['read'], Decimal(str(override)) * 1000)
    return dict(values, read=values['connect'] + values['send'] + wait)


def template(text, state):
    values = frontend(state)
    directives = '\n    '.join('proxy_' + key + '_timeout ' + seconds(values[key]) + ';' for key in KEYS)
    return text.replace('    proxy_http_version 1.1;', '    ' + directives + '\n    proxy_http_version 1.1;')


def session(state):
    if 'hosting_timeouts' not in state:
        return ''
    value = seconds(frontend(state)['read'])
    # Raise native delivery allowances when necessary; never shorten them.
    return ('\n  if (sess.idle_send_timeout < ' + value + ') { set sess.idle_send_timeout = ' + value + '; }' +
            '\n  if (sess.send_timeout < ' + value + ') { set sess.send_timeout = ' + value + '; }\n')
