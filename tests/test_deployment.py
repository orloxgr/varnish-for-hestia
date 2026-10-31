"""Publish into a fresh Hestia directory tree, using only temporary files."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import deployment


@unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0, 'Linux root file operations required')
class FreshDeployment(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hestia-deployment-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.meta = json.loads((ROOT/'addon.json').read_text())
        self.source = self.root/'source'
        (self.source/'src').mkdir(parents=True)
        (self.source/'panel').mkdir()
        (self.source/'src/addon.py').write_text('# fixture\n')
        (self.source/'panel/index.php').write_text('<?php /* __INSTALL_ROOT__ */ ?>')
        (self.source/'addon.json').write_text(json.dumps(self.meta))
        self.hestia = self.root/'hestia'
        (self.hestia/'web').mkdir(parents=True)
        (self.hestia/'bin').mkdir()
        (self.root/'opt').mkdir()
        self.target = self.root/'opt'/self.meta['id']
        self.overrides = patch.multiple(deployment, HESTIA=self.hestia, TARGET=self.target,
                                        RELEASES=self.target.with_name(self.meta['id']+'.releases'),
                                        PENDING=self.root/'state/code-update.json')
        self.overrides.start()
        self.addCleanup(self.overrides.stop)
        lint = patch.object(deployment, 'check_panel')
        lint.start()
        self.addCleanup(lint.stop)

    def test_first_addon_creates_plugins_parent(self):
        plugins = self.hestia/'web/plugins'
        self.assertFalse(plugins.exists())
        previous_umask = os.umask(0o077)
        try:
            deployment.publish(self.source, self.meta)
        finally:
            os.umask(previous_umask)
        self.assertEqual(stat.S_IMODE(plugins.stat().st_mode), 0o755)
        self.assertEqual((plugins/self.meta['slug']/'.addon-owner').read_text().strip(), self.meta['id'])
        self.assertIn(str(self.target), (plugins/self.meta['slug']/'index.php').read_text())
        self.assertTrue((self.hestia/'bin'/self.meta['command']).is_file())
        self.assertTrue(self.target.is_symlink())

    def test_retry_preserves_shared_directory_and_other_plugins(self):
        plugins = self.hestia/'web/plugins'
        (plugins/'another-plugin').mkdir(parents=True)
        plugins.chmod(0o750)
        neighbor = plugins/'another-plugin/index.php'
        neighbor.write_text('existing plugin')
        for _ in range(2):
            deployment.publish(self.source, self.meta)
        self.assertEqual(stat.S_IMODE(plugins.stat().st_mode), 0o750)
        self.assertEqual(neighbor.read_text(), 'existing plugin')
        self.assertTrue((plugins/self.meta['slug']/'index.php').is_file())


if __name__ == '__main__':
    unittest.main()
