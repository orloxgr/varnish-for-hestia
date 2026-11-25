#!/usr/bin/env python3
"""Check tracked content without printing potentially private matched values."""
import argparse
import ipaddress
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PERSONAL_PATH = re.compile(r'(?i)(?:[a-z]:[\\/]+(?:Users|Documents and Settings)[\\/]+[^\\/\s]+|/(?:Users|home)/[a-z0-9_.-]+/)')
GENERIC_HOME = re.compile(r'^/home/(?:admin|user|example|test|siteowner)/$')
IPV4 = re.compile(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])')
PRIVATE_KEY = re.compile(r'-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----')
RESERVED = tuple(ipaddress.ip_network(value) for value in ('127.0.0.0/8', '0.0.0.0/32', '192.0.2.0/24', '198.51.100.0/24', '203.0.113.0/24', '255.255.255.255/32'))
SYNTHETIC_HOME = '/'.join(['', 'home', 'alice', ''])
SYNTHETIC_HOMES = {path: {SYNTHETIC_HOME} for path in (
    'tests/test_aggressive_cache.py', 'tests/test_hosting_policy.py', 'tests/test_native_docroot.py',
)}


def findings(path, text, denied=()):
    for number, line in enumerate(text.splitlines(), 1):
        for match in PERSONAL_PATH.finditer(line):
            if not GENERIC_HOME.fullmatch(match.group()) and match.group() not in SYNTHETIC_HOMES.get(path, ()):
                yield number, 'personal-or-deployed-home-path'
        if PRIVATE_KEY.search(line):
            yield number, 'private-key-material'
        for match in IPV4.finditer(line):
            try:
                address = ipaddress.ip_address(match.group())
            except ValueError:
                continue
            # A browser version in an explicitly named User-Agent is not an IP.
            if line[max(0, match.start() - 7):match.start()] == 'Chrome/':
                continue
            if not any(address in network for network in RESERVED):
                yield number, 'non-documentation-ipv4'
        if any(value.casefold() in line.casefold() for value in denied):
            yield number, 'private-denylist-match'


def private_filename(name):
    path = Path(name)
    lower = path.name.lower()
    return (lower.startswith('.env') and lower not in ('.env.example', '.env.sample')
            or lower.startswith(('id_rsa', 'id_ed25519'))
            or lower.endswith(('.pem', '.key', '.p12', '.pfx', '.sql', '.dump', '.log', '.backup', '.bundle'))
            or '.sql.' in lower
            or any(part.lower() in ('private', 'evidence', 'artifacts') for part in path.parts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--denylist-file', type=Path, help='Optional private UTF-8 file, one customer/host identifier per line; never commit it')
    args = parser.parse_args()
    denied = ()
    if args.denylist_file:
        denied = tuple(line.strip() for line in args.denylist_file.read_text(encoding='utf-8').splitlines() if line.strip() and not line.startswith('#'))
    paths = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z']).decode('utf-8').split('\0')
    count = 0
    for name in filter(None, paths):
        if private_filename(name):
            print(f'{name}: private-artifact-filename (contents withheld)')
            count += 1
        path = ROOT / name
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b'\0' in data:
            continue
        for number, reason in findings(name, data.decode('utf-8', errors='replace'), denied):
            print(f'{name}:{number}: {reason} (value withheld)')
            count += 1
    print(f'Public-tree privacy check: {count} finding(s).')
    return int(count != 0)


if __name__ == '__main__':
    raise SystemExit(main())
