#!/usr/bin/python3
"""Install/adopt one native Varnish, resuming an interrupted initial installation."""
import argparse
import base64
import grp
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import socket
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / 'src'))
from addon import hestia
from files import write, write_json, ensure_owned_directory
from inventory import collect
from operations import exclusive
from registry import desired_state
import maintenance
import repository
import routing
import service
import deployment
import progress
from vcl import render

META = json.loads((SOURCE / 'addon.json').read_text())
ID = 'varnish-for-hestia'
DROPIN = maintenance.DROPIN
CRON = maintenance.CRON
GUARD = DROPIN.with_name('zz-varnish-for-hestia-install.conf')
PENDING = service.STORE / 'install.json'
RECEIPT = service.STORE / 'install-receipt.json'
IN_PROGRESS = service.CONFIG / '.install-in-progress'


def run(*args, **kwargs):
    progress.stage('Command: ' + shlex.join(args))
    result = subprocess.run(args, capture_output=True, timeout=None, **kwargs)
    if result.returncode:
        for label, output in (('stdout', result.stdout), ('stderr', result.stderr)):
            if output:
                text = output.decode(errors='replace') if isinstance(output, bytes) else output
                sys.stderr.write(label + ':\n' + text.rstrip() + '\n')
        raise RuntimeError('Command failed (exit ' + str(result.returncode) + '): ' + shlex.join(args))
    return result


def native_version():
    result = run('dpkg-query', '-W', '-f=${Version} ${db:Status-Status}', 'varnish').stdout.decode().strip().split()
    if len(result) != 2 or result[1] != 'installed':
        raise ValueError('Install a configured native Varnish package first')
    return result[0]


def install_package():
    # Keep the distro/repository boundary; let APT select its signed candidate.
    # Existing native services are adopted without replacing their package.
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if release.get('VERSION_CODENAME', '').strip('"') != 'resolute':
        raise ValueError('The selected official fresh-install package requires the matching Ubuntu resolute repository')
    repository.setup()
    env = dict(os.environ, DEBIAN_FRONTEND='noninteractive')
    run('apt-get', 'update', '-o', 'APT::Update::Error-Mode=any', env=env)
    simulation = run('apt-get', '-s', 'install', 'varnish', 'varnish-modules').stdout.decode()
    removals = [line.split()[1] for line in simulation.splitlines() if line.startswith('Remv ')]
    if set(removals) - {'libvarnishapi1', 'libvarnishapi2', 'libvarnishapi3'}:
        raise ValueError('Package installation would remove another service')
    run('apt-get', 'install', '-y', 'varnish', 'varnish-modules', env=env)


def cookie_modules_available():
    # Compile the actual duplicate-header APIs, rather than guessing from a
    # package version or treating a missing optional module as a broken engine.
    program = '''vcl 4.1;
import header;
import cookie;
backend default { .host = "127.0.0.1"; .port = "9"; }
sub vcl_recv { cookie.parse(req.http.Cookie); }
sub vcl_backend_response {
    header.append(beresp.http.Set-Cookie, "fixture=1; Path=/");
    header.remove(beresp.http.Set-Cookie, "^fixture=");
}
'''
    with tempfile.TemporaryDirectory(prefix='hvh-cookie-modules-') as directory:
        # varnishd drops privileges while compiling. This fixture contains no
        # secrets and must remain readable by its native compiler account.
        Path(directory).chmod(0o755)
        source = Path(directory) / 'probe.vcl'
        source.write_text(program, encoding='utf-8')
        source.chmod(0o644)
        return subprocess.run(['/usr/sbin/varnishd', '-C', '-f', str(source)],
                              capture_output=True).returncode == 0


def cookie_module_package(engine_version):
    """Prefer a published module for the installed ABI, not a newer engine."""
    provides = run('dpkg-query', '-W', '-f=${Provides}', 'varnish').stdout.decode()
    abi = re.search(r'\b(?:varnishabi|varnishd-abi)-[A-Za-z0-9]+\b', provides)
    if abi is None:
        return 'varnish-modules'  # Let APT resolve its declared dependencies.
    available = run('apt-cache', 'show', 'varnish-modules').stdout.decode()
    for paragraph in available.split('\n\n'):
        version = re.search(r'^Version: (\S+)$', paragraph, re.M)
        dependencies = re.search(r'^Depends: (.*(?:\n[ \t].*)*)', paragraph, re.M)
        if not version or not dependencies:
            continue
        exact_engine = re.search(r'\bvarnish\s*\(\s*=\s*([^\s)]+)\s*\)', dependencies[1])
        if exact_engine and exact_engine[1] != engine_version:
            continue
        if re.search(r'(?<![A-Za-z0-9+-])' + re.escape(abi[0]) + r'(?![A-Za-z0-9+-])', dependencies[1]):
            return 'varnish-modules=' + version[1]
    return 'varnish-modules'  # Preserve native dependency resolution and errors.


