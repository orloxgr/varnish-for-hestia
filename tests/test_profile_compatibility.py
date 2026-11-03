"""Run product VCL against plain HTTP origins; no hosting panel or app required.

Requires native varnishtest. Each test uses ephemeral processes and loopback ports.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from vcl import PROFILES, render


def program(profile, *, backend_response='', bypass_cookies=None):
    state = {'owners': {'alice': {'enabled': True, 'suspended': False, 'package': 'default', 'sites': {
        'example.test': {'id': 'a'*32, 'aliases': [], 'profile': profile, 'token': 'A'*32,
                         'enabled': True, 'suspended': False, 'custom_recv': '',
                         'custom_backend_response': backend_response, 'bypass_cookies': bypass_cookies or []}}}}}
    return render(state, {'origin_ip': '127.0.0.1', 'origin_port': 8080}).replace('"8080"', '"${s1_port}"', 1)


def response(path, body, *, headers=(), expect=(), policy='public, max-age=120', status=200):
    return '\n'.join(['accept', 'rxreq', 'expect req.url == "'+path+'"', *expect,
        'txresp -status '+str(status)+' -hdr "Connection: close" -hdr "Cache-Control: '+policy+'" '+
        ' '.join('-hdr "'+header+'"' for header in headers)+' -body {'+body+'}'])


def request(path, body, *, headers=(), method='GET', cache=None, status=200):
    return '\n'.join(['txreq -req '+method+' -url "'+path+'" -hdr "Host: example.test" '+
                      ' '.join('-hdr "'+header+'"' for header in headers),
                      'rxresp', 'expect resp.status == '+str(status), 'expect resp.body == {'+body+'}',
                      *(['expect resp.http.X-Hestia-Varnish == "'+cache+'"'] if cache else [])])


@unittest.skipUnless(shutil.which('varnishtest'), 'native varnishtest is required')
class ProfileCompatibility(unittest.TestCase):
    def run_policy(self, profile, responses, requests):
        origin = '\n'.join(responses).removeprefix('accept\n')
        content = ('varnishtest "Application-independent '+profile+'"\nserver s1 {\n'+origin+
                   '\n} -start\nvarnish v1 -vcl {\n'+program(profile)+
                   '\n} -start\nclient c1 {\n'+'\n'.join(requests)+'\n} -run\nserver s1 -wait\n')
        with tempfile.TemporaryDirectory(prefix='varnish-profile-') as folder:
            path = Path(folder)/'compatibility.vtc'
            path.write_text(content, encoding='utf-8')
            result = subprocess.run(['varnishtest', '-t', '15', str(path)], capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_plain_html_and_literal_esi_without_opt_in(self):
        body = '<html>Plain PHP or WordPress <esi:include src="/not-requested"/></html>'
        for profile in PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile, [response('/index.php', body, headers=['Content-Type: text/html'])],
                    [request('/index.php', body, cache='MISS'), request('/index.php', body, cache='HIT')])

    def test_exact_accept_and_native_vary_keep_json_xml_text_and_images_separate(self):
        variants = [('application/json', 'application/json', '{"ok":true}'),
                    ('application/xml', 'application/xml', '<ok/>'),
                    ('text/plain', 'text/plain', 'plain'),
                    ('image/avif;q=0,image/webp;q=0.5', 'image/webp', 'webp'),
                    (None, 'text/plain', 'no-accept')]
        for profile in PROFILES:
            with self.subTest(profile=profile):
                responses, requests = [], []
                for accept, mime, body in variants:
                    headers = ['Accept: '+accept] if accept is not None else []
                    expected = '"'+accept+'"' if accept is not None else '<undef>'
                    responses.append(response('/negotiate.php', body, headers=['Content-Type: '+mime, 'Vary: Accept'],
                                              expect=['expect req.http.Accept == '+expected]))
                    requests.extend([request('/negotiate.php', body, headers=headers, cache='MISS'),
                                     request('/negotiate.php', body, headers=headers, cache='HIT')])
                requests.append(request('/negotiate.php', '{"ok":true}', headers=['Accept: application/json'], cache='HIT'))
                self.run_policy(profile, responses, requests)

    def test_sessions_authorization_and_post_reach_plain_origin(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                responses, requests = [], []
                for header, assertion, method in [('Cookie: PHPSESSID=alice', 'expect req.http.Cookie == "PHPSESSID=alice"', 'GET'),
                    ('Authorization: Bearer example-test', 'expect req.http.Authorization == "Bearer example-test"', 'GET'),
                    ('Content-Type: application/json', 'expect req.method == "POST"', 'POST')]:
                    for n in range(2):
                        body = method+str(n)
                        responses.append(response('/private.php', body, expect=[assertion]))
                        requests.append(request('/private.php', body, headers=[header], method=method, cache='BYPASS'))
                self.run_policy(profile, responses, requests)

    def test_origin_private_cookies_and_errors_are_delivered_without_caching(self):
        for profile in PROFILES:
            with self.subTest(profile=profile):
                responses, requests = [], []
                for path, policy, headers, status in [('/private', 'private, no-store', [], 200),
                    ('/cookie', 'public, max-age=120', ['Set-Cookie: PHPSESSID=example'], 200),
                    ('/missing', 'public, max-age=120', [], 404), ('/error', 'public, max-age=120', [], 500)]:
                    for n in range(2):
                        body = path+str(n)
                        responses.append(response(path, body, policy=policy, headers=headers, status=status))
                        requests.append(request(path, body, status=status))
                self.run_policy(profile, responses, requests)

    def test_woocommerce_paths_work_without_woocommerce_or_ultracache(self):
        for profile in ['woocommerce', 'ultracache']:
            with self.subTest(profile=profile):
                responses, requests = [], []
                for path in ['/cart/', '/checkout/', '/my-account/', '/?add-to-cart=42']:
                    for n in range(2):
                        body = 'plain PHP '+str(n)
                        responses.append(response(path, body))
                        requests.append(request(path, body, cache='BYPASS'))
                self.run_policy(profile, responses, requests)

    def test_generic_application_can_use_esi_without_ultracache(self):
        self.run_policy('ultracache', [
            response('/parent', '<html>before<esi:include src="/fragment"/>after</html>',
                     headers=['Content-Type: text/html', 'Surrogate-Control: ESI/1.0'],
                     expect=['expect req.http.Surrogate-Capability == "varnish=ESI/1.0"']),
            response('/fragment', 'fragment', headers=['Content-Type: text/plain'])],
            [request('/parent', '<html>beforefragmentafter</html>', cache='MISS'),
             request('/parent', '<html>beforefragmentafter</html>', cache='HIT')])

    def test_missing_shared_parent_approval_delivers_uncached_origin(self):
        cookie = 'woocommerce_items_in_cart=1; ultracache_esi_optin=1'
        self.run_policy('ultracache', [response('/plain.php', 'visitor-'+str(n), expect=[
            'expect req.http.Cookie == "woocommerce_items_in_cart=1"']) for n in range(2)],
            [request('/plain.php', 'visitor-'+str(n), headers=['Cookie: '+cookie]) for n in range(2)])


if __name__ == '__main__':
    unittest.main()
