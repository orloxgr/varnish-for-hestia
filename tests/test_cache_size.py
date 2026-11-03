"""Shared cache size persistence, failure recovery and native malloc budgets."""
import contextlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import cache_size
import administration
import maintenance
import server_settings
import service
import transaction
from registry import desired_state


class CacheSize(unittest.TestCase):
    @contextlib.contextmanager
    def installation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = dict(installed=True, memory_mb=64, listen_port=6081, admin_port=6082)
            dropin = root / 'unit.conf'
            (root / 'settings.json').write_text(json.dumps(config))
            dropin.write_text(maintenance.service_dropin(config))
            (root / 'active.vcl').write_text('existing VCL')
            (root / 'desired.json').write_text('unchanged tokens and profiles')
            with patch.object(service, 'CONFIG', root), patch.object(service, 'STORE', root), \
                 patch.object(maintenance, 'DROPIN', dropin), patch.object(service, 'verify_native_unit'), \
                 patch.object(service.routing, 'run') as run, patch.object(service, 'wait_healthy'), \
                 patch.object(cache_size, 'check_budget'):
                yield root, config, dropin, run

    def test_size_validation_rejects_untrusted_values_before_commands(self):
        for value in [None, True, '8192', 0, -1, 128.5, '64m; reboot']:
            with patch.object(service, 'recover_pending') as recover:
                with self.assertRaises(ValueError): cache_size.resize(value)
                recover.assert_not_called()

    def test_resize_persists_native_startup_size_without_touching_site_choices(self):
        with self.installation() as (root, config, dropin, run):
            updated, restarted = cache_size.resize(8192)
            self.assertTrue(restarted)
            self.assertEqual(updated['memory_mb'], 8192)
            self.assertEqual(service.settings()['memory_mb'], 8192)
            self.assertIn('-s malloc,8192m', dropin.read_text())
            self.assertEqual((root / 'active.vcl').read_text(), 'existing VCL')
            self.assertEqual((root / 'desired.json').read_text(), 'unchanged tokens and profiles')
            self.assertFalse((root / cache_size.JOURNAL).exists())
            self.assertIn(('systemctl', 'restart', 'varnish'), [c.args for c in run.call_args_list])
            run.reset_mock()
            self.assertFalse(cache_size.resize(8192)[1])
            run.assert_not_called()

    def test_failed_restart_restores_old_size_and_retains_original_error_boundary(self):
        with self.installation() as (root, config, dropin, run):
            before = dropin.read_bytes()
            with patch.object(service, 'wait_healthy', side_effect=[RuntimeError('failed'), None]):
                with self.assertRaisesRegex(RuntimeError, 'previous size was restored'):
                    cache_size.resize(128)
            self.assertEqual(dropin.read_bytes(), before)
            self.assertEqual(service.settings()['memory_mb'], 64)
            self.assertEqual(sum(c.args == ('systemctl', 'restart', 'varnish') for c in run.call_args_list), 2)
            self.assertFalse((root / cache_size.JOURNAL).exists())

    def test_interrupted_resize_recovers_on_next_settings_read(self):
        with self.installation() as (root, config, dropin, run):
            transaction.begin(root, cache_size.paths(), filename=cache_size.JOURNAL)
            (root / 'settings.json').write_text(json.dumps(dict(config, memory_mb=128)))
            dropin.write_text(maintenance.service_dropin(dict(config, memory_mb=128)))
            self.assertEqual(service.settings()['memory_mb'], 64)
            self.assertIn('-s malloc,64m', dropin.read_text())
            self.assertFalse((root / cache_size.JOURNAL).exists())

    def test_failed_recovery_keeps_journal_for_retry(self):
        with self.installation() as (root, config, dropin, run):
            with patch.object(service, 'wait_healthy', side_effect=RuntimeError('failed')):
                with self.assertRaisesRegex(RuntimeError, 'recovery is pending'): cache_size.resize(128)
            self.assertTrue((root / cache_size.JOURNAL).exists())
            self.assertEqual(service.settings()['memory_mb'], 64)
            self.assertFalse((root / cache_size.JOURNAL).exists())

    def test_unmanaged_unit_is_not_overwritten(self):
        with self.installation() as (root, config, dropin, run):
            dropin.write_text('unmanaged')
            with self.assertRaises(ValueError): cache_size.resize(128)
            run.assert_not_called()
            self.assertEqual(dropin.read_text(), 'unmanaged')

    def test_runtime_budget_mismatch_is_rejected(self):
        from types import SimpleNamespace
        with patch.object(cache_size.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='123\n')), \
             patch.object(Path, 'read_bytes', return_value=b'/usr/sbin/varnishd\0-F\0-s\0malloc,64m\0'):
            with self.assertRaises(RuntimeError): cache_size.check_budget({'memory_mb':128})
            cache_size.check_budget({'memory_mb':64})

    def test_admin_action_reports_new_budget_without_running_policy_or_stats(self):
        from types import SimpleNamespace
        with self.installation() as (root, config, dropin, run):
            inventory = {'alice':dict(identity='one', package='default', role='user', suspended=False,
                                      sites={'example.test':dict(aliases=[], suspended=False)})}
            state = desired_state(None, inventory, 'varnish')
            (root / 'applied.json').write_text(json.dumps(state))
            with patch.object(service, 'reconcile') as reconcile, \
                 patch.object(service, 'admin', return_value=SimpleNamespace(stdout=b'Value is: 60.000 [seconds]')), \
                 patch.object(server_settings, 'memory') as snapshot:
                result = administration.request(None, 'admin-memory-size', {'memory_mb':128}, 'varnish')
            self.assertTrue(result['memory_size_saved'])
            self.assertTrue(result['service_restarted'])
            self.assertEqual(result['memory_budget_mb'], 128)
            self.assertEqual(result['total_sites'], 1)
            reconcile.assert_not_called(); snapshot.assert_not_called()

    @unittest.skipUnless(shutil.which('varnishtest'), 'Native Varnish required')
    def test_native_storage_budget_changes_after_restart(self):
        for size in [64, 128]:
            script = '''varnishtest "Native cache storage budget"
varnish v1 -arg "-s malloc,SIZEm" -vcl { backend default { .host = "127.0.0.1"; .port = "1"; } } -start
shell {varnishstat -n ${v1_name} -1 -j > ${tmpdir}/storage.json}
'''.replace('SIZE', str(size))
            # Inspect the same native s0 counters used by the resize verifier.
            script += '''shell {python3 -c 'import json; d=json.load(open("${tmpdir}/storage.json")); d=d.get("counters",d); assert abs(d["SMA.s0.g_bytes"]["value"]+d["SMA.s0.g_space"]["value"]-SIZE*1048576)<1024'}
'''.replace('SIZE', str(size))
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'budget.vtc'; path.write_text(script)
                result = subprocess.run(['varnishtest', '-t', '15', str(path)], capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
