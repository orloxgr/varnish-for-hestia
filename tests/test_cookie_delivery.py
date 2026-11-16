"""Read real HTTP header fields: cookie commas are not header separators."""
import contextlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest

from test_profile_compatibility import program
from cookie_catalogue import load_catalogue
POLICY_VERSION = load_catalogue()['version']


@contextlib.contextmanager
def proxy(profile, respond, transform=None, delivery=None):
    """An isolated origin and daemon; never load/restart the installed service."""
    class Origin(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def do_GET(self):
            body, headers = respond(self.path, self.headers)
            body = body.encode()
            self.send_response(200)
            if not any(name.lower() == 'content-type' for name, _ in headers):
                self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Connection', 'close')
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    origin = ThreadingHTTPServer(('127.0.0.1', 0), Origin)
    thread = threading.Thread(target=origin.serve_forever, daemon=True)
    thread.start()
    daemon = None
    try:
        with tempfile.TemporaryDirectory(prefix='hvh-cookie-http-') as folder:
            root = Path(folder)
            source = program(profile, cookie_delivery=delivery).replace('${s1_port}', str(origin.server_port))
            if transform is not None:
                source = transform(source)
            (root / 'policy.vcl').write_text(source)
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            with (root / 'daemon.log').open('w+') as log:
                daemon = subprocess.Popen([
                    'varnishd', '-F', '-j', 'none', '-n', str(root / 'instance'),
                    '-f', str(root / 'policy.vcl'), '-a', '127.0.0.1:' + str(port),
                    '-T', 'none', '-s', 'malloc,16m',
                    '-p', 'feature=+esi_ignore_other_elements'], stdout=log, stderr=log)
                deadline = time.monotonic() + 15
                while True:
                    if daemon.poll() is not None:
                        log.seek(0)
                        raise AssertionError('Isolated Varnish failed: ' + log.read())
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=.2):
                            break
                    except OSError:
                        if time.monotonic() >= deadline:
                            log.seek(0)
                            raise AssertionError('Isolated Varnish did not start: ' + log.read())
                        time.sleep(.05)

                def get(path, cookie=None, extra=None):
                    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
                    try:
                        headers = {'Host': 'example.test', 'X-Forwarded-Proto': 'https'}
                        if cookie is not None:
                            headers['Cookie'] = cookie
                        if extra is not None:
                            headers.update(extra)
                        connection.request('GET', path, headers=headers)
                        response = connection.getresponse()
                        fields = response.getheaders()
                        body = response.read().decode()
                        return response.status, fields, body
                    finally:
                        connection.close()

                try:
                    yield get
                finally:
                    daemon.terminate()
                    daemon.wait(timeout=10)
                    daemon = None
    finally:
        if daemon is not None:
            daemon.terminate()
            daemon.wait(timeout=10)
        origin.shutdown()
        origin.server_close()
        thread.join(timeout=5)


def cookies(fields):
    return [value for name, value in fields if name.lower() == 'set-cookie']


ENABLED = {'fbp': {'enabled': True}}


