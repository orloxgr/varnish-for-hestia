"""Render shared Varnish policy with immutable site/host/backend boundaries."""
import ipaddress
from pathlib import Path
import re

from fragments import validate
from server_settings import choices
import cookie_policy
import browser_cache
import hosting_timeouts
import profile_settings

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
            sites.append(dict(site, backend=backends[origin], active=allowed and site['enabled'] and not site['suspended'],
                              hosts=hosts, recv=(validate(profile_rules[site['profile']]['custom_recv'], 'recv') + '\n' + validate(site['custom_recv'], 'recv')).strip(),
                              response=(validate(profile_rules[site['profile']]['custom_backend_response'], 'backend_response') + '\n' + validate(site['custom_backend_response'], 'backend_response')).strip(),
                              bypass_cookies=cookie_policy.normalize(site.get('bypass_cookies', []))))
    text = ['vcl 4.1;', 'import std; import purge;', 'acl hvh_local { "127.0.0.1"; "::1"; }',
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
                            'set req.backend_hint = ' + site['backend'] + ';\n' +
                            ('set req.http.X-HVH-Disabled = "1";\n' if not site['active'] else '') + '}')
    dispatch.append(('else ' if dispatch else '') + '{ return (synth(421, "Unknown cache host")); }')
    purge = []
    custom_recv, custom_response, cookie_bypass = [], [], []
    for site in sites:
        condition = 'if (req.http.X-HVH-Site == ' + quoted(site['id']) + ')'
        purge.append(condition + ' { if (req.http.X-Hestia-Varnish-Token != ' + quoted(site['token']) +
                     ' && req.http.X-UltraCache-Token != ' + quoted(site['token']) +
                     ') { return (synth(403, "Purge token denied")); } }')
        if site['recv']:
            custom_recv.append(condition + ' { set req.http.X-Cache-Mode = "PASS"; set req.http.X-HVH-Pass-Reason = "site-rule"; ' + site['recv'] +
                               ' unset req.http.X-Cache-Mode; unset req.http.X-HVH-Pass-Reason; }')
        if site['response']:
            custom_response.append('if (bereq.http.X-HVH-Site == ' + quoted(site['id']) + ') { ' + site['response'] + ' }')
        if site['bypass_cookies']:
            cookie_bypass.append(condition + ' { if (req.http.Cookie ~ ' +
                cookie_policy.vcl_pattern(site['bypass_cookies']) +
                ') { set req.http.X-HVH-Pass-Reason = "site-cookie-rule"; return (pass); } }')
    text.append('''sub vcl_recv {''' + hosting_timeouts.session(state) + '''
  unset req.http.X-HVH-ESI-Parent;
  unset req.http.X-HVH-Site;
  unset req.http.X-HVH-Profile;
  unset req.http.X-HVH-Disabled;
  unset req.http.X-HVH-Ban-Host;
  unset req.http.X-HVH-Ban-Pattern;
  unset req.http.X-HVH-Ban-HTML;
  unset req.http.X-HVH-Control;
  unset req.http.X-HVH-Soft-Purge;
  unset req.http.X-Cache-Mode;
  unset req.http.X-HVH-Pass-Reason;
  unset req.http.X-HVH-Vary-Cookie;
  unset req.http.X-ESI-Private-Request;
  unset req.http.X-ESI-Request-Level;
  unset req.http.X-ESI-Original-Cookie;
  unset req.http.X-UltraCache-ESI-Candidate;
  unset req.http.X-UltraCache-ESI-Cookie-Check;
  unset req.http.X-UltraCache-ESI-Opt-In;
  unset req.http.X-UltraCache-ESI-Shared-Parent;
  std.collect(req.http.Cookie, "; ");
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
    call hvh_http_control;
  }
  unset req.http.X-Hestia-Varnish-Token;
  unset req.http.X-UltraCache-Token;
  unset req.http.X-Ban-Expression;
  unset req.http.X-UltraCache-Contract;
  unset req.http.X-UltraCache-Operation;
  unset req.http.X-UltraCache-Object-Expression;
  if (req.http.X-HVH-Disabled == "1") {
    set req.http.X-HVH-Pass-Reason = "site-disabled"; return (pass);
  }
  ''' + '\n'.join(custom_recv) + '''
  ''' + '\n'.join(cookie_bypass) + '''
  if (req.http.X-HVH-Profile == "ultracache") { call hvh_ultracache_recv; }
  call hvh_common_recv;
  return (hash);
}
sub vcl_pass {
  set req.http.X-Cache-Mode = "PASS";
}
sub hvh_private_cookie_recv {
  if (req.http.Cookie ~ ''' + cookie_policy.vcl_pattern(cookie_policy.PRIVATE) + ''') {
    set req.http.X-HVH-Pass-Reason = "private-cookie"; return (pass);
  }
}
sub hvh_cart_cookie_recv {
  if (req.http.Cookie ~ ''' + cookie_policy.vcl_pattern(cookie_policy.CART) + ''') {
    if (req.http.X-HVH-Profile == "ultracache" && req.http.X-UltraCache-ESI-Opt-In == "1") {
      set req.http.X-UltraCache-ESI-Candidate = "1";
    } else { set req.http.X-HVH-Pass-Reason = "cart-session"; return (pass); }
  }
}
sub vcl_hash {
  # Do not reuse objects stored under an earlier privacy/cookie policy.
  # Scheme/Accept/encoding remain Vary variants of the same purgeable object.
  hash_data("hvh-cache-policy-v5");
  hash_data(req.http.X-HVH-Site);
  hash_data(req.http.host);
  hash_data(req.url);
  return (lookup);
}
sub vcl_hit {
  if (req.http.X-HVH-Soft-Purge == "1") { call hvh_soft_purge; }
  if (req.http.X-HVH-Profile == "ultracache") { call hvh_ultracache_hit; }
}
sub vcl_miss {
  if (req.http.X-HVH-Soft-Purge == "1") { call hvh_soft_purge; }
}
sub hvh_soft_purge {
  set req.http.X-HVH-Soft-Purge = purge.soft();
  return (synth(200, "Soft purge completed"));
}
sub vcl_backend_fetch {
  unset bereq.http.Surrogate-Capability;
  if (bereq.http.X-HVH-Profile == "ultracache") { call hvh_ultracache_backend_fetch; }
}
sub hvh_mark_uncacheable {
  # Keep only a hit-for-miss decision, never the private response body.
  # A zero-lived marker makes concurrent fetches wait for one another.
  if (!beresp.http.X-HVH-Pass-Reason) { set beresp.http.X-HVH-Pass-Reason = "origin-uncacheable"; }
  set beresp.ttl = 120s;
  set beresp.uncacheable = true;
  set beresp.grace = 0s;
  set beresp.keep = 0s;
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
  set beresp.http.X-Cache-Object-Host = bereq.http.host;
  set beresp.http.X-Cache-Object-URL = bereq.url;
  unset beresp.http.X-HVH-Pass-Reason;
  std.collect(beresp.http.Cache-Control);
  std.collect(beresp.http.Surrogate-Control);
  std.collect(beresp.http.Vary);
  call hvh_response_privacy;
  if (bereq.http.X-HVH-Profile == "ultracache") { call hvh_ultracache_backend_response; }
  call hvh_response_variants;
  return (deliver);
}
sub vcl_deliver {
  if (req.http.X-Cache-Mode == "PASS" || obj.uncacheable) {
    set resp.http.X-Hestia-Varnish = "PASS";
    if (req.http.X-HVH-Pass-Reason) { set resp.http.X-Hestia-Varnish-Reason = req.http.X-HVH-Pass-Reason; }
    else if (resp.http.X-HVH-Pass-Reason) { set resp.http.X-Hestia-Varnish-Reason = resp.http.X-HVH-Pass-Reason; }
    else { set resp.http.X-Hestia-Varnish-Reason = "origin-uncacheable"; }
  } else if (obj.hits > 0) {
    set resp.http.X-Hestia-Varnish = "HIT";
    set resp.http.X-Hestia-Varnish-Reason = "cache-hit";
  } else {
    set resp.http.X-Hestia-Varnish = "MISS";
    set resp.http.X-Hestia-Varnish-Reason = "cache-miss";
  }
  set resp.http.X-Cache = resp.http.X-Hestia-Varnish;
  unset resp.http.X-Cache-Hits;
  if (resp.http.X-Cache == "HIT") { set resp.http.X-Cache-Hits = obj.hits; }
  set resp.http.X-Hestia-Varnish-Profile = req.http.X-HVH-Profile;
  # Downstream caches vary on the real Cookie header, not our scratch key.
  set resp.http.Vary = regsuball(resp.http.Vary,
    "(?i)(^|,)[[:blank:]]*X-HVH-Vary-Cookie[[:blank:]]*(?=,|$)", "\\1Cookie");
  unset resp.http.X-HVH-Pass-Reason;
  unset resp.http.X-HVH-Site;
  unset resp.http.X-HVH-ESI-Parent;
  unset resp.http.X-HVH-Profile;
  unset resp.http.X-HVH-Vary-Cookie;
  unset resp.http.X-UltraCache-ESI-Shared-Parent;
  unset resp.http.X-UltraCache-ESI-Candidate;
  unset resp.http.X-UltraCache-ESI-Opt-In;
  unset resp.http.X-Cache-Object-Host;
  unset resp.http.X-Cache-Object-URL;
}
''')
    # This is an addon-owned Varnish policy file. No application inspection,
    # configuration changes, connection checks or plugin imports are performed.
    text.insert(4, (ROOT / 'profiles/common.vcl').read_text().replace('__TRACKING_COOKIES__',
        '{"' + cookie_policy.pattern(cookie_policy.TRACKING) + '[^;]*"}'))
    text.insert(4, (ROOT / 'profiles/ultracache.vcl').read_text())
    text.insert(4, (ROOT / 'profiles/control.vcl').read_text())
    return '\n'.join(text) + '\n'
