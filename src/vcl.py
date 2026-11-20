"""Render shared Varnish policy with immutable site/host/backend boundaries."""
import ipaddress
import json
from pathlib import Path
import re

from fragments import validate
from server_settings import choices
import cookie_policy
import browser_cache
import hosting_timeouts
import profile_settings
import cookie_admin
import cookie_control
import aggressive
import cms_routes

PROFILES = profile_settings.PROFILES
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
    timeout = choices(state)['first_byte_timeout_seconds']
    backend_options = hosting_timeouts.backend(state, timeout)
    profile_rules = profile_settings.choices(state)['rules']
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
            if site['profile'] not in PROFILES or not re.fullmatch(r'[A-Za-z0-9_-]{12,}', site['token']):
                raise ValueError('Invalid Varnish profile or purge token')
            hosts = [host_name(domain), *(host_name(a) for a in site['aliases'])]
            if names.intersection(hosts) or len(hosts) != len(set(hosts)):
                raise ValueError('A hostname cannot belong to more than one site')
            names.update(hosts)
            origin = str(ipaddress.ip_address(site.get('origin_ip', address)))
            if origin not in backends:
                backends[origin] = 'hvh_origin_' + str(len(backends))
            browser_cache.selected(site, state)
            sites.append(dict(site, **aggressive.settings(site), domain=domain, backend=backends[origin], active=allowed and site['enabled'] and not site['suspended'],
                              cookie_contract=cookie_control.cache_contract(site.get('cookie_integration'),domain,site['aliases'],
                                  state.get('cookie_policies'),site.get('cookie_policies')),
                              owned_domains=list(owner['sites']),
                              hosts=hosts, recv=(validate(profile_rules[site['profile']]['custom_recv'], 'recv') + '\n' + validate(site['custom_recv'], 'recv')).strip(),
                              response=(validate(profile_rules[site['profile']]['custom_backend_response'], 'backend_response') + '\n' + validate(site['custom_backend_response'], 'backend_response')).strip(),
                              bypass_cookies=cookie_policy.normalize(site.get('bypass_cookies', []))))
    text = ['vcl 4.1;', 'import std; import purge; import header; import cookie_handoff;', 'acl hvh_local { "127.0.0.1"; "::1"; }',
            '\n'.join('backend ' + name + ' { .host = ' + quoted(ip) + '; .port = ' + quoted(str(port)) + ';'+backend_options+' }'
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
                            ('set req.http.X-SCP-Aggressive = "1"; set req.http.X-SCP-Aggressive-TTL = ' + quoted(str(site['aggressive_ttl'])) + ';\n' if site['aggressive'] else '') +
                            'set req.backend_hint = ' + site['backend'] + ';\n' +
                            ('set req.http.X-SCP-Cookie-Contract = ' + quoted(site['cookie_contract']) + ';\n') +
                            ('set req.http.X-HVH-Disabled = "1";\n' if not site['active'] else '') + '}')
    dispatch.append(('else ' if dispatch else '') + '{ return (synth(421, "Unknown cache host")); }')
    purge = []
    delivery_authorization = []
    custom_recv, custom_response, cookie_bypass, cookie_rules, response_rules = [], [], [], [], []
    cookie_groups={}
    response_groups={}
    cms_rules=[]
    for site in sites:
        condition = 'if (req.http.X-HVH-Site == ' + quoted(site['id']) + ')'
        if site['active'] and site['profile']=='ultracache':
            delivery_authorization.append('if (bereq.http.X-HVH-Site == '+quoted(site['id'])+
                ') { set bereq.http.X-UltraCache-Delivery-Authorization = '+quoted(site['token'])+'; }')
        if site.get('cms_pending_root'):
            custom_recv.append(condition+' { set req.http.X-SCP-Reason = "cms-document-root-changed"; return (pass); }')
        # Identical effective rules are emitted once, irrespective of the
        # number of hosted domains. IDs/descriptions do not multiply VCL.
        session_names=aggressive.session_names(site)
        key=json.dumps([cookie_admin.concrete(site.get('cookie_policies')),site['aggressive'],session_names],sort_keys=True)
        cookie_groups.setdefault(key,{'settings':site.get('cookie_policies'),'aggressive':site['aggressive'],'session_names':session_names,'ids':[]})['ids'].append(site['id'])
        cms_code=cms_routes.compile_recv(site.get('cms_installations'))
        if cms_code:
            cms_rules.append(condition+' {\n'+cms_code+'\n}')
        paths=cms_routes.compile_custom_recv(site.get('custom_private_paths',[]),reason='custom-private-path')
        if paths:
            custom_recv.append(condition+' {\n'+paths+'\n}')
        purge.append(condition + ' { if (req.http.X-Hestia-Varnish-Token != ' + quoted(site['token']) +
                     ' && req.http.X-UltraCache-Token != ' + quoted(site['token']) +
                     ') { return (synth(403, "Purge token denied")); } }')
        if site['recv']:
            custom_recv.append(condition + ' { set req.http.X-SCP-Reason = "site-rule"; ' + site['recv'] +
                               ' unset req.http.X-SCP-Reason; }')
        if site['response']:
            custom_response.append('if (bereq.http.X-HVH-Site == ' + quoted(site['id']) + ') { ' + site['response'] + ' }')
        if site['bypass_cookies']:
            cookie_bypass.append(condition + ' { if (req.http.Cookie ~ ' +
                cookie_policy.vcl_pattern(site['bypass_cookies']) +
                ') { set req.http.X-SCP-Cookie-Name = regsub(req.http.Cookie, {"^.*?' +
                cookie_policy.pattern(site['bypass_cookies']) + '.*$"}, "\\2");' +
                ' set req.http.X-SCP-Cookie-Role = "site-bypass";' +
                ' set req.http.X-SCP-Reason = "site-cookie-rule"; return (pass); } }')
    for group in cookie_groups.values():
        condition=' || '.join('req.http.X-HVH-Site == '+quoted(identity) for identity in group['ids'])
        cookie_rules.append('if ('+condition+') {\n'+cookie_admin.compile_vcl(state.get('cookie_policies'),group['settings'],chain_defaults=True,automatic_shared=group['session_names'])+'\n}')
        rules = cookie_admin.response_rules(state.get('cookie_policies'),group['settings'],aggressive_mode=group['aggressive'],automatic_shared=group['session_names'])
        response_groups.setdefault(rules,[]).extend(group['ids'])
    for rules,identities in response_groups.items():
        condition=' || '.join('bereq.http.X-HVH-Site == '+quoted(identity) for identity in identities)
        response_rules.append('if ('+condition+') {\nif (cookie_handoff.detach({"'+rules+'"}, bereq.is_bgfetch)) {}\n}')
    text.append('''sub vcl_recv {
  call scp_init;''' + hosting_timeouts.session(state) + '''
  unset req.http.X-HVH-ESI-Parent;
  unset req.http.X-HVH-Site;
  unset req.http.X-HVH-Profile;
  unset req.http.X-HVH-Disabled;
  unset req.http.X-HVH-Ban-Host;
  unset req.http.X-HVH-Ban-Pattern;
  unset req.http.X-HVH-Ban-HTML;
  unset req.http.X-HVH-Control;
  unset req.http.X-HVH-Soft-Purge;
  std.collect(req.http.Cookie, "; ");
  set req.http.host = std.tolower(regsub(regsub(req.http.host, ":[0-9]+$", ""), "[.]$", ""));
  ''' + '\n'.join(dispatch) + '''
  set req.http.X-SCP-Profile = req.http.X-HVH-Profile;
  set req.http.X-SCP-Site = req.http.X-HVH-Site;
  if (req.esi_level > 0 && req_top.http.X-HVH-Site != req.http.X-HVH-Site) {
    return (synth(403, "Cross-site ESI denied"));
  }
  if (req.http.X-Forwarded-Proto ~ "(?i)^https$") {
    set req.http.X-Forwarded-Proto = "https";
  } else { set req.http.X-Forwarded-Proto = "http"; }
  if (req.method == "PURGE" || req.method == "BAN" || req.method == "UC-PRIVATE-GET") {
    if (req.esi_level > 0 || client.ip !~ hvh_local ||
        (req.http.X-Real-IP && req.http.X-Real-IP !~ "^(127[.]0[.]0[.]1|::1)$") ||
        (req.http.X-Forwarded-For && req.http.X-Forwarded-For !~ "^(127[.]0[.]0[.]1|::1)$")) {
      return (synth(403, "Purge source denied"));
    }
    ''' + '\n'.join(purge) + '''
    if (req.method == "UC-PRIVATE-GET") {
      if (req.http.X-HVH-Disabled == "1") { return (synth(403, "Site disabled")); }
      call scp_private_lookup;
    }
    call hvh_http_control;
  }
  unset req.http.X-Hestia-Varnish-Token;
  unset req.http.X-UltraCache-Token;
  unset req.http.X-UltraCache-Private-Key;
  unset req.http.X-Ban-Expression;
  unset req.http.X-UltraCache-Contract;
  unset req.http.X-UltraCache-Operation;
  unset req.http.X-UltraCache-Object-Expression;
  if (req.http.X-HVH-Disabled == "1") {
    set req.http.X-SCP-Reason = "site-disabled"; return (pass);
  }
  ''' + '\n'.join(custom_recv) + '''
  ''' + '\n'.join(cookie_bypass) + '''
  call scp_recv;
  return (hash);
}
sub vcl_pass {
  call scp_pass;
}
sub vcl_hash {
  call scp_private_hash;
  # Do not reuse objects stored under an earlier privacy/cookie policy.
  # Scheme/Accept/encoding remain Vary variants of the same purgeable object.
  call scp_key;
  call scp_cookie_hash;
  hash_data("hvh-cache-policy-v10");
  hash_data(req.http.X-HVH-Site);
  if (req.http.X-SCP-Aggressive == "1") { hash_data("aggressive"); hash_data(req.http.X-SCP-Aggressive-TTL); }
  hash_data(req.http.host);
  hash_data(req.http.X-SCP-Key-URL);
  return (lookup);
}
sub vcl_hit {
  if (req.http.X-HVH-Soft-Purge == "1") { call hvh_soft_purge; }
  call scp_hit;
}
sub vcl_miss {
  call scp_private_miss;
  call scp_cookie_miss;
  if (req.http.X-HVH-Soft-Purge == "1") { call hvh_soft_purge; }
}
sub hvh_soft_purge {
  set req.http.X-HVH-Soft-Purge = purge.soft();
  return (synth(200, "Soft purge completed"));
}
sub vcl_backend_fetch {
  call scp_backend_fetch;
}
sub vcl_backend_response {
  ''' + '\n'.join(custom_response) + '''
  set beresp.http.X-HVH-Site = bereq.http.X-HVH-Site;
  set beresp.http.X-Cache-Object-Host = bereq.http.host;
  set beresp.http.X-Cache-Object-URL = bereq.http.X-SCP-Key-URL;
  call scp_backend_response;
  return (deliver);
}
sub vcl_backend_error {
  cookie_handoff.discard();
}
sub vcl_deliver {
  call scp_deliver;
  set resp.http.X-Hestia-Varnish = resp.http.X-SCP-Result;
  set resp.http.X-Hestia-Varnish-Reason = resp.http.X-SCP-Result-Reason;
  set resp.http.X-Hestia-Varnish-Profile = req.http.X-HVH-Profile;
  unset resp.http.X-SCP-Result;
  unset resp.http.X-SCP-Result-Reason;
  unset resp.http.X-HVH-Site;
  unset resp.http.X-HVH-ESI-Parent;
  unset resp.http.X-HVH-Profile;
  unset resp.http.X-Cache-Object-Host;
  unset resp.http.X-Cache-Object-URL;
}
sub scp_private_document_diagnostics {
  set resp.http.X-Hestia-Varnish = "PASS";
  set resp.http.X-Hestia-Varnish-Reason = "application-private-document";
  if (resp.http.X-UltraCache-Application-Private && resp.http.X-UltraCache-Application-Private != "") {
    set resp.http.X-Hestia-Varnish-Reason = resp.http.X-UltraCache-Application-Private;
  }
  set resp.http.X-Hestia-Varnish-Profile = req.http.X-HVH-Profile;
}
''')
    # This is an addon-owned Varnish policy file. No application inspection,
    # configuration changes, connection checks or plugin imports are performed.
    text.insert(4, cookie_policy.shared_policy('\n'.join(cookie_rules), '\n'.join(response_rules), '\n'.join(cms_rules), '\n'.join(delivery_authorization)))
    if cookie_groups:
        text.insert(4, cookie_admin.defaults_vcl())
    text.insert(4, (ROOT / 'profiles/control.vcl').read_text())
    return '\n'.join(text) + '\n'
