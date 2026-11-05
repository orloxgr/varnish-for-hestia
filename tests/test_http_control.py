"""Exercise generated product VCL against real Varnish and HTTP origins."""
import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from vcl import quoted, render


TOKEN = 'A' * 32


def program(profile='ultracache'):
    def site(identity, aliases=()):
        return dict(id=identity * 32, aliases=list(aliases), profile=profile, token=TOKEN,
                    enabled=True, suspended=False, custom_recv='', custom_backend_response='')
    owner = dict(enabled=True, suspended=False, package='default', sites={
        'example.test': site('a', ['www.example.test']), 'second.test': site('b')})
    other = copy.deepcopy(owner)
    other['sites'] = {'foreign.test': site('c')}
    return render({'owners': {'alice': owner, 'bob': other}},
                  {'origin_ip': '127.0.0.1', 'origin_port': 8080}).replace('"8080"', '"${s1_port}"', 1)


def origin(path, body, host='example.test', mime='text/html', headers=(), expect=()):
    return '\n'.join(['accept', 'rxreq', f'expect req.url == "{path}"',
                      f'expect req.http.host == "{host}"', *expect,
                      'txresp -hdr "Connection: close" -hdr "Cache-Control: public, max-age=600" '
                      f'-hdr "Content-Type: {mime}" ' +
                      ' '.join('-hdr {' + h + '}' for h in headers) + f' -body {{{body}}}'])


def get(path, body, host='example.test', cache=None, headers=()):
    return '\n'.join([f'txreq -url "{path}" -hdr "Host: {host}" ' +
                      ' '.join('-hdr {' + h + '}' for h in headers), 'rxresp',
                      'expect resp.status == 200', f'expect resp.body == {{{body}}}',
                      *([f'expect resp.http.X-Hestia-Varnish == "{cache}"'] if cache else [])])


def control(path='/', method='BAN', expression=None, status=200, host='example.test',
            token=TOKEN, headers=(), response_headers=()):
    fields = [f'Host: {host}', f'X-UltraCache-Token: {token}', *headers]
    if expression is not None:
        fields.append('X-Ban-Expression: ' + expression)
    return '\n'.join([f'txreq -req {method} -url "{path}" ' +
                      ' '.join('-hdr {' + h + '}' for h in fields), 'rxresp',
                      f'expect resp.status == {status}', *response_headers])


def contract(operation, expression=None, path='/__ultracache-vcl-contract-v2', status=200, **kwargs):
    headers = ['X-UltraCache-Contract: 2', 'X-UltraCache-Operation: ' + operation]
    if expression is not None:
        headers.append('X-UltraCache-Object-Expression: ' + expression)
    expected = ['expect resp.http.X-UltraCache-VCL-Contract == "2"',
                'expect resp.http.X-UltraCache-VCL-Adapter == "ultracache-hestia-v2"',
                'expect resp.http.X-UltraCache-VCL-Auth == "token"',
                f'expect resp.http.X-UltraCache-VCL-Operation == "{operation}"',
                'expect resp.http.X-UltraCache-VCL-Result == "' + ('ok' if status == 200 else 'error') + '"']
    return control(path, method='PURGE', status=status, headers=headers,
                   response_headers=expected, **kwargs)


