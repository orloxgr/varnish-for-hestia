"""Atomic writes for addon-owned configuration and private state."""
import json
import os
from pathlib import Path
import tempfile


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def rename_without_replacement(source, destination):
    """Linux renameat2: publish a complete directory without replacing any target."""
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def ensure_owned_directory(path, identity):
    """Atomically create the directory and its marker; caller holds the addon lock.

    Before the first journal exists, a crash must not leave an unmarked final
    directory. Staging contains only a marker (never credentials or user data).
    Interrupted empty/partly written marker stages can therefore be removed on
    retry without touching any pre-existing unmanaged target or unfamiliar data.
    """
    import re
    import stat
    path = Path(path)
    if (not path.is_absolute() or path.parent.resolve() != path.parent or path.is_symlink() or
            not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,99}', identity)):
        raise ValueError('Unexpected owned configuration directory')
    marker_name = '.addon-owner'; expected = (identity + '\n').encode()
    if path.exists():
        marker = path / marker_name
        if (not path.is_dir() or path.stat().st_uid != 0 or marker.is_symlink() or not marker.is_file() or
                marker.stat().st_uid != 0 or marker.stat().st_size != len(expected) or marker.read_bytes() != expected):
            raise ValueError('Refusing an unmanaged configuration directory')

    prefix = '.' + path.name + '.bootstrap-'
    def discard_stage(stage):
        if stage.is_symlink() or not stage.is_dir() or stage.resolve().parent != path.parent:
            return
        info = stage.stat()
        if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
            return
        children = list(stage.iterdir())
        if children:
            marker = stage / marker_name
            if (children != [marker] or marker.is_symlink() or not marker.is_file() or marker.stat().st_uid != 0 or
                    marker.stat().st_size > len(expected) or not expected.startswith(marker.read_bytes())):
                return
            marker.unlink()
        stage.rmdir()

    for stage in path.parent.glob(prefix + '*'):
        discard_stage(stage)
    if path.exists():
        sync_directory(path.parent)
        return
    stage = Path(tempfile.mkdtemp(prefix=prefix, dir=path.parent))
    try:
        descriptor = os.open(stage / marker_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(expected); stream.flush(); os.fsync(stream.fileno())
        sync_directory(stage)
        rename_without_replacement(stage, path)
        sync_directory(path.parent)
    finally:
        discard_stage(stage)


def write(path, data, mode=0o600, gid=0):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refusing a symlink configuration target')
    descriptor, candidate = tempfile.mkstemp(prefix='.'+path.name+'-', dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        os.fchown(descriptor, 0, gid)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data.encode() if isinstance(data, str) else data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(candidate, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(candidate):
            os.unlink(candidate)


def write_json(path, data):
    write(path, json.dumps(data, sort_keys=True, indent=2)+'\n')
