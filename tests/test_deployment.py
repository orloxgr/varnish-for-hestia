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
        (self.source/'panel/menu.js').write_bytes((ROOT/'panel/menu.js').read_bytes())
        (self.source/'addon.json').write_text(json.dumps(self.meta))
        self.hestia = self.root/'hestia'
        (self.hestia/'web').mkdir(parents=True)
        (self.hestia/'web/js').mkdir()
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
        self.assertEqual(deployment.menu_path().read_bytes(), (self.source/'panel/menu.js').read_bytes())
        self.assertEqual(stat.S_IMODE(deployment.menu_path().stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE(deployment.menu_path().parent.stat().st_mode), 0o755)

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

    def test_menu_rollback_and_removal_preserve_other_addons(self):
        directory = self.hestia/'web/js/custom_scripts'
        directory.mkdir()
        directory.chmod(0o750)
        neighbor = directory/'another-addon.js'
        neighbor.write_text('// another addon')
        deployment.publish(self.source, self.meta)
        original = deployment.menu_path().read_bytes()
        deployment.commit()
        (self.source/'panel/menu.js').write_bytes(original+b'\n// next release\n')
        deployment.publish(self.source, self.meta)
        self.assertNotEqual(deployment.menu_path().read_bytes(), original)
        deployment.rollback()
        self.assertEqual(deployment.menu_path().read_bytes(), original)
        deployment.remove()
        self.assertFalse(deployment.menu_path().exists())
        self.assertEqual(neighbor.read_text(), '// another addon')
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o750)

    def test_rollback_to_release_without_menu_removes_new_script(self):
        asset = self.source/'panel/menu.js'
        content = asset.read_bytes()
        asset.unlink()
        deployment.publish(self.source, self.meta)
        deployment.commit()
        asset.write_bytes(content)
        deployment.publish(self.source, self.meta)
        self.assertTrue(deployment.menu_path().is_file())
        deployment.rollback()
        self.assertFalse(deployment.menu_path().exists())


if __name__ == '__main__':
    unittest.main()
