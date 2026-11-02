"""Administrator-only server choices and an on-demand native memory snapshot."""
import json
import subprocess


def choices(state):
    result = state.get('server_settings', {})
    if not isinstance(result, dict) or set(result) - {'first_byte_timeout_seconds'}:
        raise ValueError('Invalid server settings')
    value = result.get('first_byte_timeout_seconds')
    if value is not None and (type(value) is not int or not 1 <= value <= 3600):
        raise ValueError('First-byte timeout must be 1–3600 seconds')
    return {'first_byte_timeout_seconds': value}


def change(state, payload):
    value = payload.get('first_byte_timeout_seconds')
    candidate = {'server_settings': {'first_byte_timeout_seconds': value}}
    state['server_settings'] = choices(candidate)


def memory(config):
    result = subprocess.run(['varnishstat', '-1', '-j'], capture_output=True, text=True, timeout=5)
    if result.returncode:
        raise RuntimeError('Native Varnish memory snapshot is unavailable')
    data = json.loads(result.stdout)
    counters = data.get('counters', data)
    def value(name):
        row = counters.get('SMA.s0.'+name, {})
        number = row.get('value')
        return number if type(number) in (int, float) and number >= 0 else None
    used, free = value('g_bytes'), value('g_space')
    if used is None or free is None:
        raise RuntimeError('Native malloc cache counters are unavailable')
    return {'used_bytes': used, 'free_bytes': free, 'budget_mb': config['memory_mb']}
