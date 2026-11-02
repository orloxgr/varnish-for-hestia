#!/usr/bin/python3
"""Root-side addon bridge. The panel supplies its authenticated account context."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
META = json.loads((ROOT / 'addon.json').read_text())
HESTIA = Path('/usr/local/hestia')
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HESTIA': str(HESTIA), 'LANG': 'C.UTF-8'}


class RequestError(Exception):
    pass


def hestia(command, *args):
    result = subprocess.run([str(HESTIA / 'bin' / command), *args],
                            capture_output=True, text=True, timeout=30, env=ENV)
    if result.returncode:
        raise RequestError('The account or domain is unavailable in Hestia.')
    return json.loads(result.stdout)


def account_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', value):
        raise RequestError('Invalid account.')
    return value


def dispatch(request):
    owner = account_name(request.get('owner'))
    actor = account_name(request.get('actor'))
    actor_data = hestia('v-list-user', actor, 'json').get(actor)
    action = request.get('action', 'inventory')
    is_admin = bool(actor_data and actor_data.get('ROLE') == 'admin' and actor_data.get('SUSPENDED') != 'yes')
    if action in ('admin-inventory', 'admin-bulk', 'admin-server-settings', 'admin-memory', 'admin-memory-size'):
        if not is_admin:
            raise RequestError('Administrator access required.')
        from administration import request as admin_request
        return admin_request(hestia, action, request, META['slug'])
    owner_data = hestia('v-list-user', owner, 'json').get(owner)
    if not actor_data or not owner_data or actor_data.get('SUSPENDED') == 'yes':
        raise RequestError('Account unavailable.')
    if owner != actor and actor_data.get('ROLE') != 'admin':
        raise RequestError('Another account cannot be selected.')
    if owner_data.get('SUSPENDED') == 'yes' and not is_admin:
        raise RequestError('Account suspended.')
    domains = hestia('v-list-web-domains', owner, 'json')
    action = request.get('action', 'inventory')
    path = Path('/etc/varnish-for-hestia/settings.json')
    installed = path.exists() and json.loads(path.read_text()).get('installed')
    if action not in ('inventory', 'validate-site'):
        if not installed:
            raise RequestError('Install the service addon first.')
        from service import request as service_request
        return service_request(hestia, owner, action, request)
    if action == 'validate-site':
        domain = request.get('domain')
        if not isinstance(domain, str) or domain not in domains:
            raise RequestError('Domain is not owned by this account.')
    result = {
        'ok': True, 'addon': META['id'], 'version': META['version'],
        'owner': owner, 'actor': actor, 'stage': 'account-inventory',
        'sites': [{'domain': name,
                   'aliases': [s.strip() for s in row.get('ALIAS', '').split(',') if s.strip()],
                   'suspended': row.get('SUSPENDED') == 'yes',
                   'template': row.get('PROXY', '')}
                  for name, row in sorted(domains.items())],
    }
    if installed:
        from service import request as service_request
        data = service_request(hestia, owner, 'status', {})
        result.update(stage='service-managed', service_installed=True, enabled=data['enabled'],
                      allowed=data['allowed'], sites=data['sites'])
    return result


def locked_main():
    try:
        if os.geteuid() != 0:
            raise RequestError('This bridge must be invoked through the Hestia panel or by root.')
        if sys.argv[1:] == ['reconcile']:
            from service import reconcile
            state, config, result = reconcile(hestia)
            print(json.dumps({'ok': True, 'accounts': len(state['owners']), **result}))
            return 0
        if sys.argv[1:] == ['discover']:
            # Imports are from the root-owned installation, never the caller's
            # current working directory (the wrapper uses Python isolated mode).
            sys.path.insert(0, str(ROOT / 'src'))
            from inventory import collect
            from registry import reconcile
            state, changed = reconcile('/var/lib/'+META['id'], collect(hestia), META['slug'])
            print(json.dumps({'ok':True, 'stage':'desired-state-only', 'changed':changed,
                              'accounts':len(state['owners']),
                              'sites':sum(len(x['sites']) for x in state['owners'].values()),
                              'retired_accounts':len(state['retired'])}))
            return 0
        if sys.argv[1:]:
            raise RequestError('Unsupported command.')
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            raise RequestError('Request too large.')
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise RequestError('Expected a JSON object.')
        result = dispatch(request)
        code = 0
    except (RequestError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError, OSError):
        # Never echo raw CLI output, credentials or a caller-controlled value.
        result = {'ok': False, 'error': 'Request refused or Hestia unavailable.'}
        code = 1
    print(json.dumps(result))
    return code


if __name__ == '__main__':
    from operations import exclusive
    with exclusive():
        raise SystemExit(locked_main())