def ensure_cookie_modules():
    if cookie_modules_available():
        return
    progress.stage('Installing native cookie/header modules for the existing Varnish ABI')
    # An adopted native engine already has its package source configured. Adding
    # the same repository with another Signed-By path makes APT itself unusable.
    # Use those configured sources for this dependency transaction.
    env = dict(os.environ, DEBIAN_FRONTEND='noninteractive', NEEDRESTART_MODE='l')
    run('apt-get', 'update', '-o', 'APT::Update::Error-Mode=any', env=env)
    # The engine is deliberately held at the installed version for this module
    # transaction. This is an ABI dependency, not a supported-version ceiling.
    engine_version = native_version()
    packages = ('varnish=' + engine_version, cookie_module_package(engine_version))
    preview = run('apt-get', '-s', '--no-remove', 'install', *packages, env=env).stdout.decode()
    if any(line.startswith('Remv ') or re.match(r'Inst varnish(?::[^ ]+)? ', line)
           for line in preview.splitlines()):
        raise ValueError('Cookie modules require a different Varnish engine; install the matching native module package')
    run('apt-get', 'install', '-y', '--no-remove', *packages, env=env)
    if not cookie_modules_available():
        raise ValueError('Installed native modules cannot compile the required cookie/header APIs')


def private_manifest(path):
    path = Path(path)
    info = path.stat()
    if path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o077:
        raise ValueError('Use a private root-owned JSON file')
    return json.loads(path.read_text())


def platform():
    if os.geteuid() != 0 or os.environ.get('SUDO_USER') == 'hestiaweb':
        raise ValueError('Run the installer from an administrator shell')
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if release.get('ID', '').strip('"') != 'ubuntu' or os.uname().machine != 'x86_64':
        raise ValueError('Supported platform: Ubuntu amd64')
    run('dpkg-query', '-W', '-f=${Version}', 'hestia')
    conf = Path('/usr/local/hestia/conf/hestia.conf').read_text()
    if "PROXY_SYSTEM='nginx'" not in conf or "WEB_SYSTEM='apache2'" not in conf:
        raise ValueError('Required topology: Nginx proxy and Apache/PHP-FPM')
    return int(re.search(r"^WEB_PORT='(\d+)'", conf, re.M)[1])


def save_pending(record, phase, state=None, config=None):
    record['phase'] = phase
    if state is not None:
        record['desired'] = state
    if config is not None:
        record['settings'] = config
    write_json(PENDING, record)


def prepare_guard():
    # Delay only this native package's automatic start until credentials and
    # group permissions are ready. No native unit or policy-rc.d is changed.
    write(IN_PROGRESS, ID + '\n')
    write(GUARD, '# Managed by ' + ID + '\n[Unit]\nConditionPathExists=!' + str(IN_PROGRESS) + '\n', 0o644)
    run('systemctl', 'daemon-reload')


def release_guard():
    IN_PROGRESS.unlink(missing_ok=True); GUARD.unlink(missing_ok=True)
    run('systemctl', 'daemon-reload')


