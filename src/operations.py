"""Serialize addon operations inside a root-owned runtime directory."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat


@contextmanager
def exclusive():
    directory = Path('/run/varnish-for-hestia')
    if directory.is_symlink():
        raise ValueError('Unexpected operation lock directory')
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.stat()
    if info.st_uid != 0 or info.st_mode & 0o077:
        raise ValueError('Operation lock directory must be root-private')
    descriptor = os.open(directory / 'operation.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise ValueError('Unexpected operation lock file')
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
