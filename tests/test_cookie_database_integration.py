"""Retired metadata-only updates report the bundled lifecycle without fetching."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import administration
import cookie_database
import maintenance
import service
from test_administration import fixture


class CookieDatabaseIntegration(unittest.TestCase):
    def test_legacy_update_calls_report_bundle_without_reconcile_or_fake_update(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            (store/'applied.json').write_text(json.dumps(fixture()))
            for action in ('admin-cookie-database-settings','admin-cookie-database-update'):
                with patch.object(service,'STORE',store), patch.object(service,'settings',return_value={}), \
                     patch.object(service,'reconcile') as reconcile, patch.object(cookie_database,'configure') as configure, \
                     patch.object(cookie_database,'update') as update:
                    result = administration.request(None,action,{'cookie_database_automatic':False},'varnish')
                    self.assertTrue(result['ok'])
                    self.assertIn('Update the plugin',result['cookie_database_notice'])
                    self.assertNotIn('cookie_database_updated',result)
                    self.assertFalse(result['cookie_database']['automatic'])
                    reconcile.assert_not_called()
                    if action.endswith('-settings'):
                        configure.assert_called_once_with(False)
                        update.assert_not_called()
                    else:
                        update.assert_called_once_with(force=True)
                        configure.assert_not_called()

    @unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0, 'Native owned cron file')
    def test_upgrade_removes_daily_download_keeps_reconciliation_and_is_idempotent(self):
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