def initialize(args, inventory, port):
    binary_exists = Path('/usr/sbin/varnishd').is_file()
    if binary_exists and not args.adopt:
        raise ValueError('An existing Varnish requires an explicit private adoption manifest')
    manifest = private_manifest(args.adopt) if args.adopt else None
    if manifest and not binary_exists:
        raise ValueError('Adoption requires an existing native Varnish')
    maintenance.check_integration()
    if DROPIN.exists() or CRON.exists() or GUARD.exists():
        raise ValueError('Unexpected existing initial-install integration')
    listen_port = getattr(args, 'listen_port', None) or (manifest or {}).get('listen_port', 6081)
    admin_port = getattr(args, 'admin_port', None) or (manifest or {}).get('admin_port', 6082)
    if not all(type(value) is int and 1 <= value <= 65535 for value in (listen_port, admin_port)) or listen_port == admin_port:
        raise ValueError('Use distinct valid native TCP ports')
    addresses = [site['origin_ip'] for row in inventory.values() for site in row['sites'].values()]
    if not addresses:
        addresses = list(hestia('v-list-sys-ips', 'json'))
    origin = str(ipaddress.ip_address(addresses[0]))
    previous = {}
    for name in ('desired.json', 'applied.json'):
        path = service.STORE / name
        previous[name] = base64.b64encode(path.read_bytes()).decode() if path.exists() else None
    old = json.loads(base64.b64decode(previous['desired.json'])) if previous['desired.json'] else None
    state = desired_state(old, inventory, 'varnish')
    secret = (secrets.token_urlsafe(32) + '\n').encode()
    if manifest:
        native_version()
        path = Path(manifest['admin_secret_file'])
        if not path.is_absolute() or path.is_symlink() or path.stat().st_mode & 0o007:
            raise ValueError('Use the existing private native administrator secret file')
        secret = path.read_bytes()
        run('varnishadm', '-T', '127.0.0.1:' + str(admin_port), '-S', str(path), 'status')
        for owner, sites in manifest['sites'].items():
            for domain, imported in sites.items():
                site = state['owners'][owner]['sites'][domain]
                site.update(profile=imported['profile'], token=imported['token'])
                site['settings']['original_template'] = imported.get('original_template', inventory[owner]['sites'][domain]['proxy_template'])
    else:
        for number in (listen_port, admin_port):
            with socket.socket() as probe:
                try:
                    probe.bind(('127.0.0.1', number))
                except OSError:
                    raise ValueError('A required local Varnish port is already occupied') from None
    config = {'schema': 1, 'installed': False, 'origin_ip': origin, 'origin_port': port,
              'listen_port': listen_port, 'admin_port': admin_port, 'memory_mb': args.memory_mb or 256,
              'allowed_packages': None, 'denied_packages': [], 'adopted': bool(manifest)}
    for owner, row in state['owners'].items():
        for domain, site in row['sites'].items():
            site['settings'].setdefault('original_template', inventory[owner]['sites'][domain]['proxy_template'])
    render(state, config)
    ensure_owned_directory(service.CONFIG, ID)
    service.CONFIG.chmod(0o700)
    service.STORE.mkdir(mode=0o700, parents=True, exist_ok=True); service.STORE.chmod(0o700)
    record = {'schema': 1, 'addon': ID, 'mode': 'adopt' if manifest else 'fresh',
              'desired': state, 'settings': config, 'previous': previous,
              'admin_secret': base64.b64encode(secret).decode()}
    save_pending(record, 'prepared')
    return record


