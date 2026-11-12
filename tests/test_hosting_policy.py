"""Hosting inheritance, scoped profile changes and real static browser headers."""
import copy
import http.client
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import addon
import administration
import browser_cache
import hosting_timeouts
import profile_settings
import service
from registry import desired_state
from vcl import render
import test_profile_compatibility as compatibility
import test_cache_policy as policy
from test_server_settings import fixture


class HostingPolicy(unittest.TestCase):
    def test_loaded_native_timeouts_exclude_generated_vhosts_and_keep_native_overrides(self):
        dump = '''# configuration file /etc/nginx/nginx.conf:
proxy_connect_timeout 750ms;
proxy_read_timeout 2m;
proxy_send_timeout 30s;
# configuration file /home/alice/conf/web/example.test/nginx.conf:
# Managed by varnish-for-hestia
proxy_read_timeout 900s;
# configuration file /home/alice/conf/web/example.test/nginx.conf_custom:
proxy_read_timeout 300s;
'''
        self.assertEqual(hosting_timeouts.discover(dump), dict(connect=750, read=300000, send=30000))
        self.assertEqual(hosting_timeouts.discover('# configuration file /etc/nginx/nginx.conf:\nevents {}'),
                         dict(connect=60000, read=60000, send=60000))
        self.assertEqual(hosting_timeouts.duration('1m 250ms'), 60250)
        self.assertEqual(hosting_timeouts.duration('0'), 0)
        with self.assertRaises(ValueError): hosting_timeouts.discover('invalid dump')

    def test_direct_apache_budget_and_saved_admin_override_are_preserved(self):
        state, _ = fixture()
        state['hosting_timeouts'] = dict(connect=250, read=300000, send=30000)
        text = render(state, {'origin_ip': '127.0.0.1'})
        self.assertIn('.connect_timeout = 0.25s;', text)
        self.assertIn('.first_byte_timeout = 300s;', text)
        self.assertIn('.between_bytes_timeout = 300s;', text)
        self.assertEqual(hosting_timeouts.frontend(state)['read'], 330250)
        state['server_settings'] = {'first_byte_timeout_seconds': 600}
        self.assertIn('.first_byte_timeout = 600s;', render(state, {'origin_ip': '127.0.0.1'}))
        self.assertEqual(hosting_timeouts.frontend(state)['read'], 630250)

    def test_central_and_site_browser_settings_do_not_overwrite_each_other(self):
        state, _ = fixture()
        site = state['owners']['alice']['sites']['example.test']
        self.assertEqual(browser_cache.selected(site, state)['static_seconds'], 2592000)
        payload = dict(browser_enabled=True, static_seconds=42, versioned_seconds=0, versioned_paths='/assets/app-{hash}.js')
        browser_cache.change(state, payload)
        self.assertEqual(browser_cache.selected(site, state)['static_seconds'], 42)
        browser_cache.change(state, dict(payload, static_seconds=90), site)
        browser_cache.change(state, dict(payload, static_seconds=10))
        self.assertEqual(browser_cache.selected(site, state)['static_seconds'], 90)
        browser_cache.change(state, {'inherit_browser_cache': True}, site)
        self.assertEqual(browser_cache.selected(site, state)['static_seconds'], 10)
        site['profile'] = 'ultracache'
        self.assertIn(browser_cache.PROFILE_PATHS['ultracache'][0], browser_cache.selected(site, state)['versioned_paths'])
        self.assertEqual(state['browser_cache']['versioned_paths'], ['/assets/app-{hash}.js'])
        for path in ['/assets/{hash}.js; return 200;', '/../{hash}.js', '/assets/*.js', '/$uri/{hash}.js']:
            with self.assertRaises(ValueError): browser_cache.pattern(path)
        self.assertEqual(browser_cache.validate(dict(browser_cache.DEFAULTS, static_seconds=10**12))['static_seconds'], 10**12)

    def test_profile_default_only_affects_new_domains_and_rules_are_scoped(self):
        state, inventory = fixture()
        profile_settings.change(state, dict(profile='ultracache', default_profile='ultracache',
            custom_recv='if (req.url == "/members/") { return (pass); }',
            custom_backend_response='set beresp.http.X-User-Central = "yes";'))
        inventory['alice']['sites']['new.test'] = dict(aliases=[], suspended=False)
        after = desired_state(state, inventory, 'varnish')
        self.assertEqual(after['owners']['alice']['sites']['example.test']['profile'], 'general')
        self.assertEqual(after['owners']['alice']['sites']['new.test']['profile'], 'ultracache')
        self.assertEqual(after['owners']['alice']['sites']['new.test']['enabled'], True)
        text = render(after, {'origin_ip': '127.0.0.1'})
        self.assertEqual(text.count('X-User-Central'), 1)
        with self.assertRaises(ValueError):
            profile_settings.change(after, dict(profile='general', custom_recv='set req.backend_hint = foreign;', custom_backend_response=''))

    def test_profile_change_invalidates_only_its_sites_and_browser_changes_keep_html(self):
        import hashlib
        from test_cookie_rules import fixture as many_sites
        previous, _ = many_sites()
        sites = [site for owner in previous['owners'].values() for site in owner['sites'].values()]
        sites[0]['profile'] = 'ultracache'
        state = copy.deepcopy(previous)
        profile_settings.change(state, dict(profile='ultracache', custom_recv='return (pass);', custom_backend_response=''))
        config = {'origin_ip': '127.0.0.1', 'origin_port': 8080}
        def apply(before, after):
            program = render(after, config)
            name = 'hvh_gen_' + hashlib.sha256(program.encode()).hexdigest()[:32]
            with tempfile.TemporaryDirectory() as folder:
                active = Path(folder) / 'active.vcl'; active.write_text(program)
                with patch.object(service, 'ACTIVE', active), \
                     patch.object(service, 'vcls', return_value=[{'name': name, 'status': 'active'}]), \
                     patch.object(service.routing, 'apply', return_value=({}, None)), \
                     patch.object(service.routing, 'apache_config', return_value=''), \
                     patch.object(service, 'purge') as purge, patch.object(service, 'prune'):
                    result = service.apply(after, before, {}, config, changes=[])
                    return result, purge.call_count
        result, count = apply(previous, state)
        self.assertEqual((result['invalidated_sites'], count), (1, 1))
        browser = copy.deepcopy(state); browser['browser_cache'] = dict(browser_cache.DEFAULTS, static_seconds=60)
        result, count = apply(state, browser)
        self.assertEqual((result['invalidated_sites'], count), (0, 0))

    def test_new_admin_actions_cannot_be_called_by_site_owners(self):
        for action in ('admin-browser-cache', 'admin-profile-settings'):
            with patch.object(addon, 'hestia', return_value={'alice': {'ROLE': 'user', 'SUSPENDED': 'no'}}), \
                 patch.object(administration, 'request') as request:
                with self.assertRaises(addon.RequestError): addon.dispatch(dict(actor='alice', owner='alice', action=action))
                request.assert_not_called()

    def test_owner_browser_change_is_scoped_and_rejects_foreign_domain(self):
        state, _ = fixture()
        def reconcile(hestia, mutate):
            candidate = copy.deepcopy(state)
            mutate(candidate, {})
            state.clear(); state.update(candidate)
            return state, {}, {}
        payload = dict(domain='example.test', browser_enabled=True, static_seconds=100, versioned_seconds=200, versioned_paths='')
        with patch.object(service, 'reconcile', side_effect=reconcile):
            result = service.request(None, 'alice', 'configure-browser-cache', payload)
            self.assertEqual(result['sites'][0]['browser_cache']['static_seconds'], 100)
            with self.assertRaises(ValueError):
                service.request(None, 'alice', 'configure-browser-cache', dict(payload, domain='other.test'))

    @unittest.skipUnless(shutil.which('nginx'), 'Native Nginx required')
    def test_native_static_headers_revalidation_fallback_and_domain_isolation(self):
        with tempfile.TemporaryDirectory(prefix='hvh-browser-') as folder:
            root = Path(folder)
            root.chmod(0o755)
            (root / 'asset.css').write_text('body{}')
            (root / 'app-deadbeef.js').write_text('var a=1;')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            state, _ = fixture(); site = state['owners']['alice']['sites']['example.test']
            state['browser_cache'] = dict(browser_cache.DEFAULTS, versioned_paths=['/app-{hash}.js'])
            fragment = browser_cache.template('''server {
listen 127.0.0.1:PORT;
root ROOT;
add_header X-Proof-Inherited "retained" always;
location / { try_files $uri @dynamic; expires max; }
location @dynamic { add_header Cache-Control "private, no-store"; return 200 "dynamic"; }
}'''.replace('PORT', str(port)).replace('ROOT', str(root)), site, state, 'tpl')
            config = root / 'nginx.conf'
            def write(text):
                config.write_text('pid ' + str(root / 'nginx.pid') + ';\nerror_log ' + str(root / 'error.log') + ';\nevents {}\nhttp { access_log off; ' + text + '\n}')
            write(fragment)
            run = subprocess.run(['nginx', '-t', '-c', str(config), '-p', str(root)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            process = subprocess.Popen(['nginx', '-c', str(config), '-p', str(root), '-g', 'daemon off;'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                for _ in range(100):
                    try:
                        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                        conn.request('GET', '/asset.css'); response = conn.getresponse(); response.read(); break
                    except OSError: time.sleep(.02)
                self.assertEqual(response.getheader('Cache-Control'), 'public, max-age=2592000')
                self.assertEqual(response.getheader('X-Proof-Inherited'), 'retained')
                self.assertEqual(len([h for h, _ in response.getheaders() if h.lower() == 'cache-control']), 1)
                etag = response.getheader('ETag'); self.assertTrue(etag)
                conn.request('GET', '/asset.css', headers={'If-None-Match': etag}); response = conn.getresponse(); response.read()
                self.assertEqual(response.status, 304)
                self.assertEqual(response.getheader('Cache-Control'), 'public, max-age=2592000')
                conn.request('GET', '/app-deadbeef.js?ver=1'); response = conn.getresponse(); response.read()
                self.assertEqual(response.getheader('Cache-Control'), 'public, max-age=31536000, immutable')
                conn.request('GET', '/missing.css'); response = conn.getresponse(); response.read()
                self.assertEqual(response.getheader('Cache-Control'), 'private, no-store')
                conn.close()
            finally:
                process.terminate(); process.communicate(timeout=10)


@unittest.skipUnless(shutil.which('varnishtest'), 'Native Varnish required')
class NativeHostingPolicy(unittest.TestCase):
    run_policy = policy.CachePolicy.run_policy

    def test_query_values_and_non_html_bodies_are_cached_separately(self):
        for profile in compatibility.PROFILES:
            responses, requests = [], []
            for query, body in [('page=1', 'one'), ('page=2', 'two')]:
                path = '/assets.php?' + query
                responses.append(compatibility.response(path, body, headers=['Content-Type: text/css']))
                requests += [compatibility.request(path, body, headers=['Cookie: unknown=first'], cache='MISS'),
                             compatibility.request(path, body, headers=['Cookie: unknown=second'], cache='HIT')]
            self.run_policy(profile, responses, requests)

    def test_inherited_timeout_allows_slow_post_despite_short_service_default(self):
        state, _ = fixture(); state['hosting_timeouts'] = dict(connect=500, read=1000, send=1000)
        source = render(state, {'origin_ip': '127.0.0.1', 'origin_port': 8080}).replace('"8080"', '"${s1_port}"', 1)
        source_script = '''varnishtest "inherited first-byte timeout for single POST"
server s1 { rxreq
 expect req.method == "POST"
 delay 0.3
 txresp -body {once}
} -start
varnish v1 -arg "-p first_byte_timeout=0.1" -vcl {
''' + source + '''
} -start
client c1 { txreq -req POST -url /wp-json/action -hdr "Host: example.test"
 rxresp
 expect resp.status == 200
 expect resp.body == "once"
 expect resp.http.X-Hestia-Varnish == "BYPASS"
} -run
server s1 -wait
'''
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'post.vtc'; path.write_text(source_script)
            result = subprocess.run(['varnishtest', '-t', '15', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
