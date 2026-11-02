"""Private configuration archives, cold restore and native route restoration."""
import base64
import copy
import datetime
import grp
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

from files import write, write_json, ensure_owned_directory
from inventory import collect
from registry import desired_state, locked_store
from vcl import render
import routing
import service
import deployment
import transaction
import repository

ID = 'varnish-for-hestia'
INSTALL = Path('/opt') / ID
ROUTE = Path('/usr/local/hestia/web/plugins/varnish')
BRIDGE = Path('/usr/local/hestia/bin/v-varnish-hestia')
DROPIN = Path('/etc/systemd/system/varnish.service.d/zz-varnish-for-hestia.conf')
CRON = Path('/etc/cron.d') / ID
MARKER = '# Managed by ' + ID


def root_only():
    if os.geteuid() != 0 or os.environ.get('SUDO_USER') == 'hestiaweb':
        raise ValueError('This command requires an administrator root shell')


def private_path(value):
    path = Path(value)
    if not path.is_absolute() or path.name in ('.', '..') or path.parent.resolve() != path.parent:
        raise ValueError('Use an absolute backup path without symlinks')
    info = path.parent.stat()
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError('Backup parent must be root-owned and mode 700')
    if any(path.is_relative_to(p) for p in (service.CONFIG, service.STORE, INSTALL, ROUTE)):
        raise ValueError('Keep recovery archives outside addon directories')
    return path


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate(payload):
    config, state = payload['settings'], payload['desired']
    if (config.get('schema') != 1 or config.get('listen_port') != 6081 or config.get('admin_port') != 6082 or
            not isinstance(config.get('memory_mb'), int) or not 64 <= config['memory_mb'] <= 1048576 or
            state.get('schema') != 1 or state.get('kind') != 'varnish'):
        raise ValueError('Unsupported addon configuration')
    secret = base64.b64decode(payload['admin_secret'], validate=True)
    if not secret or len(secret) > 4096 or b'\0' in secret:
        raise ValueError('Invalid administrator secret in archive')
    render(state, config)
    if payload.get('repository') is not None:
        repository.validate(payload['repository'])
    for owner, row in state['owners'].items():
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', owner):
            raise ValueError('Invalid archived owner')
        for site in row['sites'].values():
            original = site['settings'].get('original_template', 'default')
            if original and (not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', original) or original.startswith(routing.NAME)):
                raise ValueError('Archive must contain an independent original proxy template')
    return secret


def backup(value):
    root_only()
    destination = private_path(value)
    service.recover_pending()
    with locked_store(service.STORE):
        payload = {'settings': service.settings(),
                   'desired': json.loads((service.STORE / 'desired.json').read_text()),
                   'admin_secret': base64.b64encode((service.CONFIG / 'admin.secret').read_bytes()).decode(),
                   'repository': repository.current()}
        validate(payload)
        archive = {'schema': 1, 'addon': ID, 'service_version': '9.1.0',
                   'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'cache_data_included': False, 'payload': payload, 'sha256': digest(payload)}
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(archive, stream, sort_keys=True, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    return {'ok': True, 'operation': 'backup', 'accounts': len(payload['desired']['owners']), 'cache_data_included': False}


def read_backup(value):
    path = private_path(value)
    info = path.stat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077 or info.st_size > 64 * 1024 * 1024:
        raise ValueError('Archive must be a private root-owned regular file, at most 64 MiB')
    archive = json.loads(path.read_text())
    if (archive.get('schema') != 1 or archive.get('addon') != ID or archive.get('service_version') != '9.1.0' or
            archive.get('sha256') != digest(archive['payload'])):
        raise ValueError('Unsupported or damaged archive')
    validate(archive['payload'])
    return archive['payload']


def check_integration():
    deployment.check()
    for path in (ROUTE, service.CONFIG):
        if path.is_symlink() or path.resolve() != path or (path.exists() and
                (not (path / '.addon-owner').is_file() or (path / '.addon-owner').read_text().strip() != ID)):
            raise ValueError('Refusing an unmanaged addon directory')
    for path in (BRIDGE, DROPIN, CRON, routing.APACHE):
        if path.is_symlink() or (path.exists() and MARKER not in path.read_text()):
            raise ValueError('Refusing an unmanaged integration file')
    if service.STORE.is_symlink() or service.STORE.resolve() != service.STORE:
        raise ValueError('Refusing an unmanaged state path')
    record = repository.current()
    if record is not None:
        repository.check_paths(record)


def service_dropin(config):
    return (MARKER + '\n[Service]\nType=exec\nPIDFile=\nExecStart=\n'
          'ExecStart=/usr/sbin/varnishd -F -a 127.0.0.1:6081 -T 127.0.0.1:6082 -f ' + str(service.ACTIVE) +
          ' -S ' + str(service.CONFIG / 'admin.secret') + ' -p feature=+http2 -s malloc,' + str(config['memory_mb']) + 'm\n'
          'ExecReload=\nExecReload=/usr/sbin/varnishreload -p hvh_reload -m 2 ' + str(service.ACTIVE) + '\n')


def integration_files(source, config):
    DROPIN.parent.mkdir(parents=True, exist_ok=True)
    write(DROPIN, service_dropin(config), 0o644)
    write(CRON, MARKER + '\nSHELL=/bin/sh\nPATH=/usr/sbin:/usr/bin:/sbin:/bin\n'
          '* * * * * root /usr/local/hestia/bin/v-varnish-hestia reconcile >/dev/null 2>&1\n', 0o644)



def restore_paths():
    return [service.CONFIG/name for name in ('settings.json','active.vcl','admin.secret')] + [
        service.STORE/name for name in ('desired.json','applied.json')] + [DROPIN,CRON]


def recover_restore():
    record=transaction.read(service.STORE,restore_paths(),filename='restore.json')
    if record is None:return
    extra=record['extra']
    routing.run('systemctl','stop','varnish')
    repository.restore(extra['repository'])
    transaction.restore_files(record)
    before=base64.b64decode(extra['apache']) if extra['apache'] is not None else None
    routing.rollback(extra['routes'],before)
    routing.run('systemctl','daemon-reload')
    if extra['installed']:
        subprocess.run(['systemctl','reset-failed','varnish'],capture_output=True,timeout=20)
        routing.run('systemctl','start','varnish');service.wait_healthy(extra['config'])
        deployment.rollback()
    else:
        for path in (ROUTE,service.CONFIG):
            if path.exists():shutil.rmtree(path)
        deployment.remove()
        for path in service.STORE.iterdir():
            if path.name not in ('registry.lock','restore.json') and path.is_file():path.unlink()
    transaction.finish(service.STORE,filename='restore.json')


def restore(value, hestia, source):
    root_only()
    payload = read_backup(value)
    recover_restore()
    service.recover_pending()
    check_integration()
    version = subprocess.run(['dpkg-query', '-W', '-f=${Version}', 'varnish'], capture_output=True, text=True, timeout=20)
    if version.returncode or not version.stdout.startswith('9.1.0-'):
        raise ValueError('Install the supported Varnish 9.1.0 package before restore')
    installed = (service.CONFIG / 'settings.json').is_file() and json.loads((service.CONFIG / 'settings.json').read_text()).get('installed')
    if installed:
        service.settings()
    elif subprocess.run(['systemctl', 'is-active', '--quiet', 'varnish'], capture_output=True).returncode == 0:
        raise ValueError('Refusing to replace an active unmanaged Varnish')
    if not installed and service.STORE.exists() and any(p.name != 'registry.lock' for p in service.STORE.iterdir()):
        raise ValueError('Refusing unmanaged existing addon state')
    inventory = collect(hestia)
    previous_repository = repository.current()
    archived = copy.deepcopy(payload['desired'])
    for name, row in archived['owners'].items():
        if name in inventory:
            row['identity'] = inventory[name]['identity']
        for site in row['sites'].values():
            site['settings']['routing_active'] = False
    state = desired_state(archived, inventory, 'varnish')
    config = copy.deepcopy(payload['settings'])
    config['installed'] = True
    config['template_name'] = routing.install_templates(source)
    changes = routing.plan(state, inventory, config)
    for change in changes:
        if not (routing.TEMPLATES / (change[3] + '.tpl')).is_file():
            raise ValueError('Restore requires the original native proxy templates')
    program = render(state, config)
    # Compile before creating or changing installed service paths. A rejected
    # archive must also leave a removed installation ready for a later restore.
    gid = grp.getgrnam('varnish').gr_gid
    with tempfile.TemporaryDirectory(prefix='hvh-restore-', dir='/var/tmp') as directory:
        os.chown(directory, 0, gid); os.chmod(directory, 0o750)
        candidate = Path(directory) / 'candidate.vcl'
        write(candidate, program, 0o640, gid)
        compiled = subprocess.run(['/usr/sbin/varnishd', '-C', '-f', str(candidate)], capture_output=True, timeout=180)
        if compiled.returncode:
            raise ValueError('Archived VCL did not compile; current service was retained')
    ensure_owned_directory(service.CONFIG, ID)
    os.chown(service.CONFIG, 0, gid); service.CONFIG.chmod(0o750)
    service.STORE.mkdir(mode=0o700, parents=True, exist_ok=True)
    (service.CONFIG / 'generations').mkdir(mode=0o750, exist_ok=True)
    os.chown(service.CONFIG / 'generations', 0, gid)
    paths = [service.CONFIG / name for name in ('settings.json', 'active.vcl', 'admin.secret')]
    paths += [service.STORE / name for name in ('desired.json', 'applied.json')]
    paths += [DROPIN, CRON]
    before = {p: p.read_bytes() if p.is_file() else None for p in paths}
    previous_config = json.loads(before[service.CONFIG / 'settings.json']) if installed else None
    undo = None
    with locked_store(service.STORE):
        original_routes=[(owner,domain,site['proxy_template'],site['proxy_template'],site['proxy_extensions'])
                         for owner,row in inventory.items() for domain,site in row['sites'].items() if site['proxy_template']]
        apache=routing.APACHE.read_bytes() if routing.APACHE.exists() else None
        transaction.begin(service.STORE,restore_paths(),{'installed':bool(installed),'config':previous_config,
                          'repository':previous_repository,'routes':original_routes,
                          'apache':base64.b64encode(apache).decode() if apache is not None else None},filename='restore.json')
        try:
            service.admin(previous_config, 'ping') if installed else None
            routing.run('systemctl', 'stop', 'varnish')
            write(service.CONFIG / '.addon-owner', ID + '\n', 0o644)
            write(service.CONFIG / 'admin.secret', validate(payload))
            write(service.ACTIVE, program, 0o640, gid)
            write_json(service.CONFIG / 'settings.json', config)
            repository.restore(payload.get('repository'))
            integration_files(source, config)
            routing.run('systemctl', 'daemon-reload'); service.verify_native_unit()
            subprocess.run(['systemctl', 'reset-failed', 'varnish'], capture_output=True, timeout=20)
            routing.run('systemctl', 'start', 'varnish'); service.wait_healthy(config)
            _, undo = routing.apply(changes, routing.apache_config(inventory, config['origin_port']))
            subprocess.run(['python3', str(source / 'tools/install-integration.py')], check=True, capture_output=True, timeout=60)
            write_json(service.STORE / 'desired.json', state); write_json(service.STORE / 'applied.json', state)
            routing.run('systemctl', 'enable', 'varnish')
        except Exception:
            routing.run('systemctl', 'stop', 'varnish')
            repository.restore(previous_repository)
            if undo is not None:
                routing.rollback(*undo)
            for path, data in before.items():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    write(path, data, 0o640 if path == service.ACTIVE else 0o644 if path in (DROPIN, CRON) else 0o600,
                          gid if path == service.ACTIVE else 0)
            routing.run('systemctl', 'daemon-reload')
            if installed:
                subprocess.run(['systemctl', 'reset-failed', 'varnish'], capture_output=True, timeout=20)
                routing.run('systemctl', 'start', 'varnish'); service.wait_healthy(previous_config)
            else:
                for path in (ROUTE, service.CONFIG):
                    if path.exists():
                        shutil.rmtree(path)
                for path in service.STORE.iterdir():
                    if path.name != 'registry.lock' and path.is_file():
                        path.unlink()
            deployment.rollback() if installed else deployment.remove()
            transaction.finish(service.STORE,filename='restore.json')
            raise RuntimeError('Restore failed; previous service configuration restored, cache may be empty' if installed
                               else 'Restore failed; service remains stopped and archive is retained') from None
    transaction.finish(service.STORE,filename='restore.json')
    deployment.commit()
    return {'ok': True, 'operation': 'restore', 'accounts': len(state['owners']), 'cache_data_restored': False}


def uninstall(value, hestia):
    root_only()
    check_integration()
    result = backup(value)
    inventory = collect(hestia)
    state = json.loads((service.STORE / 'desired.json').read_text())
    changes = []
    for name, owner in inventory.items():
        for domain, observed in owner['sites'].items():
            current = observed['proxy_template']
            if not routing.owned_template(current):
                continue
            saved = state['owners'].get(name, {}).get('sites', {}).get(domain, {}).get('settings', {})
            original = saved.get('original_template', 'default')
            if original.startswith(routing.NAME) or not (routing.TEMPLATES / (original + '.tpl')).is_file():
                raise ValueError('The original proxy template is unavailable')
            changes.append((name, domain, current, original, observed['proxy_extensions']))
    apache_before = routing.APACHE.read_bytes() if routing.APACHE.exists() else None
    _, undo = routing.apply(changes, apache_before.decode() if apache_before else MARKER + '\n')
    try:
        routing.APACHE.unlink(missing_ok=True)
        routing.run('apache2ctl', 'configtest'); routing.run('systemctl', 'reload', 'apache2')
        routing.run('systemctl', 'disable', '--now', 'varnish')
    except Exception:
        routing.rollback(*undo)
        raise RuntimeError('Uninstall failed; original addon routes were restored') from None
    for path in (CRON, DROPIN, BRIDGE):
        path.unlink(missing_ok=True)
    repository.remove()
    routing.run('systemctl', 'daemon-reload')
    templates = [p for p in routing.TEMPLATES.glob(routing.NAME + '*')
                 if p.suffix in ('.tpl', '.stpl') and routing.owned_template(p.stem)]
    for path in templates:
        path.unlink()
    for path in (ROUTE, service.CONFIG, service.STORE):
        if path.exists():
            if path.resolve() != path or path.is_symlink():
                raise ValueError('Unexpected removal target')
            shutil.rmtree(path)
    deployment.remove()
    return dict(result, operation='uninstall', native_package_retained=True, native_service_stopped=True,
                restored_native_routes=len(changes))
