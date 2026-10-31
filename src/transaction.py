"""Durable undo records for addon configuration changes (no application data)."""
import base64
import json
import os
from pathlib import Path
from files import write, write_json, sync_directory


def begin(store, paths, extra=None, filename='apply.json'):
    record = store / filename
    if record.exists():
        raise RuntimeError('Recover the pending configuration operation first')
    before = []
    for path in paths:
        if path.is_symlink():
            raise ValueError('Unexpected transaction file')
        info = path.stat() if path.exists() else None
        before.append({'path': str(path), 'data': base64.b64encode(path.read_bytes()).decode() if info else None,
                       'mode': info.st_mode & 0o777 if info else 0o600, 'gid': info.st_gid if info else 0})
    write_json(record, {'schema': 1, 'before': before, 'extra': extra or {}})


def read(store, allowed, filename='apply.json'):
    path = store / filename
    if not path.exists():
        return None
    info = path.stat()
    if path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o077:
        raise ValueError('Unexpected configuration transaction')
    record = json.loads(path.read_text())
    if record.get('schema') != 1 or {row['path'] for row in record['before']} != {str(p) for p in allowed}:
        raise ValueError('Unrecognized configuration transaction')
    return record


def restore_files(record):
    for row in record['before']:
        path = Path(row['path'])
        if row['data'] is None:
            path.unlink(missing_ok=True); sync_directory(path.parent)
        else:
            write(path, base64.b64decode(row['data'], validate=True), row['mode'], row['gid'])


def finish(store, filename='apply.json'):
    (store / filename).unlink(missing_ok=True)
    sync_directory(store)