@unittest.skipUnless(shutil.which('varnishd'), 'Native varnishd required')
class NativeCookieDelivery(unittest.TestCase):
    def test_two_new_visitors_share_html_with_different_cookies_and_keep_existing(self):
        calls = []
        def origin(path, headers):
            calls.append(dict(headers))
            return '<html>same-public-page</html>', [('Cache-Control','public, max-age=120')]
        with proxy('basic', origin, delivery=ENABLED) as get:
            minted = []
            for expected in ('MISS','HIT'):
                status, fields, body = get('/page', 'cmplz_marketing=allow')
                self.assertEqual((status,body), (200,'<html>same-public-page</html>'))
                self.assertEqual(dict(fields)['X-Cache'], expected)
                self.assertEqual(dict(fields)['X-Cache-Cookie-Delivery'], 'fbp:independent')
                self.assertEqual(dict(fields)['Cache-Control'], 'private, no-store')
                self.assertEqual(dict(fields)['Surrogate-Control'], 'no-store')
                emitted = cookies(fields)
                self.assertEqual(len(emitted), 1)
                self.assertRegex(emitted[0], r'^_fbp=fb\.1\.[0-9]{13}\.[0-9]+; Max-Age=7776000; Path=/; SameSite=Lax; Secure$')
                minted.append(emitted[0].split(';')[0])
            self.assertNotEqual(*minted)
            _, fields, _ = get('/page','cmplz_marketing=allow; _fbp=')
            self.assertEqual(dict(fields)['X-Cache'], 'HIT')
            self.assertEqual(dict(fields)['X-Cache-Cookie-Delivery'],'fbp:independent')
            self.assertEqual(len(cookies(fields)),1)
            _, fields, _ = get('/page', 'cmplz_marketing=allow; ' + minted[0])
            self.assertEqual(dict(fields)['X-Cache'], 'HIT')
            self.assertEqual(cookies(fields), [])
            self.assertEqual(dict(fields)['Cache-Control'], 'public, max-age=120')
            self.assertNotIn('Surrogate-Control',dict(fields))
            self.assertEqual(dict(fields)['X-Cache-Cookie-Delivery'], 'fbp:existing-preserved')
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]['Cookie'], 'cmplz_marketing=allow')
            self.assertFalse(any(name.lower().startswith('x-scp-fbp-') for name in calls[0]))

    def test_consent_unknown_accept_reject_revoke_and_revisit(self):
        calls = []
        def origin(path, headers):
            calls.append(path)
            return 'public', [('Cache-Control','public, max-age=120')]
        with proxy('basic', origin, delivery=ENABLED) as get:
            for consent, allowed in [(None,False), ('allow',True), ('deny',False),
                                     ('allow',True), ('deny',False), (None,False)]:
                _, fields, _ = get('/page', 'cmplz_marketing='+consent if consent else None)
                self.assertEqual(bool(cookies(fields)), allowed)
            self.assertEqual(calls, ['/page'])

    def test_actual_provider_hold_prevents_new_cookie_without_bypassing_public_html(self):
        def origin(path, headers):
            return 'public', [('Cache-Control','public, max-age=120')]
        with proxy('basic', origin, delivery=ENABLED) as get:
            get('/page')
            _, fields, _ = get('/page','cmplz_marketing=allow; wc_facebook_signals_state=held')
            self.assertEqual(dict(fields)['X-Cache'],'HIT')
            self.assertEqual(cookies(fields),[])
            self.assertEqual(dict(fields)['X-Cache-Cookie-Delivery'],'fbp:provider-held')
            self.assertEqual(dict(fields)['X-Cache-Cookie-Names'],'wc_facebook_signals_state')
            self.assertEqual(dict(fields)['Cache-Control'],'public, max-age=120')

    def test_basic_respects_an_available_authoritative_provider_endpoint(self):
        def origin(path, headers):
            return 'public', [('Cache-Control','public, max-age=120'),
                ('X-UltraCache-Cookie-Policy',POLICY_VERSION),
                ('X-UltraCache-Cookie-Delivery','provider-endpoint-fbp'), ('X-UltraCache-Cacheable','1')]
        with proxy('basic', origin, delivery=ENABLED) as get:
            for expected in ('MISS','HIT'):
                _, fields, _ = get('/page','cmplz_marketing=allow')
                self.assertEqual(dict(fields)['X-Cache'],expected)
                self.assertEqual(cookies(fields),[])
                self.assertEqual(dict(fields)['X-Cache-Cookie-Delivery'],'fbp:provider-endpoint')

    def test_origin_renewals_deletions_and_other_cookie_fields_win_unchanged(self):
        def origin(path, headers):
            values = [
                '_fbp=provider-normalized; Path=/; Max-Age=7776000; Domain=example.test; Secure; SameSite=Lax',
                'session=private; Path=/account; HttpOnly; Secure; SameSite=Strict',
                'obsolete=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/',
                '_fbp=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/legacy']
            return 'private-response', [('Cache-Control','public, max-age=120'),
                                       *[('Set-Cookie',value) for value in values]]
        with proxy('basic', origin, delivery=ENABLED) as get:
            for cookie in ('cmplz_marketing=allow', 'cmplz_marketing=allow; _fbp=existing'):
                _, fields, _ = get('/page', cookie)
                self.assertEqual(dict(fields)['X-Cache'], 'PASS')
                self.assertEqual(dict(fields)['X-Cache-Cookie-Delivery'], 'fbp:origin-provider')
                self.assertEqual(dict(fields)['Cache-Control'],'private, no-store')
                self.assertEqual(dict(fields)['Surrogate-Control'],'no-store')
                self.assertEqual(cookies(fields), [value for name,value in origin('',{})[1] if name=='Set-Cookie'])

    def test_browser_headers_cannot_enable_delivery_or_approve_ultracache_objects(self):
        def origin(path, headers):
            self.assertIsNone(headers.get('X-UltraCache-Cookie-Delivery'))
            return 'public', [('Cache-Control','public, max-age=120')]
        forged = {'X-SCP-Fbp-Enabled':'1', 'X-SCP-Fbp-Consent':'1',
                  'X-SCP-Fbp-New':'_fbp=forged', 'X-UltraCache-Cookie-Delivery':'proxy-fbp',
                  'X-UltraCache-Cookie-Policy':POLICY_VERSION}
        for profile, config in [('basic',None), ('ultracache',ENABLED)]:
            with self.subTest(profile=profile), proxy(profile, origin, delivery=config) as get:
                for expected in ('MISS','HIT'):
                    _, fields, _ = get('/page','cmplz_marketing=allow',forged)
                    self.assertEqual(dict(fields)['X-Cache'], expected)
                    self.assertEqual(cookies(fields), [])

    def test_ultracache_requires_current_origin_policy_and_proxy_ownership(self):
        for ownership, version, allowed in [('proxy-fbp',POLICY_VERSION,True),
                                             ('provider-endpoint-fbp',POLICY_VERSION,False),
                                             ('proxy-fbp','old-policy',False)]:
            def origin(path, headers):
                return 'public', [('Cache-Control','public, max-age=120'),
                    ('X-UltraCache-Cookie-Policy',version), ('X-UltraCache-Cookie-Delivery',ownership),
                    ('X-UltraCache-Cacheable','1')]
            with self.subTest(owner=ownership,version=version), proxy('ultracache', origin, delivery=ENABLED) as get:
                for expected in ('MISS','HIT'):
                    _, fields, _ = get('/page','cmplz_marketing=allow')
                    self.assertEqual(dict(fields)['X-Cache'], expected)
                    self.assertEqual(bool(cookies(fields)), allowed)

    def test_private_and_non_html_responses_never_trigger_issuance(self):
        for profile in ('basic','ultracache'):
            def origin(path, headers):
                return 'origin', [('Cache-Control','private, no-store' if path=='/private' else 'public, max-age=120'),
                    ('Content-Type','application/json' if path=='/json' else 'text/html'),
                    ('X-UltraCache-Cookie-Policy',POLICY_VERSION),
                    ('X-UltraCache-Cookie-Delivery','proxy-fbp'), ('X-UltraCache-Cacheable','1')]
            with self.subTest(profile=profile), proxy(profile, origin, delivery=ENABLED) as get:
                for path in ('/private','/json','/wp-admin/'):
                    _, fields, _ = get(path,'cmplz_marketing=allow')
                    self.assertEqual(cookies(fields), [])

    def test_public_only_esi_keeps_public_response_caching(self):
        calls = []
        def origin(path, headers):
            calls.append(path)
            if path == '/fragment':
                return 'public-fragment', [('Cache-Control','public, max-age=120')]
            return '<html><esi:include src="/fragment"/></html>', [
                ('Cache-Control','public, max-age=120'), ('Surrogate-Control','ESI/1.0'),
                ('X-UltraCache-ESI-Shared-Parent','1'), ('X-UltraCache-ESI-Private-Count','0')]
        with proxy('ultracache', origin) as get:
            for expected in ('MISS','HIT'):
                _, fields, body = get('/public-parent')
                self.assertEqual(body,'<html>public-fragment</html>')
                self.assertEqual(dict(fields)['X-Cache'],expected)
                self.assertEqual(dict(fields)['Cache-Control'],'public, max-age=120')
                self.assertNotEqual(dict(fields).get('Surrogate-Control'),'no-store')
            self.assertEqual(calls,['/public-parent','/fragment'])


if __name__ == '__main__':
    unittest.main()
