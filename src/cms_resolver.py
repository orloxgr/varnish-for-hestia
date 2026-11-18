"""Addon-owned local authentication service, with Hestia account identities."""
import grp
import hashlib
import json
from pathlib import Path
import pwd
import re
import subprocess
import socket
import stat
import struct
import time
from urllib.parse import unquote

import aggressive
import hosting_timeouts
from files import write, write_json

UNIT=Path('/etc/systemd/system/varnish-for-hestia-cms.service')
NAME='varnish-for-hestia-cms'
SOCKET='/run/varnish-for-hestia-cms/sessions.sock'
CODE=Path('/opt/varnish-for-hestia')


def run(*args):
    result=subprocess.run(list(args),capture_output=True,text=True)
    if result.returncode:raise RuntimeError('CMS session service operation failed')
    return result.stdout.strip()


def selected(state):
    return [(owner,site) for owner,row in state.get('owners',{}).items() for site in row['sites'].values()
            if row['enabled'] and not row['suspended'] and site['enabled'] and not site['suspended'] and
            aggressive.settings(site)['aggressive'] and any(r['cms']=='joomla' for r in site.get('cms_installations',[]))]


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


def frame_bytes(config):
    import service
    value=service.admin(config,'param.show','http_req_size').stdout.decode()
    match=re.search(r'Value is:\s*([0-9]+(?:[.][0-9]+)?)([kmg]?)\s*\[bytes\]',value,re.I)
    if not match:raise ValueError('Native HTTP request allowance is unavailable')
    return int(float(match[1])*{'':1,'k':1024,'m':1024**2,'g':1024**3}[match[2].lower()])*6+128


def configuration(state,config):
    daemon=pwd.getpwnam('varnish')
    sites={}
    for owner,site in selected(state):
        identity=pwd.getpwnam(owner)
        root=Path(site['cms_document_root'])
        if identity.pw_uid==0 or not root.is_absolute() or '..' in root.parts:raise ValueError('Invalid CMS hosting identity')
        roots=[dict(cms='joomla',base=row['base'],root=str(root/unquote(row['base']).lstrip('/')))
               for row in site['cms_installations'] if row['cms']=='joomla']
        sites[site['id']]=dict(uid=identity.pw_uid,gid=identity.pw_gid,home=identity.pw_dir,installations=roots)
        origin=dict(type='tcp',address=site.get('origin_ip',config.get('origin_ip','127.0.0.1')),port=config.get('origin_port',8080))
        sites[site['id']].update(names=[site.get('domain',next(domain for domain,row in state['owners'][owner]['sites'].items() if row is site)),*site.get('aliases',[])],
                                origins={'http':origin,'https':dict(origin)})
    shared=Path(__file__).resolve().parents[1]/'shared'
    source_identity=hashlib.sha256(b''.join((shared/name).read_bytes() for name in
        ('cms_sessions.py','cms_session_server.py','cms_metadata.py','cms_discovery.py','cms_routes.py'))).hexdigest()
    allowances=state.get('hosting_timeouts',{})
    token_timeout=hosting_timeouts.frontend(state)['read']/1000 if all(key in allowances for key in ('connect','read','send')) else allowances.get('connect',60000)/1000
    return dict(schema=1,socket=SOCKET,allowed_uids=[daemon.pw_uid],socket_gid=grp.getgrnam('varnish').gr_gid,
                max_frame_bytes=frame_bytes(config),query_timeout=state.get('hosting_timeouts',{}).get('connect',60000)/1000 or None,
                token_timeout=token_timeout or None,
                sites=sites,source_identity=source_identity)


def prepare(state,config):
    if not selected(state):return
    before=snapshot(); following=configuration(state,config)
    write_json(configuration_path(),following)
    if before['unit'] is None:
        write(UNIT,unit(),0o644);run('systemctl','daemon-reload')
    if before['running'] and before['configuration'] and before['configuration'].get('source_identity')!=following['source_identity']:
        run('systemctl','restart',NAME)
    else:run('systemctl','enable','--now',NAME)
    wait(following)


def wait(config):
    duration=config.get('query_timeout')
    deadline=time.monotonic()+duration if duration is not None else None
    while True:
        try:
            info=Path(config['socket']).lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=0 or info.st_gid!=config['socket_gid']:
                raise ValueError('Unexpected CMS resolver socket ownership')
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
                connection.settimeout(max(.001,deadline-time.monotonic()) if deadline is not None else None)
                connection.connect(config['socket'])
                _,uid,_=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                if uid!=0:raise ValueError('Unexpected CMS resolver peer identity')
                return
        except (FileNotFoundError,ConnectionRefusedError,socket.timeout):
            if deadline is not None and time.monotonic()>=deadline:
                raise RuntimeError('CMS session resolver did not become ready') from None
            time.sleep(.05)


def restore(before):
    if before is None:return
    path=configuration_path()
    if before['configuration'] is None:path.unlink(missing_ok=True)
    else:write_json(path,before['configuration'])
    if before['unit'] is None:
        if UNIT.exists():
            if UNIT.read_text()!=unit():raise ValueError('CMS resolver unit ownership changed')
            run('systemctl','disable','--now',NAME);UNIT.unlink();run('systemctl','daemon-reload')
    else:
        if not UNIT.exists():write(UNIT,before['unit'],0o644);run('systemctl','daemon-reload')
        run('systemctl','enable','--now',NAME) if before['running'] else run('systemctl','stop',NAME)


def finish(state):
    if selected(state) or not UNIT.exists():return
    if UNIT.is_symlink() or UNIT.read_text()!=unit():raise ValueError('CMS resolver unit ownership changed')
    run('systemctl','disable','--now',NAME)
    configuration_path().unlink(missing_ok=True)
    UNIT.unlink();run('systemctl','daemon-reload')
