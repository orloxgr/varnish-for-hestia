"""Native Hestia document roots, unprivileged CMS discovery and route metadata.

Explicit install/refresh/save scopes only. A normal panel GET never recursively
walks customer files or opens their database. Last valid routes survive errors.
"""
import datetime
import json
from pathlib import Path
import pwd
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
WORKER = Path('/opt/varnish-for-hestia/src/cms_inventory.py')
sys.path.insert(0, str(ROOT / 'shared'))
sys.path.insert(0, str(ROOT / 'src'))
import cms_discovery
import cms_metadata
import cms_routes
import cms_cookies
from inventory import document_root


def query(connection, statement, timeout):
    if not statement.startswith('SELECT ') or __import__('os').geteuid() == 0:
        raise ValueError('CMS metadata requires an unprivileged SELECT')
    command = ['/usr/bin/mysql', '--no-defaults', '--batch', '--raw', '--skip-column-names',
               '--default-character-set=utf8mb4', '--host='+connection['host'],
               '--user='+connection['user'], '--database='+connection['database']]
    if connection.get('port') is not None:command.append('--port='+str(connection['port']))
    if connection.get('socket'):command.append('--socket='+connection['socket'])
    result = subprocess.run(command, input='START TRANSACTION READ ONLY; '+statement+'; ROLLBACK;',
                            capture_output=True, text=True, timeout=timeout,
                            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','MYSQL_PWD':connection['password']})
    if result.returncode:raise cms_metadata.MetadataUnavailable('Configured route metadata unavailable')
    return [json.loads(line) for line in result.stdout.splitlines() if line]


def discover(payload):
    root=Path(payload['root'])
    if root.is_symlink() or not root.is_dir():raise ValueError('Native CMS document root is unavailable')
    # Do not report an unreadable root as a successful empty installation list.
    with __import__('os').scandir(root):pass
    records = cms_discovery.discover(payload['root'], payload.get('excluded_directories', []))
    notices=[]
    cookies=[]
    for index, record in enumerate(records):
        if record['cms'] not in ('wordpress','joomla','prestashop'):continue
        root=Path(payload['root'])/unquote(record['base']).lstrip('/')
        if record['cms']=='joomla':
            try:cookies.append(dict(cms='joomla',base=record['base'],cookie_name=cms_cookies.joomla_name(root),supported=True))
            except (OSError,ValueError):
                cookies.append(dict(cms='joomla',base=record['base'],supported=False))
                notices.append('joomla at '+record['base']+': Static Joomla cookie recognition is unavailable.')
        try:
            connection=cms_metadata.connection(record['cms'],root)
            records[index]=cms_metadata.aliases(record,lambda sql:query(connection,sql,payload.get('timeout')),
                                                 connection['prefix'],payload['hosts'])
        except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
            notices.append(record['cms']+' at '+record['base']+': Configured route metadata unavailable; standard CMS routes remain active.')
    return dict(installations=records,notices=notices,cookies=cookies)


def refresh(state, inventory, hestia, scope):
    for owner, row in state['owners'].items():
        for domain, site in row['sites'].items():
            if scope != 'all' and (owner,domain) not in (scope or []):continue
            checked=datetime.datetime.now(datetime.timezone.utc).isoformat()
            excluded = cms_discovery.exclusions(site.get('cms_excluded_directories', []))
            # Explicit exclusions also retire retained metadata if this refresh
            # fails. They must never be restored by the last-valid alias merge.
            for field in ('cms_installations', 'cms_cookies'):
                if field in site:
                    site[field] = [r for r in site[field] if not cms_discovery.excluded(r['base'], excluded)]
            try:
                account=pwd.getpwnam(owner)
                if account.pw_uid == 0 or not row['identity'].startswith(str(account.pw_uid)+':'):
                    raise ValueError('Hosting identity changed')
                root=document_root(hestia,owner,domain,inventory[owner]['sites'][domain])
                payload=dict(root=root,hosts=[domain,*site['aliases']],excluded_directories=excluded,
                             timeout=state.get('hosting_timeouts',{}).get('connect',60000)/1000 or None)
                process=subprocess.run([sys.executable,'-I','-B',str(WORKER),'--worker'],
                                        input=json.dumps(payload),capture_output=True,text=True,cwd='/',
                                        user=account.pw_uid,group=account.pw_gid,extra_groups=[],umask=0o077,
                                        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':account.pw_dir})
                if process.returncode:raise ValueError('CMS discovery failed')
                result=json.loads(process.stdout)
                records=[r for r in cms_routes.normalize(result['installations']) if not cms_discovery.excluded(r['base'], excluded)]
                # A metadata failure must not discard previously known aliases.
                if result['notices']:
                    previous={(r['cms'],r['base']):r for r in site.get('cms_installations',[])}
                    for record in records:
                        old=previous.get((record['cms'],record['base']))
                        if old:
                            record['private_paths']=sorted(set(record['private_paths']+old['private_paths']))
                            record['private_queries']=[*old.get('private_queries',[]),*record['private_queries']]
                site['cms_installations']=cms_routes.normalize(records)
                site['cms_cookies']=[r for r in result['cookies'] if not cms_discovery.excluded(r['base'], excluded)]
                site.pop('cms_sessions',None)
                site['cms_document_root']=root
                site.pop('cms_pending_root',None)
                site['cms_discovery']={'checked_utc':checked,'status':'partial' if result['notices'] else 'complete',
                                       'error':' '.join(result['notices']) or None}
            except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
                site['cms_discovery']={'checked_utc':checked,'status':'unavailable',
                                       'error':('The native document root changed and CMS discovery failed. Shared cache is paused for this website until Refresh CMS detection succeeds.' if site.get('cms_pending_root') else
                                                'CMS discovery unavailable. Last known CMS routes are retained; refresh CMS detection after checking the native document root and hosting account.')}


def changed_roots(state,inventory):
    """Native topology changes warrant one scan; panel reads otherwise reuse it."""
    changed=set()
    for owner,row in state['owners'].items():
        for domain,site in row['sites'].items():
            actual=inventory[owner]['sites'][domain].get('document_root')
            old=site.get('cms_document_root')
            if not actual or not old:continue
            # Native lists may retain a trailing slash; refresh stores Path's
            # normalized spelling. Compare the same representation both ways.
            actual=str(Path(actual))
            if actual==str(Path(old)):
                site.pop('cms_pending_root',None)
            elif not site.get('cms_pending_root') or str(Path(site['cms_pending_root']))!=actual:
                site['cms_pending_root']=actual
                changed.add((owner,domain))
    return changed


if __name__ == '__main__':
    if sys.argv[1:] != ['--worker'] or __import__('os').geteuid()==0:raise SystemExit(1)
    try:print(json.dumps(discover(json.load(sys.stdin))))
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):raise SystemExit(1)
