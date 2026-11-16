"""Hestia recognition controls do not reconcile VCL or call upstream on reads."""
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
    def test_manual_update_and_toggle_do_not_reconcile_or_reload_varnish(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory)
            (store/'applied.json').write_text(json.dumps(fixture()))
            for action in ('admin-cookie-database-settings','admin-cookie-database-update'):
                with patch.object(service,'STORE',store), patch.object(service,'settings',return_value={}), \
                     patch.object(service,'reconcile') as reconcile, patch.object(cookie_database,'configure') as configure, \
                     patch.object(cookie_database,'update') as update, \
                     patch.object(cookie_database,'status',return_value={'automatic':True,'records':2288}):
                    result = administration.request(None,action,{'cookie_database_automatic':False},'varnish')
                    self.assertTrue(result['ok'])
                    reconcile.assert_not_called()
                    if action.endswith('-settings'):
                        configure.assert_called_once_with(False)
                        update.assert_not_called()
                    else:
                        update.assert_called_once_with(force=True)
                        configure.assert_not_called()

    @unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0, 'Native owned cron file')
    def test_daily_cron_keeps_discovery_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'addon-cron'
            with patch.object(maintenance,'CRON',path):
                maintenance.install_cron()
                original = path.read_bytes()
                maintenance.install_cron()
                self.assertEqual(path.read_bytes(),original)
                self.assertIn(b'reconcile',original)
                self.assertIn(b' 3 * * * root ',original)
                self.assertEqual(original.count(b'update-cookie-database'),1)
                path.write_text('unmanaged')
                with self.assertRaises(ValueError):
                    maintenance.install_cron()


if __name__ == '__main__':
    unittest.main()