@unittest.skipUnless(shutil.which('varnishtest'), 'native varnishtest is required')
class HTTPControl(unittest.TestCase):
    def run_vcl(self, responses, requests, profile='ultracache'):
        source = ('varnishtest "Scoped HTTP invalidation"\nserver s1 {\n' +
                  '\n'.join(responses).removeprefix('accept\n') +
                  '\n} -start\nvarnish v1 -vcl {\n' + program(profile) +
                  '\n} -start\nclient c1 {\n' + '\n'.join(requests) +
                  '\n} -run\nserver s1 -wait\n')
        with tempfile.TemporaryDirectory(prefix='hvh-control-') as directory:
            path = Path(directory) / 'control.vtc'
            path.write_text(source)
            result = subprocess.run(['varnishtest', '-t', '15', str(path)],
                                    capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_portable_exact_ban_preserves_other_urls_aliases_and_tenants(self):
        objects = [('/target?x=1', 'target'), ('/control', 'control'),
                   ('/target?x=1', 'alias', 'www.example.test'),
                   ('/target?x=1', 'same-owner', 'second.test'),
                   ('/target?x=1', 'other-owner', 'foreign.test')]
        initial = [get(*item, cache='MISS') for item in objects]
        self.run_vcl([*(origin(*item) for item in objects), origin('/target?x=1', 'new')],
                     [*initial, *(get(*item, cache='HIT') for item in objects),
                      control(expression=r'req.http.host == example.test && req.url ~ ^/target\?x\=1$'),
                      *(get(*item, cache='HIT') for item in objects[1:]),
                      get('/target?x=1', 'new', cache='MISS')])

    def test_portable_batch_ban_keeps_unselected_control(self):
        self.run_vcl([origin('/one', 'one'), origin('/two', 'two'), origin('/control', 'control'),
                      origin('/one', 'one-new'), origin('/two', 'two-new')],
                     [get('/one', 'one'), get('/two', 'two'), get('/control', 'control'),
                      control(expression=r'req.http.host == example.test && req.url ~ ^(?:/one|/two)$'),
                      get('/control', 'control', cache='HIT'),
                      get('/one', 'one-new', cache='MISS'), get('/two', 'two-new', cache='MISS')])

    def test_contract_capabilities_does_not_invalidate(self):
        self.run_vcl([origin('/control', 'control')],
                     [get('/control', 'control'), contract('capabilities'),
                      'expect resp.http.X-UltraCache-VCL-Capabilities == "exact-purge,exact-ban,batch-ban,html-ban,host-ban,soft-purge"',
                      get('/control', 'control', cache='HIT')])

    def test_contract_exact_and_batch_decode_generated_quoted_operands(self):
        self.run_vcl([origin('/one?x=1', 'one'), origin('/two', 'two'), origin('/control', 'control'),
                      origin('/one?x=1', 'new-one'), origin('/one?x=1', 'newer-one'), origin('/two', 'new-two')],
                     [get('/one?x=1', 'one'), get('/two', 'two'), get('/control', 'control'),
                      contract('exact-ban', r'obj.http.X-Cache-Object-Host == "example.test" && obj.http.X-Cache-Object-URL ~ "^\\/one\\?x\\=1$"'),
                      get('/control', 'control', cache='HIT'), get('/two', 'two', cache='HIT'),
                      get('/one?x=1', 'new-one', cache='MISS'),
                      contract('batch-ban', r'obj.http.X-Cache-Object-Host == "example.test" && obj.http.X-Cache-Object-URL ~ "^(?:\\/one\\?x\\=1|\\/two)$"'),
                      get('/control', 'control', cache='HIT'),
                      get('/one?x=1', 'newer-one', cache='MISS'), get('/two', 'new-two', cache='MISS')])

    def test_long_contract_exact_ban_invalidates_only_selected_object(self):
        for query_bytes in (2400, 3400):
            with self.subTest(query_bytes=query_bytes):
                path = '/target?q=' + 'x' * query_bytes
                expression = ('obj.http.X-Cache-Object-Host == "example.test" && '
                              'obj.http.X-Cache-Object-URL ~ ' + quoted('^' + re.escape(path) + '$'))
                objects = [(path, 'old'), ('/control', 'control'),
                           (path, 'alias', 'www.example.test'),
                           (path, 'foreign', 'foreign.test')]
                self.run_vcl([*(origin(*item) for item in objects), origin(path, 'new')],
                             [*(get(*item, cache='MISS') for item in objects),
                              *(get(*item, cache='HIT') for item in objects),
                              contract('exact-ban', expression),
                              *(get(*item, cache='HIT') for item in objects[1:]),
                              get(path, 'new', cache='MISS'), get(path, 'new', cache='HIT')])

    def test_long_escaped_contract_batch_ban_preserves_scope(self):
        paths = ['/one?q=' + 'a.b+c-' * 140, '/two?q=' + 'd.e+f-' * 140]
        pattern = '^(?:' + '|'.join(re.escape(path) for path in paths) + ')$'
        expression = ('obj.http.X-Cache-Object-Host == "example.test" && '
                      'obj.http.X-Cache-Object-URL ~ ' + quoted(pattern))
        self.assertGreater(len(expression), 3000)
        objects = [(paths[0], 'one'), (paths[1], 'two'), ('/control', 'control'),
                   (paths[0], 'foreign', 'foreign.test')]
        self.run_vcl([*(origin(*item) for item in objects),
                      origin(paths[0], 'one-new'), origin(paths[1], 'two-new')],
                     [*(get(*item, cache='MISS') for item in objects),
                      *(get(*item, cache='HIT') for item in objects),
                      contract('batch-ban', expression),
                      *(get(*item, cache='HIT') for item in objects[2:]),
                      get(paths[0], 'one-new', cache='MISS'),
                      get(paths[0], 'one-new', cache='HIT'),
                      get(paths[1], 'two-new', cache='MISS'),
                      get(paths[1], 'two-new', cache='HIT')])

    def test_long_contract_rejects_malformed_operands_and_wrong_token(self):
        prefix = ('obj.http.X-Cache-Object-Host == "example.test" && '
                  'obj.http.X-Cache-Object-URL ~ ')
        operand = '^/target' + 'x' * 3400 + '$'
        malformed = [prefix + '"' + operand + '"tail"',
                     prefix + '"' + operand + '\\"',
                     prefix + quoted(operand) + ' && obj.status > 0']
        valid = prefix + quoted(operand)
        self.run_vcl([origin('/control', 'control')],
                     [get('/control', 'control', cache='MISS'),
                      *(contract('exact-ban', value, status=400) for value in malformed),
                      control('/__ultracache-vcl-contract-v2', method='PURGE',
                              token='wrong', status=403,
                              headers=['X-UltraCache-Contract: 2',
                                       'X-UltraCache-Operation: exact-ban',
                                       'X-UltraCache-Object-Expression: ' + valid]),
                      get('/control', 'control', cache='HIT')])

    def test_html_flush_preserves_static_objects_and_foreign_hosts(self):
        for versioned in (False, True):
            with self.subTest(versioned=versioned):
                operation = (contract('html-ban', 'obj.http.X-Cache-Object-Host == "example.test" && obj.http.Content-Type ~ "^text/html"')
                             if versioned else control(expression='req.http.host == example.test && obj.http.Content-Type ~ ^text/html'))
                self.run_vcl([origin('/page', 'page'), origin('/asset.css', 'css', mime='text/css'),
                              origin('/page', 'foreign', 'foreign.test'), origin('/page', 'new')],
                             [get('/page', 'page'), get('/asset.css', 'css'), get('/page', 'foreign', 'foreign.test'),
                              operation, get('/asset.css', 'css', cache='HIT'),
                              get('/page', 'foreign', 'foreign.test', cache='HIT'), get('/page', 'new', cache='MISS')])

    def test_host_flush_preserves_aliases_and_other_sites(self):
        for versioned in (False, True):
            with self.subTest(versioned=versioned):
                operation = (contract('host-ban', 'obj.http.X-Cache-Object-Host == "example.test" && obj.http.X-Cache-Object-URL ~ ".*"')
                             if versioned else control(expression='req.http.host == example.test && req.url ~ .*'))
                self.run_vcl([origin('/page', 'page'), origin('/asset.css', 'css', mime='text/css'),
                              origin('/page', 'alias', 'www.example.test'), origin('/page', 'same-owner', 'second.test'),
                              origin('/page', 'new'), origin('/asset.css', 'new-css', mime='text/css')],
                             [get('/page', 'page'), get('/asset.css', 'css'), get('/page', 'alias', 'www.example.test'),
                              get('/page', 'same-owner', 'second.test'), operation,
                              get('/page', 'alias', 'www.example.test', cache='HIT'),
                              get('/page', 'same-owner', 'second.test', cache='HIT'),
                              get('/page', 'new', cache='MISS'), get('/asset.css', 'new-css', cache='MISS')])

    def test_invalid_expressions_and_unauthorized_requests_do_not_flush(self):
        self.run_vcl([origin('/control', 'control')], [get('/control', 'control'),
            control(status=400), control(expression='obj.status > 0', status=400),
            control(expression='req.http.host == example.test && req.url ~ ^[$', status=400),
            control(expression='req.http.host == example.test && req.url ~ /control', status=400),
            control(expression='req.http.host == foreign.test && req.url ~ .*', status=403),
            control(expression='req.http.host == example.test && req.url ~ .*', token='wrong', status=403),
            control(expression='req.http.host == example.test && req.url ~ .*',
                    headers=['X-Forwarded-For: 203.0.113.20'], status=403),
            contract('exact-ban', 'obj.http.X-Cache-Object-Host == "example.test" && obj.http.X-Cache-Object-URL ~ ".*"', status=400),
            contract('batch-ban', 'obj.http.X-Cache-Object-Host == "example.test" && obj.http.X-Cache-Object-URL ~ "^/control$" && obj.status > 0', status=400),
            contract('html-ban', 'obj.http.X-Cache-Object-Host == "foreign.test" && obj.http.Content-Type ~ "^text/html"', status=403),
            contract('unknown', status=400),
            get('/control', 'control', cache='HIT')])

    def test_exact_purge_removes_all_vary_variants_but_not_other_urls(self):
        for versioned in (False, True):
            with self.subTest(versioned=versioned):
                operation = contract('exact-purge', path='/target') if versioned else control('/target', method='PURGE')
                self.run_vcl([origin('/target', 'html', headers=['Vary: Accept']),
                              origin('/target', 'json', mime='application/json', headers=['Vary: Accept']),
                              origin('/control', 'control'),
                              origin('/target', 'new-html', headers=['Vary: Accept']),
                              origin('/target', 'new-json', mime='application/json', headers=['Vary: Accept'])],
                             [get('/target', 'html', headers=['Accept: text/html']),
                              get('/target', 'json', headers=['Accept: application/json']),
                              get('/control', 'control'), operation, get('/control', 'control', cache='HIT'),
                              get('/target', 'new-html', headers=['Accept: text/html'], cache='MISS'),
                              get('/target', 'new-json', headers=['Accept: application/json'], cache='MISS')])

    def test_soft_purge_expires_only_selected_url_and_preserves_other_hosts(self):
        for versioned in (False, True):
            with self.subTest(versioned=versioned):
                operation = contract('soft-purge', path='/target') if versioned else control('/target', method='PURGE', headers=['X-Purge: soft'])
                self.run_vcl([origin('/target','old'), origin('/control','control'),
                              origin('/target','foreign','foreign.test'), origin('/target','new')],
                             [get('/target','old'),get('/control','control'),get('/target','foreign','foreign.test'),
                              control('/target',method='PURGE',headers=['X-Purge: soft'],token='wrong',status=403),
                              get('/target','old',cache='HIT'),operation,
                              get('/control','control',cache='HIT'),get('/target','foreign','foreign.test',cache='HIT'),
                              get('/target','old',cache='HIT'), 'delay 0.2', get('/target','new',cache='HIT'),
                              control('/missing',method='PURGE',headers=['X-Purge: soft'])])

    def test_ban_expression_longer_than_old_limit_removes_every_selected_url(self):
        selected = ['/target-one', '/target-two']
        pattern = '^(' + '|'.join([*selected, *('/absent-' + str(i) for i in range(300))]) + ')$'
        self.assertGreater(len(pattern), 3000)
        self.run_vcl([origin(selected[0],'old1'),origin(selected[1],'old2'),origin('/control','control'),
                      origin(selected[0],'new1'),origin(selected[1],'new2')],
                     [get(selected[0],'old1'),get(selected[1],'old2'),get('/control','control'),
                      control(expression='req.http.host == example.test && req.url ~ ' + pattern),
                      get('/control','control',cache='HIT'),get(selected[0],'new1',cache='MISS'),get(selected[1],'new2',cache='MISS')])

    def test_scoped_ban_works_without_wordpress_or_ultracache_for_every_profile(self):
        for profile in ('general', 'wordpress', 'woocommerce', 'ultracache'):
            with self.subTest(profile=profile):
                self.run_vcl([origin('/target', 'old', mime='text/plain'),
                              origin('/control', 'control', mime='text/plain'),
                              origin('/target', 'new', mime='text/plain')],
                             [get('/target', 'old'), get('/control', 'control'),
                              control(expression='req.http.host == example.test && req.url ~ ^/target$'),
                              get('/control', 'control', cache='HIT'), get('/target', 'new', cache='MISS')],
                             profile=profile)

    def test_private_esi_keeps_visitors_separate_while_parent_is_shared(self):
        fragment = '/?ultracache_esi=cart&esi_scope=private'
        parent = '<html>before<esi:include src="/?ultracache_esi=cart&amp;esi_scope=private"/>after</html>'
        self.run_vcl([origin('/parent', parent, headers=['Surrogate-Control: ESI/1.0'],
                              expect=['expect req.http.Cookie == <undef>']),
                      origin(fragment, 'cart-A', mime='text/plain',
                             expect=['expect req.http.Cookie == "esi_session=A"',
                                     'expect req.http.X-ESI-Private-Request == "1"']),
                      origin(fragment, 'cart-B', mime='text/plain',
                             expect=['expect req.http.Cookie == "esi_session=B"',
                                     'expect req.http.X-ESI-Private-Request == "1"'])],
                     [get('/parent', '<html>beforecart-Aafter</html>', headers=['Cookie: esi_session=A'], cache='MISS'),
                      get('/parent', '<html>beforecart-Bafter</html>', headers=['Cookie: esi_session=B'], cache='HIT')])

    def test_actual_ultracache_producer_expressions_preserve_scope(self):
        # Exported from the actual UltraCache PHP traits, including their quoting
        # and operation classification. This is not a Python reimplementation.
        corpus = json.loads((Path(__file__).parent / 'fixtures' / 'ultracache-http-v2.json').read_text())
        paths = [row['targetPath'] for row in corpus['rows'] if row['targetPath']]
        for row in corpus['rows']:
            for versioned in (False, True):
                with self.subTest(operation=row['operation'], target=row['targetPath'], versioned=versioned):
                    targets = [row['targetPath']] if row['targetPath'] else paths
                    operation = row['operation']
                    if operation == 'html-ban':
                        control_path, control_mime, control_host = '/control.css', 'text/css', 'example.test'
                    elif operation == 'host-ban':
                        control_path, control_mime, control_host = '/control', 'text/html', 'foreign.test'
                    else:
                        control_path, control_mime, control_host = '/control', 'text/html', 'example.test'
                    invalidate = (contract(operation, row['objectExpression']) if versioned
                                  else control(expression=row['portableExpression']))
                    self.run_vcl([*(origin(path, 'old-' + str(i)) for i, path in enumerate(targets)),
                                  origin(control_path, 'control', control_host, control_mime),
                                  *(origin(path, 'new-' + str(i)) for i, path in enumerate(targets))],
                                 [*(get(path, 'old-' + str(i)) for i, path in enumerate(targets)),
                                  get(control_path, 'control', control_host), invalidate,
                                  get(control_path, 'control', control_host, cache='HIT'),
                                  *(get(path, 'new-' + str(i), cache='MISS') for i, path in enumerate(targets))])


if __name__ == '__main__':
    unittest.main()
