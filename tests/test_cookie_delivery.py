"""Read real HTTP header fields: cookie commas are not header separators."""
import contextlib
import http.client
import os
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


def policy_for_choices(profile,choices):
    return program(profile,cookie_policies=choices,other_profile=profile)


@contextlib.contextmanager
def proxy(profile, respond, transform=None, delivery=None, policies=None, management=False, site_settings=None, ports=(0,0),other_profile=None,daemon_parameters=(),allow_post=False):
    """An isolated origin and daemon; never load/restart the installed service."""
    class Origin(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def do_GET(self):
            result = respond(self.path, self.headers)
            if result is None:
                self.close_connection = True # owned upstream EOF/fetch-error fixture
                return
            status, body, headers = result if len(result)==3 else (200,*result)
            if isinstance(body,str):body = body.encode()
            streaming = not isinstance(body,bytes)
            self.send_response(status)
            if not any(name.lower() == 'content-type' for name, _ in headers):
                self.send_header('Content-Type', 'text/html')
            if not streaming and not any(name.lower() == 'content-length' for name, _ in headers):
                self.send_header('Content-Length', str(len(body)))
            self.send_header('Connection', 'close')
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            try:
                if streaming:
                    for chunk in body:
                        self.wfile.write(chunk);self.wfile.flush()
                else:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):
                pass # abandoned client streaming fixture
            finally:
                if streaming and hasattr(body,'close'):body.close()

        def log_message(self, *args):
            pass

    if allow_post:Origin.do_POST=Origin.do_GET
    origin = ThreadingHTTPServer(('127.0.0.1', ports[0]), Origin)
    thread = threading.Thread(target=origin.serve_forever, daemon=True)
    thread.start()
    daemon = None
    try:
        with tempfile.TemporaryDirectory(prefix='hvh-cookie-http-') as folder:
            root = Path(folder)
            source = program(profile, cookie_delivery=delivery, cookie_policies=policies, site_settings=site_settings,other_profile=other_profile).replace('${s1_port}', str(origin.server_port))
            module = os.environ.get('SCP_TEST_COOKIE_MODULE')
            if module:
                source = source.replace('import cookie_handoff;', 'import cookie_handoff from "'+module+'";')
            if transform is not None:
                source = transform(source)
            (root / 'policy.vcl').write_text(source)
            with socket.socket() as reservation:
                reservation.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                reservation.bind(('127.0.0.1', ports[1]))
                port = reservation.getsockname()[1]
            admin_args=['-T','none']
            if management:
                with socket.socket() as reservation:
                    reservation.bind(('127.0.0.1',0));admin_port=reservation.getsockname()[1]
                secret=root/'admin.secret';secret.write_text('owned-test-only');secret.chmod(0o600)
                admin_args=['-T','127.0.0.1:'+str(admin_port),'-S',str(secret)]
            with (root / 'daemon.log').open('w+') as log:
                daemon = subprocess.Popen([
                    'varnishd', '-F', '-j', 'none', '-n', str(root / 'instance'),
                    '-f', str(root / 'policy.vcl'), '-a', '127.0.0.1:' + str(port),
                    *admin_args, '-s', 'malloc,16m',
                    '-p', 'feature=+esi_ignore_other_elements',
                    *[arg for value in daemon_parameters for arg in ('-p',value)]], stdout=log, stderr=log)
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

                get.endpoint = ('127.0.0.1', port)
                # Raw HTTP regressions must use the same adapter entry headers.
                get.request_headers = {'Host': 'example.test', 'X-Forwarded-Proto': 'https'}
                get.origin_port = origin.server_port
                get.source = source
                get.instance = root/'instance'
                def stop_origin():
                    origin.shutdown();origin.server_close();thread.join(timeout=5)
                get.stop_origin = stop_origin
                if management:
                    def adm(*args):
                        result=subprocess.run(['varnishadm','-T','127.0.0.1:'+str(admin_port),'-S',str(secret),*args],capture_output=True,text=True)
                        if result.returncode:raise AssertionError(result.stdout+result.stderr)
                        return result.stdout
                    get.adm=adm
                    def activate(name,source):
                        path=root/(name+'.vcl');path.write_text(source)
                        for args in [('vcl.load',name,str(path)),('vcl.use',name)]:
                            result=subprocess.run(['varnishadm','-T','127.0.0.1:'+str(admin_port),
                                '-S',str(secret),*args],capture_output=True,text=True)
                            if result.returncode:raise AssertionError(result.stdout+result.stderr)
                    get.activate=activate
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


