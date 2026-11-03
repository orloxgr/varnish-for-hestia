"""Addon-owned official APT repository, resumable without changing other sources."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

from files import write, write_json

KEY = Path('/etc/apt/keyrings/varnish-for-hestia.gpg')
SOURCE = Path('/etc/apt/sources.list.d/varnish-for-hestia.list')
RECORD = Path('/var/lib/varnish-for-hestia/repository.json')
KEY_URL = 'https://packages.varnish-software.com/varnish/varnish.pub.asc'
KEY_SHA256 = 'eea1110e5aa0afc0e8cfe872f0f5bbf0778d95e811227e19835c02378dd03ff2'
SOURCE_TEXT = ('# Managed by varnish-for-hestia\n'
               'deb [arch=amd64 signed-by=' + str(KEY) + '] https://packages.varnish-software.com/varnish/ubuntu resolute main\n')


def validate(record):
    if record.get('schema') != 1 or record.get('source') != SOURCE_TEXT or record.get('key_source_sha256') != KEY_SHA256:
        raise ValueError('Unsupported addon repository record')
    key = base64.b64decode(record['key'], validate=True)
    if not key or hashlib.sha256(key).hexdigest() != record['key_sha256']:
        raise ValueError('Damaged addon repository key')
    return key


def current():
    if RECORD.is_symlink():
        raise ValueError('Unexpected repository record path')
    if not RECORD.exists():
        return None
    record = json.loads(RECORD.read_text())
    validate(record)
    return record


def check_paths(record):
    key = validate(record)
    for path, expected in ((KEY, key), (SOURCE, SOURCE_TEXT.encode())):
        if path.is_symlink() or (path.exists() and path.read_bytes() != expected):
            raise ValueError('Refusing an unmanaged or modified addon repository file')


def setup():
    record = current()
    if record is None:
        if KEY.exists() or KEY.is_symlink() or SOURCE.exists() or SOURCE.is_symlink():
            raise ValueError('Refusing unmanaged addon repository paths')
        with urllib.request.urlopen(KEY_URL, timeout=None) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != KEY_SHA256:
            raise ValueError('Official signing key differs from the verified release')
        key = subprocess.run(['gpg', '--dearmor'], input=data, capture_output=True, check=True).stdout
        record = {'schema': 1, 'source': SOURCE_TEXT, 'key': base64.b64encode(key).decode(),
                  'key_sha256': hashlib.sha256(key).hexdigest(), 'key_source_sha256': KEY_SHA256}
        # Record ownership before writing the public files, so interruption after
        # either atomic write is recoverable by the same install command.
        write_json(RECORD, record)
    restore(record)


def restore(record):
    previous = current()
    if previous is not None:
        check_paths(previous)
    if record is None:
        if previous is not None:
            KEY.unlink(missing_ok=True); SOURCE.unlink(missing_ok=True); RECORD.unlink()
        return
    check_paths(record)
    key = validate(record)
    KEY.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    write_json(RECORD, record)
    write(KEY, key, 0o644); write(SOURCE, SOURCE_TEXT, 0o644)


def remove():
    restore(None)
