"""The installed catalogue updates descriptions and functional rules together."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import cookie_database
import cookie_recognition


class BundledCookies(unittest.TestCase):
    def test_old_download_is_not_used_and_legacy_update_does_not_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            snapshot=root/'recognition-state.json'
            original=b'old downloaded snapshot preserved for rollback'
            snapshot.write_bytes(original)
            with patch.object(cookie_database,'directory',return_value=root), \
                 patch.object(cookie_recognition,'fetch',side_effect=AssertionError('No runtime fetch')):
                status=cookie_database.update(force=True)
                self.assertEqual(status['result'],'bundled')
                self.assertFalse(status['automatic'])
                self.assertGreater(status['rules'],2000)
                self.assertIn('Update the plugin',status['message'])
                self.assertEqual(cookie_database.database(),json.loads(cookie_database.BUNDLED.read_text(encoding='utf-8')))
                self.assertEqual(snapshot.read_bytes(),original)


if __name__=='__main__':unittest.main()
