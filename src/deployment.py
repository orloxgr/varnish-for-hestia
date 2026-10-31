"""Publish complete addon code generations with one atomic pointer change."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
from files import write, write_json, sync_directory, ensure_owned_directory

ID = json.loads((Path(__file__).resolve().parents[1]/'addon.json').read_text())['id']
HESTIA = Path('/usr/local/hestia')
TARGET = Path('/opt')/ID
RELEASES = Path('/opt')/(ID+'.releases')
PENDING = Path('/var/lib')/ID/'code-update.json'


def check():
    check_menu()
    if TARGET.is_symlink():
        real=TARGET.resolve()
        if real.parent != RELEASES or RELEASES.is_symlink() or not real.is_dir():
            raise ValueError('Unexpected installed code pointer')
        marker=real/'.addon-owner'
    elif TARGET.exists():
        if not TARGET.is_dir():
            raise ValueError('Unexpected code path')
        marker=TARGET/'.addon-owner'
    else:
        return
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_uid != 0 or marker.read_text().strip()!=ID:
        raise ValueError('Refusing unmanaged installed code')


def switch(release):
    temporary=TARGET.with_name('.'+ID+'.link-'+secrets.token_hex(6))
    temporary.symlink_to(release, target_is_directory=True)
    previous=None
    try:
        if TARGET.is_symlink():
            previous=str(TARGET.resolve());os.replace(temporary,TARGET)
        elif TARGET.exists():
            # Atomic exchange permits a directory and symlink to trade names.
            # Existing requests always see one complete generation.
            previous=str(RELEASES/('legacy-'+secrets.token_hex(6)))
            libc=ctypes.CDLL(None,use_errno=True)
            if libc.renameat2(-100,os.fsencode(temporary),-100,os.fsencode(TARGET),2):
                error=ctypes.get_errno();raise OSError(error,os.strerror(error))
            os.replace(temporary,previous);sync_directory(RELEASES)
        else:
            os.replace(temporary,TARGET)
        sync_directory(TARGET.parent)
        return previous
    finally:
        if temporary.is_symlink():temporary.unlink()


def check_panel(path):
    result = subprocess.run([str(HESTIA/'php/bin/php'), '-l', str(path)],
                            capture_output=True, timeout=20)
    if result.returncode:
        details = b'\n'.join(output for output in (result.stdout, result.stderr) if output).decode(errors='replace').strip()
        raise RuntimeError('Panel PHP syntax check failed (exit ' + str(result.returncode) + '): ' +
                           str(path) + '\n' + details)


def menu_path():
    return HESTIA/'web/js/custom_scripts'/(ID+'.js')


def check_menu():
    path = menu_path()
    if path.is_symlink() or path.parent.resolve() != path.parent:
        raise ValueError('Unexpected addon menu script path')
    if path.exists() and (not path.is_file() or not path.read_text().startswith('// Managed by '+ID+'\n')):
        raise ValueError('Refusing an unmanaged menu script')


def shared_directory(path):
    try:
        path.mkdir(mode=0o755)
    except FileExistsError:
        pass
    else:
        path.chmod(0o755)


def sync_menu(release):
    check_menu()
    asset = release/'panel/menu.js'
    if asset.is_file():
        shared_directory(menu_path().parent)
        write(menu_path(),asset.read_bytes(),0o644)
    else:
        menu_path().unlink(missing_ok=True)



def publish(source,meta):
    check()
    ensure_owned_directory(RELEASES,ID); RELEASES.chmod(0o755)
    stage=Path(tempfile.mkdtemp(prefix='release-',dir=RELEASES))
    stage.chmod(0o755)
    try:
        for name in ('src','panel','profiles','templates','tools'):
            if (source/name).is_dir():
                shutil.copytree(source/name,stage/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        shutil.copyfile(source/'addon.json',stage/'addon.json')
        page=(stage/'panel/index.php').read_text().replace('__INSTALL_ROOT__',str(TARGET))
        (stage/'panel/index.php').write_text(page)
        write(stage/'.addon-owner',ID+'\n',0o644)
        check_panel(stage/'panel/index.php')
        for directory,_,files in os.walk(stage):
            os.chmod(directory,0o755)
            for name in files:
                path=Path(directory)/name;path.chmod(0o644)
                with path.open('rb') as stream:os.fsync(stream.fileno())
            sync_directory(directory)
        sync_directory(RELEASES)
        # A pointer journal is useful for an ordinary failed upgrade. Interrupted
        # publication itself is complete and the same installer can roll forward.
        PENDING.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        if not PENDING.exists():
            old=str(TARGET.resolve()) if TARGET.is_symlink() else None
            # Reserve the legacy destination before exchange for durable undo.
            if TARGET.exists() and not TARGET.is_symlink():
                old=str(RELEASES/('legacy-'+secrets.token_hex(6)))
                shutil.copytree(TARGET,old,ignore=shutil.ignore_patterns('__pycache__'))
                for directory,_,files in os.walk(old):
                    for name in files:
                        with (Path(directory)/name).open('rb') as stream:os.fsync(stream.fileno())
                    sync_directory(directory)
                sync_directory(RELEASES)
            write_json(PENDING,{'schema':1,'previous':old,'legacy':TARGET.exists() and not TARGET.is_symlink()})
        record=json.loads(PENDING.read_text())
        if TARGET.exists() and not TARGET.is_symlink():
            # Keep the predeclared legacy destination stable across a crash.
            temporary=TARGET.with_name('.'+ID+'.link-'+secrets.token_hex(6))
            temporary.symlink_to(stage,target_is_directory=True)
            libc=ctypes.CDLL(None,use_errno=True)
            if libc.renameat2(-100,os.fsencode(temporary),-100,os.fsencode(TARGET),2):
                error=ctypes.get_errno();temporary.unlink();raise OSError(error,os.strerror(error))
            shutil.rmtree(temporary);sync_directory(TARGET.parent)
        else:
            switch(stage)
        route=HESTIA/'web/plugins'/meta['slug']
        shared_directory(route.parent)
        ensure_owned_directory(route,ID);route.chmod(0o755)
        write(route/'index.php',page,0o644)
        command=HESTIA/'bin'/meta['command']
        write(command,'#!/bin/sh\n# Managed by '+ID+'\nexec /usr/bin/python3 -I '+str(TARGET/'src/addon.py')+' "$@"\n',0o755)
        sync_menu(stage)
    except Exception:
        if not TARGET.is_symlink() or TARGET.resolve()!=stage:
            shutil.rmtree(stage)
        raise


def commit():
    PENDING.unlink(missing_ok=True)
    if PENDING.parent.exists():sync_directory(PENDING.parent)


def rollback():
    if not PENDING.exists():return
    record=json.loads(PENDING.read_text());previous=record['previous']
    if previous is not None and Path(previous).is_dir():
        switch(previous)
        meta=json.loads((TARGET/'addon.json').read_text())
        page=(TARGET/'panel/index.php').read_text().replace('__INSTALL_ROOT__',str(TARGET))
        write(HESTIA/'web/plugins'/meta['slug']/'index.php',page,0o644)
        sync_menu(TARGET)
    commit()


def remove():
    check()
    menu_path().unlink(missing_ok=True)
    if TARGET.is_symlink():
        TARGET.unlink();sync_directory(TARGET.parent)
    elif TARGET.exists():
        shutil.rmtree(TARGET)
    if RELEASES.exists():
        marker=RELEASES/'.addon-owner'
        if RELEASES.is_symlink() or not marker.is_file() or marker.read_text().strip()!=ID:
            raise ValueError('Refusing unmanaged code releases')
        shutil.rmtree(RELEASES);sync_directory(RELEASES.parent)