def install(args):
    progress.stage('Checking platform and native Hestia topology')
    port = platform()
    if PENDING.exists():
        record = private_manifest(PENDING)
        if record.get('schema') != 1 or record.get('addon') != ID or record.get('mode') not in ('adopt', 'fresh'):
            raise ValueError('Unrecognized pending installation')
        maintenance.check_integration()
        if GUARD.is_symlink() or (GUARD.exists() and '# Managed by ' + ID not in GUARD.read_text()):
            raise ValueError('Refusing an unmanaged startup guard')
        if args.memory_mb is not None and args.memory_mb != record['settings']['memory_mb']:
            raise ValueError('An interrupted installation retains its original memory budget')
        resumed = True
    elif (service.CONFIG / 'settings.json').exists() and json.loads((service.CONFIG / 'settings.json').read_text()).get('installed'):
        progress.stage('Existing installation found; retaining credentials, site choices and cache size')
        native_version()
        ensure_cookie_modules()
        existing = service.settings()
        if args.memory_mb is not None and args.memory_mb != existing['memory_mb']:
            raise ValueError('Existing memory budget is retained; change Varnish cache size in Hestia Plugins > Varnish > All accounts')
        before = (service.CONFIG / 'settings.json').read_bytes()
        try:
            progress.stage('Publishing addon code and Hestia panel integration')
            run('python3', str(SOURCE / 'tools/install-integration.py'))
            progress.stage('Installing managed proxy template definitions')
            existing['template_name'] = routing.install_templates(SOURCE, existing)
            write_json(service.CONFIG / 'settings.json', existing)
            _, _, result = service.reconcile(hestia)
            progress.stage('Enabling native ESI attribute processing without restarting Varnish')
            maintenance.configure_esi(existing)
            progress.stage('Scheduling daily upstream cookie recognition updates')
            maintenance.install_cron()
        except Exception:
            write(service.CONFIG / 'settings.json', before)
            deployment.rollback()
            raise
        deployment.commit()
        progress.stage('Upgrade complete; native Varnish and web configuration applied')
        return {'ok': True, 'mode': 'upgrade-or-reinstall', 'credentials_preserved': True, **result}
    else:
        progress.stage('Preparing initial installation/adoption and complete account inventory')
        record = initialize(args, collect(hestia), port)
        resumed = False
    inventory = collect(hestia)
    state = desired_state(record['desired'], inventory, 'varnish')
    config = record['settings']; config['installed'] = False
    for owner, row in state['owners'].items():
        for domain, site in row['sites'].items():
            site['origin_ip'] = inventory[owner]['sites'][domain]['origin_ip']
            site['settings'].setdefault('original_template', inventory[owner]['sites'][domain]['proxy_template'])
            site['settings']['routing_active'] = False
    program = render(state, config)
    apache_before = routing.APACHE.read_bytes() if routing.APACHE.exists() else None
    undo = [(owner, domain,
             state['owners'][owner]['sites'][domain]['settings']['original_template'] if resumed and routing.owned_template(web['proxy_template']) else web['proxy_template'],
             web['proxy_template'], web['proxy_extensions'])
            for owner, data in inventory.items() for domain, web in data['sites'].items() if web['proxy_template']]
    DROPIN.parent.mkdir(parents=True, exist_ok=True)
    try:
        if record['mode'] == 'fresh':
            prepare_guard()
        service.CONFIG.chmod(0o700)
        write(service.ACTIVE, program)
        write(service.CONFIG / 'admin.secret', base64.b64decode(record['admin_secret'], validate=True))
        write_json(service.CONFIG / 'settings.json', config)
        maintenance.integration_files(SOURCE, config)
        CRON.unlink(missing_ok=True)
        save_pending(record, 'package', state, config)
        if record['mode'] == 'fresh':
            install_package()
        native_version()
        ensure_cookie_modules()
        gid = grp.getgrnam('varnish').gr_gid
        os.chown(service.CONFIG, 0, gid); service.CONFIG.chmod(0o750)
        generations = service.CONFIG / 'generations'; generations.mkdir(mode=0o750, exist_ok=True)
        os.chown(generations, 0, gid); generations.chmod(0o750)
        os.chown(service.ACTIVE, 0, gid); service.ACTIVE.chmod(0o640)
        release_guard(); service.verify_native_unit()
        save_pending(record, 'starting', state, config)
        subprocess.run(['systemctl', 'reset-failed', 'varnish'], capture_output=True, timeout=None)
        run('systemctl', 'restart', 'varnish'); service.wait_healthy(config)
        config['template_name'] = routing.install_templates(SOURCE, config)
        run('python3', str(SOURCE / 'tools/install-integration.py'))
        save_pending(record, 'routing', state, config)
        # The registry must start from the transaction's persisted identities,
        # including after a failed attempt restored an absent/older registry.
        write_json(service.STORE / 'desired.json', state)
        state, _, result = service.reconcile(hestia, config_override=config)
        maintenance.integration_files(SOURCE, config)
        run('systemctl', 'enable', 'varnish')
        config['installed'] = True
        save_pending(record, 'complete', state, config)
        write_json(service.CONFIG / 'settings.json', config)
        os.replace(PENDING, RECEIPT)
        directory = os.open(service.STORE, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        deployment.commit()
        progress.stage('Installation complete; service enabled and configuration committed')
        return {'ok': True, 'mode': record['mode'], 'resumed': resumed, 'accounts': len(state['owners']), **result}
    except Exception:
        try:
            routing.rollback(undo, apache_before)
        finally:
            CRON.unlink(missing_ok=True)
            config['installed'] = False
            write_json(service.CONFIG / 'settings.json', config)
            save_pending(record, 'retry-required', state, config)
            for name, encoded in record['previous'].items():
                path = service.STORE / name
                if encoded is None:
                    path.unlink(missing_ok=True)
                else:
                    write(path, base64.b64decode(encoded))
            if record['mode'] == 'fresh':
                prepare_guard()
                subprocess.run(['systemctl', 'disable', '--now', 'varnish'], capture_output=True, timeout=None)
            else:
                DROPIN.unlink(missing_ok=True); release_guard()
                run('systemctl', 'restart', 'varnish')
        raise


def perform(args):
    if args.memory_mb is not None and args.memory_mb <= 0:
        raise ValueError('Choose a positive cache budget in MiB')
    progress.stage('Waiting for the addon operation lock (another reconcile or panel operation may be active)')
    with exclusive():
        progress.stage('Operation lock acquired')
        return install(args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adopt', metavar='PRIVATE_MANIFEST')
    parser.add_argument('--memory-mb', type=int)
    parser.add_argument('--listen-port', type=int, help='Initial loopback HTTP listener port (default 6081)')
    parser.add_argument('--admin-port', type=int, help='Initial loopback administrative port (default 6082)')
    parser.add_argument('--json', action='store_true', help='Write the final result as JSON to stdout; progress stays on stderr')
    args = parser.parse_args()
    raise SystemExit(progress.execute(lambda: perform(args), title=META['title'],
                                     version=META['version'], json_output=args.json))
