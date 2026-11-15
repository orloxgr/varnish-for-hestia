"""Hestia adapter for the unchanged, panel-independent HTTP parity runner."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from vcl import render

parser = argparse.ArgumentParser()
parser.add_argument('--profile', required=True, choices=('basic', 'ultracache'))
args = parser.parse_args()
sites = {}
for domain, identity, token in [('example.test', 'a', 'b'), ('other.test', 'c', 'd')]:
    sites[domain] = dict(id=identity * 32, aliases=[], profile=args.profile, token=token * 64,
                         enabled=True, suspended=False, custom_recv='', custom_backend_response='')
state = {'owners': {'alice': dict(enabled=True, suspended=False, package='default', sites=sites)}}
source = render(state, {'origin_ip': '127.0.0.1', 'origin_port': 8080})
source = source.replace('"8080"', '"${s1_port}"', 1)
print(json.dumps(dict(vcl=source, get_headers={}, purge_headers={'X-UltraCache-Token': 'b' * 64})))
