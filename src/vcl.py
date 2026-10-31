"""Render shared Varnish policy with immutable site/host/backend boundaries."""
import ipaddress
from pathlib import Path
import re

from fragments import validate

PROFILES = ('general', 'wordpress', 'woocommerce', 'ultracache')
ROOT = Path(__file__).resolve().parents[1]


def quoted(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def host_name(value):
    if not isinstance(value, str) or len(value) > 253:
        raise ValueError('Invalid site hostname')
    plain = value[2:] if value.startswith('*.') else value
    if not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', part) for part in plain.split('.')):
        raise ValueError('Invalid site hostname')
    return value


def render(state, config):
    address = str(ipaddress.ip_address(config['origin_ip']))
    port = config.get('origin_port', 8080)
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('Invalid Apache origin port')
    sites, names, identities = [], set(), set()
    backends = {address: 'hvh_origin'}
    for _, owner in sorted(state['owners'].items()):
        allowed = (owner['enabled'] and not owner['suspended'] and
                   owner['package'] not in config.get('denied_packages', []) and
                   (config.get('allowed_packages') is None or owner['package'] in config['allowed_packages']))
        for domain, site in sorted(owner['sites'].items()):
            sid = site['id']
            if not re.fullmatch(r'[0-9a-f]{32}', sid) or sid in identities:
                raise ValueError('Invalid or duplicate site scope')
            identities.add(sid)
            if site['profile'] not in PROFILES or not re.fullmatch(r'[A-Za-z0-9_-]{12,256}', site['token']):
                raise ValueError('Invalid Varnish profile or purge token')
            hosts = [host_name(domain), *(host_name(a) for a in site['aliases'])]
            if names.intersection(hosts) or len(hosts) != len(set(hosts)):
                raise ValueError('A hostname cannot belong to more than one site')
            names.update(hosts)
            origin = str(ipaddress.ip_address(site.get('origin_ip', address)))
            if origin not in backends:
                backends[origin] = 'hvh_origin_' + str(len(backends))
            sites.append(dict(site, backend=backends[origin], active=allowed and site['enabled'] and not site['suspended'],
                              hosts=hosts, recv=validate(site['custom_recv'], 'recv'),
                              response=validate(site['custom_backend_response'], 'backend_response')))
    text = ['vcl 4.1;', 'import std;', 'acl hvh_local { "127.0.0.1"; "::1"; }',
            '\n'.join('backend ' + name + ' { .host = ' + quoted(ip) + '; .port = ' + quoted(str(port)) + '; }'
                      for ip, name in backends.items())]
    dispatch = []
    # Exact hostnames take priority over wildcard aliases, independently of
    # registry iteration order. A wildcard belongs to exactly one site scope.
    routes = [(site, h) for site in sites for h in site['hosts']]
    routes.sort(key=lambda route: (route[1].startswith('*.'), -len(route[1]), route[1]))
    for site, host in routes:
            condition = ('req.http.host ~ ' + quoted('^([a-z0-9-]+[.])+' + re.escape(host[2:]).replace(r'\.', '[.]') + '$')
                         if host.startswith('*.') else 'req.http.host == ' + quoted(host))
            dispatch.append(('if' if not dispatch else 'else if') + ' (' + condition + ') {\n' +
                            'set req.http.X-HVH-Site = ' + quoted(site['id']) + ';\n' +
                            'set req.http.X-HVH-Profile = ' + quoted(site['profile']) + ';\n' +
                            'set req.backend_hint = ' + site['backend'] + ';\n' +
                            ('set req.http.X-HVH-Disabled = "1";\n' if not site['active'] else '') + '}')
    dispatch.append(('else ' if dispatch else '') + '{ return (synth(421, "Unknown cache host")); }')
    purge = []
    custom_recv, custom_response = [], []
    for site in sites:
        condition = 'if (req.http.X-HVH-Site == ' + quoted(site['id']) + ')'
        purge.append(condition + ' { if (req.http.X-Hestia-Varnish-Token != ' + quoted(site['token']) +
                     ' && req.http.X-UltraCache-Token != ' + quoted(site['token']) +
                     ') { return (synth(403, "Purge token denied")); } }')
        if site['recv']:
            custom_recv.append(condition + ' { set req.http.X-Cache-Mode = "PASS"; ' + site['recv'] +
                               ' unset req.http.X-Cache-Mode; }')
        if site['response']:
            custom_response.append('if (bereq.http.X-HVH-Site == ' + quoted(site['id']) + ') { ' + site['response'] + ' }')
    text.append('''sub vcl_recv {
  unset req.http.X-HVH-ESI-Parent;
  unset req.http.X-HVH-Site;
  unset req.http.X-HVH-Profile;
  unset req.http.X-HVH-Disabled;
  unset req.http.X-Cache-Mode;
  set req.http.host = std.tolower(regsub(regsub(req.http.host, ":[0-9]+$", ""), "[.]$", ""));
  ''' + '\n'.join(dispatch) + '''
  if (req.esi_level > 0 && req_top.http.X-HVH-Site != req.http.X-HVH-Site) {
    return (synth(403, "Cross-site ESI denied"));
  }
  if (req.http.X-Forwarded-Proto ~ "(?i)^https$") {
    set req.http.X-Forwarded-Proto = "https";
  } else { set req.http.X-Forwarded-Proto = "http"; }
  if (req.method == "PURGE" || req.method == "BAN") {
    if (req.esi_level > 0 || client.ip !~ hvh_local ||
        (req.http.X-Real-IP && req.http.X-Real-IP !~ "^(127[.]0[.]0[.]1|::1)$") ||
        (req.http.X-Forwarded-For && req.http.X-Forwarded-For !~ "^(127[.]0[.]0[.]1|::1)$")) {
      return (synth(403, "Purge source denied"));
    }
    ''' + '\n'.join(purge) + '''
    if (req.method == "PURGE") { return (purge); }
    ban("obj.http.X-HVH-Site == " + req.http.X-HVH-Site);
    return (synth(200, "Site cache invalidated"));
  }
  unset req.http.X-Hestia-Varnish-Token;
  unset req.http.X-UltraCache-Token;
  unset req.http.X-Ban-Expression;
  if (req.http.X-HVH-Disabled == "1") {
    set req.http.X-Cache-Mode = "PASS"; return (pass);
  }
  ''' + '\n'.join(custom_recv) + '''
  if (req.url ~ "^/[.]well-known/(acme-challenge|pki-validation)/") {
    set req.http.X-Cache-Mode = "PASS"; return (pass);
  }
  if (req.http.X-HVH-Profile == "ultracache") { call hvh_ultracache_recv; }
  if (req.http.Authorization || req.http.Upgrade || (req.method != "GET" && req.method != "HEAD")) {
    set req.http.X-Cache-Mode = "PASS"; return (pass);
  }
  if (req.http.Cookie) { set req.http.X-Cache-Mode = "PASS"; return (pass); }
  if (req.http.X-HVH-Profile == "wordpress" || req.http.X-HVH-Profile == "woocommerce") {
    if (req.url ~ "(?i)^/(wp-admin(?:/|[?]|$)|wp-login[.]php|wp-json(?:/|[?]|$)|xmlrpc[.]php|wp-cron[.]php)" ||
        req.url ~ "(?i)[?&](preview|customize_changeset_uuid|rest_route|nocache)=") {
      set req.http.X-Cache-Mode = "PASS"; return (pass);
    }
  }
  if (req.http.X-HVH-Profile == "woocommerce" &&
      (req.url ~ "(?i)^/(cart|checkout|my-account)(/|[?]|$)" ||
       req.url ~ "(?i)[?&](add-to-cart|wc-ajax|wc-api)=")) {
    set req.http.X-Cache-Mode = "PASS"; return (pass);
  }
  return (hash);
}
sub vcl_hash {
  hash_data(req.http.X-HVH-Site);
  hash_data(req.http.host);
  hash_data(req.url);
  return (lookup);
}
sub vcl_hit {
  if (req.http.X-HVH-Profile == "ultracache") { call hvh_ultracache_hit; }
}
sub vcl_backend_fetch {
  if (bereq.http.X-HVH-Profile == "ultracache") { call hvh_ultracache_backend_fetch; }
}
sub vcl_backend_response {
  if (bereq.http.X-HVH-Profile == "ultracache") { set beresp.keep = 5m; }
  if (beresp.http.Vary != "*") {
    if (!beresp.http.Vary) { set beresp.http.Vary = "X-Forwarded-Proto"; }
    else if (beresp.http.Vary !~ "(?i)(^|,)[[:blank:]]*X-Forwarded-Proto[[:blank:]]*(,|$)") {
      set beresp.http.Vary = beresp.http.Vary + ", X-Forwarded-Proto";
    }
  }
  ''' + '\n'.join(custom_response) + '''
  set beresp.http.X-HVH-Site = bereq.http.X-HVH-Site;
  if (bereq.http.X-HVH-Profile == "ultracache") { call hvh_ultracache_backend_response; }
  if (beresp.status >= 400 || beresp.http.Set-Cookie || beresp.http.Vary == "*" ||
      beresp.http.Cache-Control ~ "(?i)(private|no-cache|no-store)" || beresp.http.Pragma ~ "(?i)no-cache") {
    set beresp.ttl = 0s; set beresp.uncacheable = true;
  }
  return (deliver);
}
sub vcl_deliver {
  if (req.http.X-HVH-Profile == "ultracache") { call hvh_ultracache_deliver; }
  if (req.http.X-Cache-Mode == "PASS") { set resp.http.X-Hestia-Varnish = "BYPASS"; }
  else if (obj.hits > 0) { set resp.http.X-Hestia-Varnish = "HIT"; }
  else { set resp.http.X-Hestia-Varnish = "MISS"; }
  set resp.http.X-Hestia-Varnish-Profile = req.http.X-HVH-Profile;
  unset resp.http.X-HVH-Site;
  unset resp.http.X-HVH-ESI-Parent;
  unset resp.http.X-HVH-Profile;
}
''')
    # This is an addon-owned Varnish policy file. No application inspection,
    # configuration changes, connection checks or plugin imports are performed.
    text.insert(4, (ROOT / 'profiles/ultracache.vcl').read_text())
    return '\n'.join(text) + '\n'