@unittest.skipUnless(shutil.which('varnishd'), 'Native varnishd required')
class NativeCookieDelivery(unittest.TestCase):
    def test_legacy_enabled_issuer_and_approval_headers_cannot_mint_identifiers(self):
        for profile in ('basic', 'ultracache'):
            calls = []
            def origin(path, headers):
                calls.append(dict(headers))
                return 'public', [('Cache-Control', 'public, max-age=120'),
                    ('X-UltraCache-Cookie-Policy', POLICY_VERSION),
                    ('X-UltraCache-Cookie-Delivery', 'proxy-fbp'), ('X-UltraCache-Cacheable', '1')]
            with self.subTest(profile=profile), proxy(profile, origin,
                    delivery={'fbp': {'enabled': True}}) as get:
                for expected, cookie in [('MISS', 'cmplz_marketing=allow'),
                        ('HIT', 'cmplz_marketing=allow; _fbp=visitor-a'),
                        ('HIT', 'cmplz_marketing=allow; _fbp=visitor-b')]:
                    _, fields, body = get('/page', cookie)
                    self.assertEqual(body, 'public')
                    self.assertEqual(dict(fields)['X-Cache'], expected)
                    self.assertEqual(cookies(fields), [])
                    self.assertNotIn('X-Cache-Cookie-Delivery', dict(fields))
                self.assertEqual(len(calls), 1)

    def test_original_provider_fields_are_preserved_without_replay_for_any_name(self):
        values = ['_fbp=provider-normalized; Path=/; Secure; SameSite=Lax',
            'another_provider=unique; Path=/; HttpOnly; Secure',
            'obsolete=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/']
        for profile in ('basic', 'ultracache'):
            calls = []
            def origin(path, headers):
                calls.append(headers.get('Cookie'))
                return 'provider response', [('Cache-Control', 'public, max-age=120'),
                    *[('Set-Cookie', value) for value in values]]
            with self.subTest(profile=profile), proxy(profile, origin) as get:
                for identifier in ('visitor-a', 'visitor-b'):
                    _, fields, _ = get('/page', '_fbp=' + identifier)
                    self.assertEqual(dict(fields)['X-Cache'], 'PASS')
                    self.assertEqual(cookies(fields), values)
                    self.assertEqual(dict(fields)['Cache-Control'], 'private, no-store')
                self.assertEqual(calls, ['_fbp=visitor-a', '_fbp=visitor-b'])

    def test_fbp_obeys_common_site_variant_and_private_choices(self):
        from test_cookie_admin import settings
        for profile in ('basic', 'ultracache'):
            for action in ('variant', 'private'):
                def origin(path, headers):
                    return 'public', [('Cache-Control', 'public, max-age=120')]
                with self.subTest(profile=profile, action=action), proxy(profile, origin,
                        policies=settings('_fbp', action)) as get:
                    expected = ('MISS', 'MISS', 'HIT') if action == 'variant' else ('PASS',) * 3
                    for identifier, result in zip(('a', 'b', 'a'), expected):
                        _, fields, _ = get('/page', '_fbp=' + identifier)
                        self.assertEqual(dict(fields)['X-Cache'], result)
                        self.assertEqual(cookies(fields), [])

    def test_public_only_esi_keeps_public_response_caching(self):
        calls = []
        def origin(path, headers):
            calls.append(path)
            if path == '/fragment':
                return 'public-fragment', [('Cache-Control', 'public, max-age=120')]
            return '<html><esi:include src="/fragment"/></html>', [
                ('Cache-Control', 'public, max-age=120'), ('Surrogate-Control', 'ESI/1.0'),
                ('X-UltraCache-ESI-Shared-Parent', '1'), ('X-UltraCache-ESI-Private-Count', '0')]
        with proxy('ultracache', origin) as get:
            for expected in ('MISS', 'HIT'):
                _, fields, body = get('/public-parent')
                self.assertEqual(body, '<html>public-fragment</html>')
                self.assertEqual(dict(fields)['X-Cache'], expected)
                self.assertEqual(dict(fields)['Cache-Control'], 'public, max-age=120')
            self.assertEqual(calls, ['/public-parent', '/fragment'])


if __name__ == '__main__':
    unittest.main()
