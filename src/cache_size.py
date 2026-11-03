"""Restart the existing native service with a durable cache-budget change."""
import json
from pathlib import Path
import subprocess

from files import write, write_json
import service
import transaction

JOURNAL = 'resize.json'


def validate(value):
    if type(value) is not int or not value > 0:
        raise ValueError('Cache size must be a positive number of MiB')
    return value


def paths():
    from maintenance import DROPIN
    return [service.CONFIG / 'settings.json', DROPIN]


def check_budget(config):
    result = subprocess.run(['systemctl', 'show', 'varnish', '-p', 'MainPID', '--value'],
                            capture_output=True, text=True, timeout=None)
    pid = result.stdout.strip()
    if result.returncode or not pid.isdecimal() or int(pid) < 1:
        raise RuntimeError('The native Varnish manager is unavailable')
    # Inspect the running manager, rather than non-atomic storage counters that
    # can change while requests refill the cache immediately after a restart.
    args = (Path('/proc') / pid / 'cmdline').read_bytes().decode().split('\0')
    if (Path(args[0]).name != 'varnishd' or
            sum(args[i] == '-s' and args[i+1] == 'malloc,' + str(config['memory_mb']) + 'm'
                for i in range(len(args)-1)) != 1):
        raise RuntimeError('The running cache storage does not match the requested size')


def start(config):
    service.routing.run('systemctl', 'daemon-reload')
    service.verify_native_unit()
    service.routing.run('systemctl', 'reset-failed', 'varnish')
    service.routing.run('systemctl', 'restart', 'varnish')
    service.wait_healthy(config)
    check_budget(config)


def recover():
    record = transaction.read(service.STORE, paths(), filename=JOURNAL)
    if record is None:
        return False
    transaction.restore_files(record)
    config = json.loads((service.CONFIG / 'settings.json').read_text())
    validate(config['memory_mb'])
    start(config)
    transaction.finish(service.STORE, filename=JOURNAL)
    return True


def resize(value):
    from maintenance import DROPIN, MARKER, service_dropin
    validate(value)
    # Called under the bridge/installer's existing exclusive operation lock.
    service.recover_pending()
    config = service.settings()
    if value == config['memory_mb']:
        return config, False
    if (DROPIN.is_symlink() or DROPIN.parent.is_symlink() or not DROPIN.is_file() or
            not DROPIN.read_text().startswith(MARKER + '\n')):
        raise ValueError('The managed native service configuration is unavailable')
    updated = dict(config, memory_mb=value)
    transaction.begin(service.STORE, paths(), filename=JOURNAL)
    try:
        write(DROPIN, service_dropin(updated), 0o644)
        write_json(service.CONFIG / 'settings.json', updated)
        start(updated)
    except Exception:
        try:
            recover()
        except Exception:
            raise RuntimeError('Cache resize failed; recovery is pending. Check the native Varnish service.') from None
        raise RuntimeError('Cache resize failed; the previous size was restored. Cache contents were cleared.') from None
    transaction.finish(service.STORE, filename=JOURNAL)
    return updated, True
