"""Use native Hestia commands to select additional proxy templates."""
import ipaddress
import hashlib
from pathlib import Path
import re
import subprocess
import time

from files import write

NAME = 'hvh-varnish'
TEMPLATES = Path('/usr/local/hestia/data/templates/web/nginx')
APACHE = Path('/etc/apache2/conf.d/varnish-for-hestia.inc')
MARKER = '# Managed by varnish-for-hestia'


def run(*args):
    result = subprocess.run(args, capture_output=True, timeout=None)
    if result.returncode:
        raise RuntimeError('Native web configuration operation failed')


def nginx_workers(master):
    result = set()
    try:
        children = Path('/proc/' + master + '/task/' + master + '/children').read_text().split()
    except FileNotFoundError:
        return result
    for child in children:
        try:
            command = Path('/proc/' + child + '/cmdline').read_bytes()
        except FileNotFoundError:
            continue
        if b'nginx: worker process' in command and b'shutting down' not in command:
            result.add(child)
    return result


def reload_nginx():
    # ExecReload acknowledges SIGHUP before workers take the new vhosts. Wait
    # on native worker turnover, without making any application HTTP requests.
    master = subprocess.check_output(['systemctl', 'show', 'nginx', '-p', 'MainPID', '--value'], text=True).strip()
    before = nginx_workers(master)
    run('systemctl', 'reload', 'nginx')
    while True:
        current = nginx_workers(master)
        if current and not current.intersection(before):
            return
        state = subprocess.check_output(['systemctl', 'is-active', 'nginx'], text=True).strip()
        if state not in ('active', 'reloading', 'activating'):
            raise RuntimeError('Nginx stopped during configuration reload')
        time.sleep(.025)


def allowed(owner, config):
    return (owner['enabled'] and not owner['suspended'] and
            owner['package'] not in config.get('denied_packages', []) and
            (config.get('allowed_packages') is None or owner['package'] in config['allowed_packages']))


def enabled(owner, site, config):
    return allowed(owner, config) and site['enabled'] and not site['suspended']


def owned_template(name):
    if not re.fullmatch(r'hvh-varnish(?:-[0-9a-f]{12})?', name):
        return False
    return all((TEMPLATES / (name + '.' + ext)).is_file() and
               MARKER in (TEMPLATES / (name + '.' + ext)).read_text() for ext in ('tpl', 'stpl'))


def set_template(owner, domain, template, extensions):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', template):
        raise ValueError('Invalid stored proxy template')
    # Native CLI refuses suspended users/domains. Use the same native rendering
    # functions in that case, preserving SUSPENDED throughout. This also permits
    # uninstall/rollback without briefly enabling a suspended hosting account.
    script = r'''user=$1; domain=$2; template=$3; extensions=$4; restart=no
source /etc/hestiacp/hestia.conf
source "$HESTIA/func/main.sh"
source "$HESTIA/func/domain.sh"
source "$HESTIA/func/ip.sh"
source_conf "$HESTIA/conf/hestia.conf"
is_format_valid user domain template extensions restart
is_object_valid user USER "$user"
is_object_valid web DOMAIN "$domain"
is_proxy_template_valid "$template"
check_hestia_demo_mode
get_domain_values web
owner_suspended=$(get_object_value user USER "$user" '$SUSPENDED')
if [ "$SUSPENDED" != yes ] && [ "$owner_suspended" != yes ]; then
    exec "$BIN/v-change-web-domain-proxy-tpl" "$user" "$domain" "$template" "$extensions" no
fi
local_ip=$(get_real_ip "$IP")
del_web_config "$PROXY_SYSTEM" "$PROXY.tpl"
if [ "$SSL" = yes ]; then del_web_config "$PROXY_SYSTEM" "$PROXY.stpl"; fi
PROXY=$template; PROXY_EXT=$extensions
prepare_web_domain_values
add_web_config "$PROXY_SYSTEM" "$PROXY.tpl"
if [ "$SSL" = yes ]; then add_web_config "$PROXY_SYSTEM" "$PROXY.stpl"; fi
update_object_value web DOMAIN "$domain" '$PROXY' "$template"
update_object_value web DOMAIN "$domain" '$PROXY_EXT' "$extensions"
check_result $? 'Proxy template update failed'
'''
    result = subprocess.run(['/bin/bash', '-c', script, 'hvh-template', owner, domain, template, extensions],
                            capture_output=True, timeout=None)
    if result.returncode:
        raise RuntimeError('Native web configuration operation failed')


