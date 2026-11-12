"""Native HTTP regressions for privacy, hit-for-miss and cookie handling."""
import concurrent.futures
import http.client
import http.server
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest

import test_profile_compatibility as compatibility


@unittest.skipUnless(shutil.which('varnishtest'), 'native varnishtest is required')
class CachePolicy(unittest.TestCase):
    def run_policy(self, profile, responses, requests, *, tail='', program=None):
        source = compatibility.program(profile) if program is None else program
        content = ('varnishtest "Cache policy regression"\nserver s1 {\n' +
                   '\n'.join(responses).removeprefix('accept\n') + '\n} -start\n' +
                   'varnish v1 -vcl {\n' + source + '\n} -start\nclient c1 {\n' +
                   '\n'.join(requests) + '\n} -run\n' + tail + '\nserver s1 -wait\n')
        with tempfile.TemporaryDirectory(prefix='hvh-policy-') as directory:
            path = Path(directory) / 'policy.vtc'
            path.write_text(content)
            result = subprocess.run(['varnishtest', '-t', '15', str(path)],
                                    capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_uncacheable_responses_keep_hit_for_miss_without_reusing_bodies(self):
        cases = [('private, no-store', [], 200), ('public, max-age=120', ['Set-Cookie: session=a'], 200),
                 ('public, max-age=120', ['Vary: *'], 200),
                 ('public, max-age=120', ['Surrogate-Control: no-store'], 200),
                 ('public, max-age=120', ['Surrogate-Control: No-Store'], 200),
                 ('public, max-age=120', ['Surrogate-Control: max-age=600', 'Surrogate-Control: no-store'], 200),
                 ('public, max-age=0', [], 200), ('public, max-age=120', [], 404),
                 ('public, max-age=120', [], 503)]
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                responses, requests = [], []
                for number, (policy, headers, status) in enumerate(cases):
                    path = '/uncacheable-' + str(number)
                    for visitor in ('A', 'B'):
                        body = path + visitor
                        responses.append(compatibility.response(path, body, policy=policy,
                                                               headers=headers, status=status))
                        requests.append(compatibility.request(path, body, status=status))
                self.run_policy(profile, responses, requests,
                                tail='varnish v1 -expect MAIN.cache_hitmiss == ' + str(len(cases)))

    def test_hit_for_miss_can_become_cacheable_before_marker_expires(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [compatibility.response('/changing', 'private', policy='private, no-store'),
                     compatibility.response('/changing', 'public')],
                    [compatibility.request('/changing', 'private'),
                     compatibility.request('/changing', 'public', cache='MISS'),
                     compatibility.request('/changing', 'public', cache='HIT')],
                    tail='varnish v1 -expect MAIN.cache_hitmiss == 1')

    def test_site_ttl_cannot_override_surrogate_no_store(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                source = compatibility.program(profile, backend_response='set beresp.ttl = 1d;')
                self.run_policy(profile,
                    [compatibility.response('/private', visitor, headers=['Surrogate-Control: no-store'])
                     for visitor in ('A', 'B')],
                    [compatibility.request('/private', visitor) for visitor in ('A', 'B')],
                    program=source, tail='varnish v1 -expect MAIN.cache_hitmiss == 1')

    def test_site_zero_ttl_keeps_only_hit_for_miss(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                source = compatibility.program(profile,
                    backend_response='set beresp.ttl = 0s; set beresp.grace = 1m; set beresp.keep = 1m;')
                self.run_policy(profile,
                    [compatibility.response('/uncached', visitor) for visitor in ('A', 'B')],
                    [compatibility.request('/uncached', visitor) for visitor in ('A', 'B')],
                    program=source, tail='varnish v1 -expect MAIN.cache_hitmiss == 1')

    def test_no_store_esi_parent_is_composed_for_each_delivery(self):
        for surrogate_headers in (['Surrogate-Control: ESI/1.0, no-store'],
                                  ['Surrogate-Control: ESI/1.0', 'Surrogate-Control: no-store']):
            with self.subTest(headers=surrogate_headers):
                self.run_policy('ultracache',
                    [compatibility.response('/parent', '<html>A<esi:include src="/fragment"/></html>',
                         headers=['Content-Type: text/html', *surrogate_headers]),
                     compatibility.response('/fragment', 'fragment'),
                     compatibility.response('/parent', '<html>B<esi:include src="/fragment"/></html>',
                         headers=['Content-Type: text/html', *surrogate_headers])],
                    [compatibility.request('/parent', '<html>Afragment</html>', cache='BYPASS'),
                     compatibility.request('/parent', '<html>Bfragment</html>', cache='BYPASS')],
                    tail='varnish v1 -expect MAIN.cache_hitmiss == 1')

    def test_shared_parent_approval_cannot_override_surrogate_no_store(self):
        cookie = 'woocommerce_items_in_cart=1; ultracache_esi_optin=1'
        self.run_policy('ultracache',
            [compatibility.response('/parent', visitor, headers=['Content-Type: text/html',
                'Surrogate-Control: ESI/1.0, no-store', 'X-UltraCache-ESI-Shared-Parent: 1'],
                expect=['expect req.http.Cookie == "woocommerce_items_in_cart=1"'])
             for visitor in ('A', 'B')],
            [compatibility.request('/parent', visitor, headers=['Cookie: '+cookie], cache='BYPASS')
             for visitor in ('A', 'B')], tail='varnish v1 -expect MAIN.cache_hitmiss == 1')

    def test_analytics_and_unknown_cookies_share_public_objects_without_stripping(self):
        cookies = ['_ga=first', '_ga=first; _gid=second',
                   '__utma=first; _ga_G123ABC=second; _gat_gtag_UA_123_1=third; _fbp=fourth',
                   '_ga=first; _ga=second; _gid=',
                   '__utmb=b; __utmc=c; __utmt=t; __utmv=v; __utmz=z; _gat=1',
                   'sbjs_migrations=m; sbjs_current_add=c; sbjs_first_add=f',
                   'cmplz_banner-status=dismissed; never_seen_before=visitor',
                   'some_vendor_2026=anything; custom_session=A', 'language=el; currency=EUR']
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                responses, requests = [], []
                for number, cookie in enumerate(cookies):
                    path = '/page-' + str(number)
                    responses.append(compatibility.response(path, 'anonymous',
                                     expect=['expect req.http.Cookie == "'+cookie+'"']))
                    requests.extend([compatibility.request(path, 'anonymous', headers=['Cookie: '+cookie], cache='MISS'),
                                     compatibility.request(path, 'anonymous', headers=['Cookie: _ga=another'], cache='HIT')])
                self.run_policy(profile, responses, requests)

    def test_builtin_private_cookies_pass_without_stripping_any_cookies(self):
        cookies = ['wordpress_logged_in_abcd=A', 'wordpress_sec_abcd=A', 'wp-postpass_abcd=A',
                   'comment_author_abcd=A', 'PHPSESSID=A', 'woocommerce_items_in_cart=1',
                   'woocommerce_cart_hash=A', 'wp_woocommerce_session_abcd=A',
                   'woocommerce_recently_viewed=1', 'yith_wcwl_session_abcd=A', 'yith_woocompare_abcd=A']
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                responses, requests = [], []
                for cookie in cookies:
                    for combined in ('_ga=tracking; '+cookie, cookie+'; _gid=tracking',
                                     '_ga=tracking; '+cookie+'; _fbp=tracking'):
                        for visitor in ('A', 'B'):
                            responses.append(compatibility.response('/page', visitor,
                                             expect=['expect req.http.Cookie == "'+combined+'"']))
                            requests.append(compatibility.request('/page', visitor,
                                            headers=['Cookie: '+combined], cache='BYPASS'))
                self.run_policy(profile, responses, requests)

    def test_application_private_paths_preserve_original_cookies(self):
        for profile in ('wordpress', 'woocommerce'):
            with self.subTest(profile=profile):
                paths = ['/wp-admin/', '/wp-login.php', '/wp-json/', '/?preview=1']
                if profile == 'woocommerce':
                    paths += ['/cart/', '/checkout/', '/my-account/', '/?add-to-cart=1']
                responses, requests = [], []
                for path in paths:
                    for visitor in ('A', 'B'):
                        responses.append(compatibility.response(path, visitor,
                                         expect=['expect req.http.Cookie == "_ga=tracking"']))
                        requests.append(compatibility.request(path, visitor,
                                        headers=['Cookie: _ga=tracking'], cache='BYPASS'))
                self.run_policy(profile, responses, requests)

    def test_post_and_authorization_pass_with_original_cookies(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                responses, requests = [], []
                for method, extra in [('POST', []), ('GET', ['Authorization: Bearer fixture'])]:
                    for visitor in ('A', 'B'):
                        responses.append(compatibility.response('/page', visitor,
                                         expect=['expect req.http.Cookie == "_ga=tracking"']))
                        requests.append(compatibility.request('/page', visitor, method=method,
                                        headers=['Cookie: _ga=tracking', *extra], cache='BYPASS'))
                self.run_policy(profile, responses, requests)

    def test_upgrade_does_not_reuse_previous_policy_namespace(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                source = compatibility.program(profile)
                old = source.replace('hash_data("hvh-cache-policy-v4");', 'hash_data("hvh-cache-policy-v3");')
                tail = ('varnish v1 -vcl {\n'+source+'\n}\nclient c2 {\n'+
                        compatibility.request('/page', 'new', cache='MISS')+'\n'+
                        compatibility.request('/page', 'new', cache='HIT')+'\n} -run')
                self.run_policy(profile,
                    [compatibility.response('/page', 'old'), compatibility.response('/page', 'new')],
                    [compatibility.request('/page', 'old', cache='MISS')], program=old, tail=tail)

    @unittest.skipUnless(shutil.which('varnishd'), 'native varnishd is required')
    def test_uncacheable_concurrent_fetches_reach_origin_together(self):
        # The origin waits for all eight arrivals. Serializing these fetches
        # fails the rendezvous rather than relying on a benchmark threshold.
        class Origin(http.server.BaseHTTPRequestHandler):
            arrivals = 0
            mutex = threading.Lock()
            ready = threading.Event()

            def do_GET(self):
                with self.mutex:
                    type(self).arrivals += 1
                    number = self.arrivals
                    if number == 9:
                        self.ready.set()
                ok = number == 1 or self.ready.wait(5)
                body = str(number).encode()
                self.send_response(200 if ok else 504)
                self.send_header('Cache-Control', 'private, no-store')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Origin)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='hvh-concurrent-') as directory:
                root = Path(directory)
                source = compatibility.program('general').replace('"${s1_port}"', '"'+str(server.server_port)+'"')
                (root/'policy.vcl').write_text(source)
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    port = sock.getsockname()[1]
                with (root/'varnish.log').open('w+') as log:
                    process = subprocess.Popen(['varnishd', '-F', '-j', 'none', '-n', str(root/'instance'),
                        '-a', '127.0.0.1:'+str(port), '-T', 'none', '-f', str(root/'policy.vcl'),
                        '-s', 'malloc,32m', '-p', 'thread_pool_min=5', '-p', 'thread_pool_max=20'],
                        stdout=log, stderr=log)
                    try:
                        deadline = time.monotonic()+10
                        while True:
                            if process.poll() is not None:
                                log.seek(0)
                                self.fail(log.read())
                            try:
                                with socket.create_connection(('127.0.0.1', port), timeout=.1):
                                    break
                            except OSError:
                                if time.monotonic() > deadline:
                                    raise
                                time.sleep(.05)

                        def get():
                            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
                            try:
                                connection.request('GET', '/private', headers={'Host': 'example.test', 'Connection': 'close'})
                                response = connection.getresponse()
                                return response.status, response.read()
                            finally:
                                connection.close()

                        self.assertEqual(get(), (200, b'1'))
                        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                            responses = list(executor.map(lambda _: get(), range(8)))
                        self.assertEqual(sorted(responses), [(200, str(n).encode()) for n in range(2, 10)])
                        self.assertTrue(Origin.ready.is_set())
                    finally:
                        process.terminate()
                        try:
                            process.wait(timeout=8)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
