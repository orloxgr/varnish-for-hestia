"""Reused projections must retain actual scoped policy and mutation semantics."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'shared')]
import cookie_admin
import cookie_execution
from test_cookie_admin import settings


class CookieExecution(unittest.TestCase):
    def test_central_and_site_variants_keep_their_full_execution(self):
        project = cookie_execution.projections()
        central = settings('currency', 'variant')
        for site in (None, settings('currency', 'private'), settings('tracking', 'shared')):
            self.assertEqual(project(central, site), tuple(cookie_admin.executable(central, site)))
            self.assertEqual(project(copy.deepcopy(central), copy.deepcopy(site)), project(central, site))

    def test_mutated_inputs_cannot_reuse_a_stale_projection(self):
        project = cookie_execution.projections()
        choice = settings('currency', 'variant')
        before = project(None, choice)
        choice['rules'][0]['action'] = 'private'
        self.assertNotEqual(project(None, choice), before)
        self.assertEqual(project(None, choice), tuple(cookie_admin.executable(None, choice)))
        choice['rules'][0]['description'] = 'Metadata only'
        self.assertEqual(project(None, choice), tuple(cookie_admin.executable(None, choice)))


if __name__ == '__main__':
    unittest.main()
