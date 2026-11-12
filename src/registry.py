"""Persistent desired state, independent of service activation and Hestia files."""
from contextlib import contextmanager
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import uuid


def validate_inventory(inventory):
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError('An empty or failed Hestia inventory must not delete accounts')
    for owner, row in inventory.items():
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', owner):
            raise ValueError('Invalid account identity')
        if not isinstance(row.get('identity'), str) or not row['identity']:
            raise ValueError('Missing account creation identity')
        if not isinstance(row.get('sites'), dict):
            raise ValueError('Incomplete site inventory')
        for domain, site in row['sites'].items():
            def valid_name(s, wildcard=False):
                if not isinstance(s, str) or len(s) > 253:
                    return False
                if wildcard and s.startswith('*.'):
                    s = s[2:]
                return all(re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', label)
                           for label in s.split('.'))
            if not valid_name(domain) or not all(valid_name(s, True) for s in site.get('aliases', [])):
                raise ValueError('Invalid domain inventory')


def desired_state(previous, inventory, kind):
    """Compute desired state. No service/configuration changes occur here."""
    validate_inventory(inventory)
    state = copy.deepcopy(previous or {'schema':1, 'owners':{}, 'retired':[]})
    if (state.get('schema') != 1 or kind not in ('dragonfly', 'varnish') or
            state.get('kind', kind) != kind):
        raise ValueError('Unsupported state schema or addon')
    state['kind'] = kind
    owners = state['owners']
    # Retired slots stay reserved until explicit cleanup confirms removal of data.
    used = {row['database'] for row in [*owners.values(), *state['retired']]
            if 'database' in row}
    for owner in list(owners):
        if owner not in inventory or owners[owner]['identity'] != inventory[owner]['identity']:
            old = owners.pop(owner)
            old.pop('password', None)
            state['retired'].append(old)
    for owner, observed in sorted(inventory.items()):
        if owner not in owners:
            uid = uuid.uuid4().hex
            row = {'name':owner, 'id':uid, 'identity':observed['identity'],
                   'enabled':True, 'sites':{}, 'retired_sites':[]}
            if kind == 'dragonfly':
                slot = next(i for i in range(len(used)+1) if i not in used)
                used.add(slot)
                row.update(database=slot, username=owner+'_'+uid[:12],
                           password=secrets.token_urlsafe(32), prefix='dfh:'+uid+':')
            owners[owner] = row
        row = owners[owner]
        for key in ('package', 'role', 'suspended'):
            row[key] = observed[key]
        for domain in list(row['sites']):
            if domain not in observed['sites']:
                retired = row['sites'].pop(domain)
                retired.pop('token', None)
                row['retired_sites'].append(retired)
        for domain, site in sorted(observed['sites'].items()):
            if domain not in row['sites']:
                sid = uuid.uuid4().hex
                entry = {'domain':domain, 'id':sid, 'enabled':True, 'settings':{}}
                if kind == 'dragonfly':
                    entry['prefix'] = row['prefix'] + sid + ':'
                else:
                    from profile_settings import choices
                    entry.update(token=secrets.token_urlsafe(32), profile=choices(state)['default_profile'],
                                 custom_recv='', custom_backend_response='', bypass_cookies=[])
                row['sites'][domain] = entry
            entry = row['sites'][domain]
            if kind == 'varnish':
                entry.setdefault('bypass_cookies', [])
            entry.update(aliases=sorted(set(site.get('aliases', []))),
                         suspended=site.get('suspended', False))
    if kind == 'dragonfly':
        # Capacity is a desired setting; activation must validate/apply it safely.
        required = max(used, default=0) + 1
        state['required_database_capacity'] = max(16, 1 << (required - 1).bit_length())
    return state


@contextmanager
def locked_store(directory):
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError('State directory must not be a symlink')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    lock = directory / 'registry.lock'
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield directory / 'desired.json'


def reconcile(directory, inventory, kind):
    with locked_store(directory) as path:
        if path.is_symlink():
            raise ValueError('State file must not be a symlink')
        old = json.loads(path.read_text()) if path.exists() else None
        new = desired_state(old, inventory, kind)
        changed = old != new
        if changed:
            descriptor, candidate = tempfile.mkstemp(prefix='.desired-', dir=path.parent)
            try:
                with os.fdopen(descriptor, 'w') as stream:
                    json.dump(new, stream, sort_keys=True, indent=2)
                    stream.write('\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(candidate, path)
                directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if os.path.exists(candidate):
                    os.unlink(candidate)
        return new, changed