def plan(state, inventory, config):
    changes = []
    selected = config.get('template_name', NAME)
    if not owned_template(selected):
        raise ValueError('The configured addon template version is unavailable')
    revision = hashlib.sha256(b''.join((TEMPLATES / (selected + '.' + ext)).read_bytes() for ext in ('tpl', 'stpl'))).hexdigest()
    for owner_name, owner in state['owners'].items():
        for domain, site in owner['sites'].items():
            observed = inventory[owner_name]['sites'][domain]
            site['origin_ip'] = str(ipaddress.ip_address(observed['origin_ip']))
            current = observed['proxy_template']
            saved = site['settings']
            # A selection made directly in Hestia is a real owner choice. A
            # native rebuild retains our template and does not look like opt-out.
            if saved.get('routing_active') and not owned_template(current) and not owner['suspended'] and not site['suspended']:
                site['enabled'] = False
                saved['original_template'] = current
            if 'original_template' not in saved or (not saved['original_template'] and current):
                saved['original_template'] = current if not owned_template(current) else 'default'
            saved['proxy_extensions'] = observed['proxy_extensions']
            if not current:
                # Native no-proxy domains stay in their original web topology.
                saved['routing_active'] = False
                continue
            target = selected if enabled(owner, site, config) else saved['original_template']
            if not owner['suspended'] and not site['suspended'] and (current != target or
                    (target == selected and saved.get('template_revision') != revision)):
                changes.append((owner_name, domain, current, target, observed['proxy_extensions']))
            saved['routing_active'] = target == selected
            saved['template_revision'] = revision
    return changes


def apache_config(inventory, port):
    addresses = {'127.0.0.1', '::1'}
    addresses.update(str(ipaddress.ip_address(site['origin_ip'])) for owner in inventory.values() for site in owner['sites'].values())
    trusted = ' || '.join("%{CONN_REMOTE_ADDR} == '" + ip + "'" for ip in sorted(addresses))
    expression = "req('X-Forwarded-Proto') == 'https' && (" + trusted + ')'
    return (MARKER + '\n# Restore HTTPS metadata only for native local proxy connections.\n'
            '<IfModule proxy_fcgi_module>\n    ProxyFCGISetEnvIf "' + expression + '" HTTPS on\n</IfModule>\n')


def install_templates(source, config=None):
    data = {ext: (source / 'templates' / (NAME + '.' + ext)).read_bytes() for ext in ('tpl', 'stpl')}
    listen = (config or {}).get('listen_port', 6081)
    if type(listen) is not int or not 1 <= listen <= 65535:
        raise ValueError('Invalid native Varnish TCP port')
    data = {ext: text.replace(b'127.0.0.1:6081', ('127.0.0.1:' + str(listen)).encode()) for ext, text in data.items()}
    selected = NAME + '-' + hashlib.sha256(b''.join(data.values())).hexdigest()[:12]
    for extension in ('tpl', 'stpl'):
        destination = TEMPLATES / (selected + '.' + extension)
        if destination.is_symlink() or (destination.exists() and MARKER not in destination.read_text()):
            raise ValueError('Refusing an unmanaged template path')
        if destination.exists():
            if destination.read_bytes() != data[extension]:
                raise ValueError('An installed immutable template version was modified')
        else:
            write(destination, data[extension], 0o644)
    return selected


def apply(changes, apache_text):
    before = APACHE.read_bytes() if APACHE.exists() else None
    if APACHE.is_symlink() or (before is not None and MARKER.encode() not in before):
        raise ValueError('Refusing an unmanaged Apache extension')
    done = []
    changed_apache = before != apache_text.encode()
    try:
        if changed_apache:
            APACHE.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            write(APACHE, apache_text, 0o644)
        for owner, domain, previous, target, extensions in changes:
            # Include the current entry before the native operation: it can
            # partially regenerate config before reporting a failure.
            done.append((owner, domain, previous, target, extensions))
            set_template(owner, domain, target, extensions)
        if changed_apache or changes:
            run('apache2ctl', 'configtest'); run('nginx', '-t')
            if changed_apache:
                run('systemctl', 'reload', 'apache2')
            if changes:
                reload_nginx()
    except Exception:
        rollback(done, before)
        raise
    return {'route_updates': len(changes), 'apache_updated': changed_apache}, (done, before)


def rollback(changes, apache_before):
    for owner, domain, previous, target, extensions in reversed(changes):
        available = subprocess.run(['/usr/local/hestia/bin/v-list-web-domain', owner, domain, 'json'], capture_output=True, timeout=None)
        if available.returncode:
            # Native concurrent deletion is authoritative; never recreate it.
            continue
        set_template(owner, domain, previous, extensions)
    if apache_before is None:
        APACHE.unlink(missing_ok=True)
    else:
        write(APACHE, apache_before, 0o644)
    run('apache2ctl', 'configtest'); run('nginx', '-t')
    run('systemctl', 'reload', 'apache2'); reload_nginx()
