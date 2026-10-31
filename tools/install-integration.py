#!/usr/bin/python3
"""Atomically install addon-owned code, panel route and root bridge."""
import json
import os
from pathlib import Path
import sys
source=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(source/'src'))
from deployment import publish
meta=json.loads((source/'addon.json').read_text())
if os.geteuid()!=0 or not Path('/usr/local/hestia/web/inc/main.php').is_file():
    raise SystemExit('An administrator root shell and Hestia are required')
for path in (Path('/usr/local/hestia/bin')/meta['command'],):
    if path.is_symlink() or (path.exists() and '# Managed by '+meta['id'] not in path.read_text()):
        raise SystemExit('Refusing unmanaged integration')
publish(source,meta)
print(json.dumps({'addon':meta['id'],'route':'/plugins/'+meta['slug']+'/',
                  'atomic_code_publication':True,'service_configuration_changed':False}))
