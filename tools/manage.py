#!/usr/bin/python3
"""Root maintenance from a retained checkout, including restore after removal."""
import argparse
import json
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / 'src'))
from addon import hestia
from maintenance import backup, restore, uninstall, root_only
from operations import exclusive

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('operation', choices=['backup', 'restore', 'uninstall'])
parser.add_argument('file', help='Absolute archive path in a root-owned mode-700 directory')
args = parser.parse_args()
try:
    root_only()
    with exclusive():
        if args.operation == 'restore':
            result = restore(args.file, hestia, SOURCE)
        elif args.operation == 'uninstall':
            result = uninstall(args.file, hestia)
        else:
            result = backup(args.file)
    print(json.dumps(result))
except Exception as error:
    print(json.dumps({'ok': False, 'error_type': type(error).__name__,
                      'error': str(error) if isinstance(error, (ValueError, RuntimeError))
                      else 'Maintenance failed; recovery archive is retained'}))
    raise SystemExit(1)
