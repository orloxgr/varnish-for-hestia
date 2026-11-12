"""Read the complete native Hestia inventory, or fail without changing state."""
import pwd
from pathlib import Path
import subprocess
import progress


def collect(hestia):
    progress.stage('Reading native Hestia accounts and IP addresses')
    users = hestia('v-list-users', 'json')
    addresses = hestia('v-list-sys-ips', 'json')
    def local_ip(value):
        if value in addresses:
            return value
        matched = [key for key, row in addresses.items() if row.get('NAT') == value]
        if len(matched) != 1:
            raise ValueError('The domain has no unambiguous native origin address')
        return matched[0]
    result = {}
    for number, (owner, row) in enumerate(sorted(users.items()), 1):
        progress.stage('Account ' + str(number) + '/' + str(len(users)) + ': ' + owner + ' — reading domains')
        # Directory birth time survives password/package changes but differs for
        # replacement accounts, even if name/UID/creation-second are recycled.
        directory = Path('/usr/local/hestia/data/users') / owner
        birth = subprocess.check_output(['stat','--format=%w','--',str(directory)],text=True).strip()
        if not birth or birth == '-':
            raise ValueError('A stable account creation identity is unavailable')
        identity = str(pwd.getpwnam(owner).pw_uid) + ':' + birth
        domains = hestia('v-list-web-domains', owner, 'json')
        result[owner] = {
            'identity':identity, 'package':row['PACKAGE'], 'role':row['ROLE'],
            'suspended':row['SUSPENDED'] == 'yes',
            'sites':{domain:{'aliases':[s.strip() for s in web.get('ALIAS','').split(',') if s.strip()],
                             'suspended':web.get('SUSPENDED') == 'yes',
                             'origin_ip':local_ip(web['IP']), 'proxy_template':web.get('PROXY',''),
                             'proxy_extensions':web.get('PROXY_EXT','')}
                     for domain, web in domains.items()},
        }
    progress.stage('Inventory complete: ' + str(len(result)) + ' accounts, ' + str(sum(len(row['sites']) for row in result.values())) + ' domains')
    return result
