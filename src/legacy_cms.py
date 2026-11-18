"""Retire the former CMS helper; retain only owned-resource rollback support."""
import json
from pathlib import Path
import stat
import subprocess
from files import write, write_json

UNIT=Path('/etc/systemd/system/varnish-for-hestia-cms.service')
NAME='varnish-for-hestia-cms'
CODE=Path('/opt/varnish-for-hestia')
SOCKET=Path('/run/varnish-for-hestia-cms/sessions.sock')


def run(*args):
    result=subprocess.run(list(args),capture_output=True,text=True)
    if result.returncode:raise RuntimeError('Legacy CMS helper cleanup or recovery failed')
    return result.stdout.strip()


def configuration_path():
    import service
    return service.STORE/'cms-sessions.json'


def unit():
    return '''# Managed by varnish-for-hestia
[Unit]
Description=Varnish for Hestia CMS session resolver
After=network.target
[Service]
Type=simple
User=root
Group=root
RuntimeDirectory='''+NAME+'''
RuntimeDirectoryMode=0755
ExecStart=/usr/bin/python3 -I -B '''+str(CODE/'shared/cms_session_server.py')+''' --config '''+str(configuration_path())+'''
TimeoutStartSec=infinity
Restart=on-failure
RestartSec=2
UMask=0077
NoNewPrivileges=true
CapabilityBoundingSet=CAP_SETUID CAP_SETGID CAP_CHOWN
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
[Install]
WantedBy=multi-user.target
'''



def snapshot():
    if UNIT.is_symlink() or (UNIT.exists() and UNIT.read_text()!=unit()):
        raise ValueError('Refusing an independent CMS resolver unit')
    path=configuration_path()
    if path.is_symlink():raise ValueError('Unexpected CMS resolver configuration')
    return dict(configuration=json.loads(path.read_text()) if path.exists() else None,
                unit=UNIT.read_text() if UNIT.exists() else None,
                running=UNIT.exists() and run('systemctl','show',NAME,'--property=ActiveState','--value')=='active')


def restore(before):
    """Recover an old apply journal; this never creates a new helper setup."""
    if before is None:return
    if before['unit'] is not None and before['unit']!=unit():
        raise ValueError('Legacy CMS resolver snapshot ownership changed')
    current=snapshot()
    # New packages contain no worker. A failed upgrade restores its previous
    # immutable code release before an actually retired old service is started.
    if before['running'] and not current['running'] and not (CODE/'shared/cms_session_server.py').is_file():
        import deployment
        deployment.rollback()
        if not (CODE/'shared/cms_session_server.py').is_file():
            raise RuntimeError('Previous addon code is required to recover its legacy CMS service')
    path=configuration_path()
    if before['configuration'] is None:path.unlink(missing_ok=True)
    else:write_json(path,before['configuration'])
    if before['unit'] is None:
        if UNIT.exists():retire()
    else:
        if not UNIT.exists():write(UNIT,before['unit'],0o644);run('systemctl','daemon-reload')
        if before['running']:run('systemctl','enable','--now',NAME)
        elif current['running']:run('systemctl','stop',NAME)


def retire():
    """Run only after helper-free VCL activation (or native uninstall)."""
    snapshot()  # Ownership checks happen before any resource is changed.
    if UNIT.exists():
        run('systemctl','disable','--now',NAME)
        UNIT.unlink();run('systemctl','daemon-reload')
    configuration_path().unlink(missing_ok=True)
    parent=SOCKET.parent
    if parent.is_symlink():raise ValueError('Unexpected legacy CMS runtime directory')
    if parent.exists():
        if parent.stat().st_uid!=0:
            raise ValueError('Unexpected legacy CMS runtime directory')
        if SOCKET.is_symlink():raise ValueError('Unexpected legacy CMS runtime socket')
        if SOCKET.exists():
            if not stat.S_ISSOCK(SOCKET.stat().st_mode) or SOCKET.stat().st_uid!=0:
                raise ValueError('Unexpected legacy CMS runtime socket')
            SOCKET.unlink()
        try:parent.rmdir()
        except OSError:
            if any(parent.iterdir()):raise ValueError('Unexpected files in legacy CMS runtime directory')
            raise
