"""Native nonce composition and non-restarting service feature upgrades."""
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import maintenance
import service
import test_cache_policy as policy
import test_profile_compatibility as http


class ServiceFeatures(unittest.TestCase):
    def config(self):
        return dict(listen_port=6081, admin_port=6082, memory_mb=8192)

    def test_startup_and_upgrade_enable_attribute_parsing_without_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder).resolve() / 'unit.conf'
            path.write_text('# Local comment\n' + maintenance.service_dropin(self.config()).replace(',+esi_ignore_other_elements', ''))
            with patch.object(maintenance, 'DROPIN', path), patch.object(maintenance.routing, 'run') as run, \
                 patch.object(service, 'admin') as admin:
                maintenance.configure_esi(self.config())
                self.assertIn('-p feature=+http2,+esi_ignore_other_elements', path.read_text())
                self.assertIn('-s malloc,8192m', path.read_text())
                run.assert_called_once_with('systemctl', 'daemon-reload')
                admin.assert_called_once_with(self.config(), 'param.set', 'feature', '+esi_ignore_other_elements')
                run.reset_mock(); admin.reset_mock()
                maintenance.configure_esi(self.config())
                run.assert_not_called()
                admin.assert_called_once_with(self.config(), 'param.set', 'feature', '+esi_ignore_other_elements')

    def test_native_update_failure_restores_managed_unit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder).resolve() / 'unit.conf'
            original = maintenance.service_dropin(self.config()).replace(',+esi_ignore_other_elements', '').encode()
            path.write_bytes(original)
            with patch.object(maintenance, 'DROPIN', path), patch.object(maintenance.routing, 'run') as run, \
                 patch.object(service, 'admin', side_effect=RuntimeError('Native parameter failed')):
                with self.assertRaisesRegex(RuntimeError, 'Native parameter failed'):
                    maintenance.configure_esi(self.config())
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual([call.args for call in run.call_args_list],
                                 [('systemctl', 'daemon-reload'), ('systemctl', 'daemon-reload')])

    def test_unmanaged_service_file_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder).resolve() / 'unit.conf'
            path.write_text('administrator-owned service')
            with patch.object(maintenance, 'DROPIN', path), patch.object(maintenance.routing, 'run') as run, \
                 patch.object(service, 'admin') as admin:
                with self.assertRaisesRegex(ValueError, 'unmanaged'):
                    maintenance.configure_esi(self.config())
                self.assertEqual(path.read_text(), 'administrator-owned service')
                run.assert_not_called(); admin.assert_not_called()


@unittest.skipUnless(shutil.which('varnishtest'), 'native varnishtest required')
class NonceEsi(unittest.TestCase):
    run_policy = policy.CachePolicy.run_policy

    def test_startup_flags_compose_all_contexts_with_private_visitor_fragments(self):
        startup = next(line.split('=', 1)[1] for line in maintenance.service_dropin(
            dict(listen_port=6081, admin_port=6082, memory_mb=8192)).splitlines() if line.startswith('ExecStart=/'))
        tokens = shlex.split(startup)
        flag = tokens[tokens.index('-p') + 1]
        paths = {context: '/?ultracache_esi=nonce&esi_scope=private&context=' + context + '&sig=fixture'
                 for context in ('js', 'json', 'attribute')}
        tags = {context: '<esi:include src="' + path.replace('&', '&amp;') + '"/>' for context, path in paths.items()}

        def body(values):
            return ('<html><script>window.nonce=\'' + values['js'] + '\';</script>' +
                    '<script type="application/json">{"nonce":"' + values['json'] + '"}</script>' +
                    "<input value='" + values['attribute'] + "'></html>")

        origins = [http.response('/nonce-parent', body(tags), headers=[
            'Content-Type: text/html', 'Surrogate-Control: ESI/1.0', 'X-UltraCache-ESI-Shared-Parent: 1'])]
        requests = []
        for index, visitor in enumerate(('A', 'B', 'A')):
            values = {context: visitor + str(index) + context for context in paths}
            for context, path in paths.items():
                origins.append(http.response(path, values[context], headers=[
                    'Content-Type: text/plain', 'Set-Cookie: fragment_cookie=must-not-reach-browser'],
                    expect=['expect req.http.Cookie == "wp_woocommerce_session_demo=' + visitor + '"',
                            'expect req.http.X-ESI-Private-Request == "1"',
                            'expect req.http.X-ESI-Original-Cookie == <undef>']))
            requests += [http.request('/nonce-parent', body(values), headers=[
                'Cookie: wp_woocommerce_session_demo=' + visitor + '; ultracache_esi_optin=1; unrelated=do-not-forward'],
                cache='MISS' if index == 0 else 'HIT'), 'expect resp.http.Set-Cookie == <undef>']
        self.run_policy('ultracache', origins, requests, varnish_args='-arg "-p ' + flag + '"')

    def test_runtime_feature_update_is_additive_and_effective_without_restart(self):
        source = http.program('ultracache')
        tag = '<esi:include src="/?ultracache_esi=nonce&amp;esi_scope=private"/>'
        parent = "<html><input value='" + tag + "'></html>"
        origins = '\n'.join([
            http.response('/parent', parent, headers=['Content-Type: text/html', 'Surrogate-Control: ESI/1.0']),
            http.response('/?ultracache_esi=nonce&esi_scope=private', 'newnonce', headers=['Content-Type: text/plain'])]).removeprefix('accept\n')
        script = ('varnishtest "Add ESI attribute feature without resetting other flags"\nserver s1 {\n' + origins +
                  '\n} -start\nvarnish v1 -arg "-p feature=+esi_remove_bom" -vcl {\n' + source +
                  '\n} -start\nvarnish v1 -cliok "param.set feature +esi_ignore_other_elements"\n' +
                  'varnish v1 -cliexpect "esi_remove_bom" "param.show feature"\n' +
                  'client c1 {\n' + http.request('/parent', "<html><input value='newnonce'></html>") +
                  '\n} -run\nserver s1 -wait\n')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'runtime.vtc'; path.write_text(script)
            result = subprocess.run(['varnishtest', '-t', '15', str(path)], capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cold_private_parent_with_set_cookie_still_composes_esi(self):
        fragment = '/?ultracache_esi=cart&esi_scope=private'
        tag = '<esi:include src="/?ultracache_esi=cart&amp;esi_scope=private"/>'
        origins, requests = [], []
        for visitor in ('A', 'B'):
            origins += [http.response('/cold', '<html>native-nonce-' + visitor + tag + '</html>',
                policy='private, no-store', headers=['Content-Type: text/html',
                    'Surrogate-Control: content=ESI/1.0, no-store',
                    'Set-Cookie: wp_woocommerce_session_demo=' + visitor + '; Path=/']),
                http.response(fragment, 'empty-cart', headers=['Content-Type: text/plain'],
                    expect=['expect req.http.Cookie == <undef>'])]
            requests += [http.request('/cold', '<html>native-nonce-' + visitor + 'empty-cart</html>', cache='PASS'),
                'expect resp.http.Set-Cookie == "wp_woocommerce_session_demo=' + visitor + '; Path=/"']
        self.run_policy('ultracache', origins, requests)


if __name__ == '__main__':
    unittest.main()
