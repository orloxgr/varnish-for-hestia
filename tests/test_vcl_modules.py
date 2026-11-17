"""Owned module edits enter the complete artifact; no runtime includes remain."""
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))
from vcl_source import expand
from cookie_catalogue import load_catalogue, render_policy


class VclModules(unittest.TestCase):
    def test_include_only_change_changes_artifact_and_old_artifact_survives_source_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'shared'
            shutil.copytree(ROOT / 'shared', root, ignore=shutil.ignore_patterns('__pycache__'))
            coordinator = (root / 'cache-policy.vcl').read_text(encoding='utf-8')
            before = render_policy(expand(coordinator, root), load_catalogue())
            module = root / 'vcl/cookies.vcl'
            module.write_text(module.read_text(encoding='utf-8') + '\n# Module-only change\n', encoding='utf-8')
            after = render_policy(expand(coordinator, root), load_catalogue())
            self.assertNotEqual(hashlib.sha256(before.encode()).digest(), hashlib.sha256(after.encode()).digest())
            self.assertEqual((root / 'cache-policy.vcl').read_text(encoding='utf-8'), coordinator)
            shutil.rmtree(root)
            self.assertNotIn('include "', before)
            self.assertNotIn('include "', after)
            self.assertIn('sub scp_cookie_variation', before)

    def test_unmanaged_paths_and_nested_includes_are_rejected(self):
        with self.assertRaises(ValueError):
            expand('include "../../unmanaged.vcl";')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'vcl').mkdir()
            (root / 'vcl/core.vcl').write_text('include "other.vcl";')
            with self.assertRaises(ValueError):
                expand('include "vcl/core.vcl";', root)
