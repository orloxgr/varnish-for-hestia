"""Retired status actions are refused; cron upgrades retain reconciliation."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'shared'))
import administration
import addon


class CookieDatabaseIntegration(unittest.TestCase):
    def test_retired_status_actions_are_refused_before_loading_service(self):
        for action in ('admin-cookie-database-settings','admin-cookie-database-update'):
            with self.subTest(action=action), patch.dict(sys.modules,{'service':None}):
                with self.assertRaisesRegex(ValueError,'Invalid administrator action'):
                    administration.request(None,action,{'cookie_database_automatic':False},'varnish')

    def test_retired_update_command_reports_failure_without_reconciling(self):
        output=io.StringIO()
        with patch.object(sys,'argv',['addon.py','update-cookie-database']), \
             patch.object(addon.os,'geteuid',return_value=0,create=True), \
             patch.dict(sys.modules,{'service':None}), redirect_stdout(output):
            self.assertEqual(addon.locked_main(),1)
        self.assertFalse(json.loads(output.getvalue())['ok'])

    @unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0, 'Native owned cron file')
    def test_upgrade_removes_daily_download_keeps_reconciliation_and_is_idempotent(self):
        import maintenance
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'addon-cron'
            path.write_text(maintenance.MARKER+'\n17 3 * * * root v-varnish-hestia update-cookie-database\n')
            with patch.object(maintenance,'CRON',path):
                maintenance.install_cron()
                original = path.read_bytes()
                maintenance.install_cron()
                self.assertEqual(path.read_bytes(),original)
                self.assertIn(b'reconcile',original)
                self.assertNotIn(b' 3 * * * root ',original)
                self.assertNotIn(b'update-cookie-database',original)
                self.assertEqual(original.count(b'reconcile'),1)
                path.write_text('unmanaged')
                with self.assertRaises(ValueError):
                    maintenance.install_cron()


if __name__ == '__main__':
    unittest.main()
