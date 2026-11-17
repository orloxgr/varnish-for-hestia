"""Exact signed wire protocol; metadata changes do not change effective scope."""
import http.server
import hashlib
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))
import cookie_control as control
from test_cookie_admin import settings


class CookieControl(unittest.TestCase):
    def test_contract_covers_private_selectors_but_not_shadowed_private_rules(self):
        connection={'enabled':True,'url':'https://example.test'+control.PATH}
        central=settings('membership','private')
        self.assertEqual(control.cache_contract(connection,'example.test',central=central),
            control.effective_digest('example.test',control.snapshot(central)))
        self.assertEqual(control.cache_contract(connection,'example.test',central=central,
            site=settings('membership','automatic')),'')

    def test_inactive_url_does_not_block_work_but_enabling_checks_ownership(self):
        value={'enabled':False,'url':'https://old.example'+control.PATH}
        self.assertEqual(control.integration(value,'example.test'),value)
        with self.assertRaises(ValueError):control.integration(dict(value,enabled=True),'example.test')
        self.assertFalse(control.integration({'enabled':False,'url':''},'example.test')['enabled'])

    def test_unsigned_body_is_rejected_without_reading_it(self):
        class Response:
            code = 200
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, *args): raise AssertionError('Unsigned body must not be read')
        class Opener:
            def open(self, request): return Response()
        client = control.Client({'enabled': True, 'url': 'https://example.test'+control.PATH},
                                'example.test', 'fixture-token', control.snapshot())
        with patch.object(control.urllib.request, 'build_opener', return_value=Opener()), \
                self.assertRaisesRegex(control.ControlError, 'authentication failed'):
            client.call('status')

    def test_owned_alias_is_the_signed_application_host(self):
        client = control.Client({'enabled': True, 'url': 'https://www.example.test'+control.PATH},
                                'example.test', 'fixture-token', control.snapshot(), aliases=['www.example.test'])
        self.assertEqual(client.host, 'www.example.test')
        self.assertEqual(client.target_digest, control.effective_digest('www.example.test', control.snapshot()))

    def test_digest_ignores_descriptions_but_not_variant_semantics(self):
        value = settings('currency', 'variant')
        before = control.effective_digest('example.test', control.snapshot(site=value))
        value['rules'][0]['description'] = 'Updated description'
        self.assertEqual(before, control.effective_digest('example.test', control.snapshot(site=value)))
        value['rules'][0]['action'] = 'shared'
        self.assertNotEqual(before, control.effective_digest('example.test', control.snapshot(site=value)))

    def test_configuration_cannot_fetch_other_hosts_or_paths(self):
        for url in ['https://elsewhere.test'+control.PATH, 'https://example.test/wp-config.php',
                    'https://user:password@example.test'+control.PATH, 'https://example.test'+control.PATH+'?secret=1']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                control.integration({'enabled': True, 'url': url}, 'example.test')

    def test_exact_native_requests_and_authenticated_responses(self):
        token = 'fixture-token-no-production-credential'
        policy = control.snapshot(site=settings('currency', 'variant'))
        active = control.effective_digest('example.test', control.snapshot())
        target = control.effective_digest('example.test', policy)
        operations = []
        tamper = False
        rollback_state='restored'
        rollback_override=None
        failure=None
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                nonlocal active
                body = self.rfile.read(int(self.headers['Content-Length']))
                data = json.loads(body)
                assert self.path == control.PATH
                assert self.headers[control.HEADER] == control.request_signature(token, body, 'example.test', data['requestId'], data['expires'])
                operation = data['operation']; operations.append(operation)
                if operation == 'commit':
                    active = target
                elif operation == 'rollback':
                    active = rollback_override or data['baseDigest']
                result = dict(ok=True, protocol=1, operation=operation, requestId=data['requestId'],
                              host=data['host'], activeDigest=active, targetDigest=target)
                if operation=='rollback':result['rollbackState']=rollback_state
                status=500 if failure else 200
                if failure:result.update(ok=False,**failure)
                raw = control.canonical(result)
                self.send_response(status)
                self.send_header(control.HEADER, control.response_signature(token, status, data['requestId'], raw))
                self.send_header(control.DIGEST_HEADER, hashlib.sha256(raw).hexdigest())
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers(); self.wfile.write(raw.replace(b'"ok":true', b'"ok":null') if tamper else raw)
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        client = control.Client({'enabled': True, 'url': 'https://example.test'+control.PATH}, 'example.test', token, policy)
        # Only the test destination changes; signed host/path/body remain real.
        client.url = 'http://127.0.0.1:' + str(server.server_port) + control.PATH
        for operation in ('status', 'prepare', 'commit', 'rollback'):
            client.call(operation)
        self.assertEqual(operations, ['status', 'prepare', 'commit', 'rollback'])
        rollback_override=hashlib.sha256(b'newer actual policy').hexdigest()
        for rollback_state in ('not-applied','superseded'):
            result=client.call('rollback')
            self.assertEqual(result['activeDigest'],rollback_override)
        rollback_state='restored'
        with self.assertRaisesRegex(control.ControlError,'did not restore'):
            client.call('rollback')
        failure={'stage':'commit','code':'ultracache_html_retirement_failed','message':'Private visitor or credential text must not be echoed'}
        with self.assertRaisesRegex(control.ControlError,'commit.*500; ultracache_html_retirement_failed') as caught:
            client.call('commit')
        self.assertNotIn(failure['message'],str(caught.exception))
        failure['code']='unsafe/private/value'
        with self.assertRaises(control.ControlError) as caught:client.call('commit')
        self.assertNotIn(failure['code'],str(caught.exception))
        failure=None
        tamper = True
        with self.assertRaisesRegex(control.ControlError, 'authentication failed'):
            client.call('status')
