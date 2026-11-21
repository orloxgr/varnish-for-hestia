"""Old exclusions become visible choices during normal Hestia reconciliation."""
import copy
import os
from pathlib import Path
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'shared'))
import cookie_admin
import cookie_control
from cookie_catalogue import load_catalogue
from cookie_migration import migrate_site, SOURCE
from test_cms_cookie_choices import cache, owned_module
from test_cookie_delivery import proxy


def choice(name, basic, ultracache, kind='prefix'):
    return dict(schemaVersion=2, rules=[dict(id='custom:existing', match=dict(kind=kind, value=name),
        description='Existing choice', actions=dict(basic=basic, ultracache=ultracache))])


def action(settings, name, profile, central=None):
    rows = cookie_admin.active(central, settings, profile)
    return next(row['action'] for row in rows if cookie_admin._matches(row['match'], dict(kind='exact', value=name)))


class LegacyCookieMigration(unittest.TestCase):
    def test_covered_old_exact_does_not_override_new_prefix_in_either_profile(self):
        saved = choice('member_', 'shared', 'variant')
        site = dict(cookie_policies=copy.deepcopy(saved), bypass_cookies=['member_gold'])
        migrate_site(site)
        self.assertNotIn('bypass_cookies', site)
        self.assertEqual(site['cookie_policies'], saved)

    def test_new_narrow_choices_win_while_old_prefix_still_excludes_other_names(self):
        site = dict(cookie_policies=choice('member_gold', 'shared', 'variant', 'exact'), bypass_cookies=['member_*'])
        migrate_site(site)
        for profile, expected in (('basic', 'shared'), ('ultracache', 'variant')):
            self.assertEqual(action(site['cookie_policies'], 'member_gold', profile), expected)
            self.assertEqual(action(site['cookie_policies'], 'member_silver', profile), 'private')
        imported = next(row for row in site['cookie_policies']['rules'] if row['id'].startswith('legacy-bypass:'))
        self.assertIn(SOURCE, imported['description'])
        rows = cookie_admin.table({'records': []}, load_catalogue(), site=site['cookie_policies'])
        self.assertTrue(any(row['id'] == imported['id'] and SOURCE in row['description'] for row in rows))

    def test_missing_column_imports_private_without_overwriting_the_other_column(self):
        site = dict(cookie_policies=choice('member_', 'shared', None), bypass_cookies=['member_*'])
        migrate_site(site)
        self.assertEqual(len(site['cookie_policies']['rules']), 1)
        row = site['cookie_policies']['rules'][0]
        self.assertEqual(row['id'], 'custom:existing')
        self.assertEqual(row['actions'], dict(basic='shared', ultracache='private'))
        for profile, expected in row['actions'].items():
            snapshot = cookie_control.materialized_snapshot(site=site['cookie_policies'], profile=profile)
            self.assertEqual(action(snapshot['site'], 'member_gold', profile, snapshot['central']), expected)

    def test_normal_site_precedence_does_not_freeze_central_choices(self):
        site = dict(bypass_cookies=['member_*'])
        migrate_site(site)
        for selected in ('shared', 'variant', 'private'):
            central = choice('member_', selected, selected)
            for profile in ('basic', 'ultracache'):
                self.assertEqual(action(site['cookie_policies'], 'member_gold', profile, central), 'private')
                self.assertEqual(action(None, 'member_gold', profile, central), selected)

    def test_validation_is_atomic_and_migration_is_idempotent(self):
        for invalid in ('*', ['valid', 'bad=value'], None):
            site = dict(cookie_policies=choice('member_', 'shared', 'variant'), bypass_cookies=invalid)
            before = copy.deepcopy(site)
            with self.assertRaises(ValueError):
                migrate_site(site)
            self.assertEqual(site, before)
        site = dict(token='owned-fixture-token', profile='ultracache', aliases=['alias.example.test'],
                    custom_recv='', bypass_cookies=['member_*', 'currency'])
        self.assertTrue(migrate_site(site))
        before = copy.deepcopy(site)
        self.assertFalse(migrate_site(site))
        self.assertEqual(site, before)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Native Hestia state modules require Linux')
    def test_normal_desired_state_migrates_and_repeated_upgrade_retains_tokens_and_choices(self):
        from registry import desired_state
        from test_registry import fixture
        inventory = fixture(1, 2)
        old = desired_state(None, inventory, 'varnish')
        site = old['owners']['user000']['sites']['s0.user000.test']
        site.update(cookie_policies=choice('member_gold', 'shared', 'variant', 'exact'), bypass_cookies=['member_*'])
        following = desired_state(old, inventory, 'varnish')
        migrated = following['owners']['user000']['sites']['s0.user000.test']
        self.assertEqual(migrated['token'], site['token'])
        self.assertEqual(migrated['id'], site['id'])
        self.assertNotIn('bypass_cookies', migrated)
        self.assertEqual(desired_state(following, inventory, 'varnish'), following)


@unittest.skipUnless(shutil.which('varnishd'), 'Native varnishd required')
class NativeLegacyCookieMigration(unittest.TestCase):
    def test_normal_migration_uses_only_saved_profile_actions_on_the_wire(self):
        for profile in ('basic', 'ultracache'):
            site = dict(cookie_policies=choice('member_gold', 'shared', 'variant', 'exact'), bypass_cookies=['member_*'])
            migrate_site(site)
            calls = []
            def origin(path, headers):
                calls.append(headers.get('Cookie'))
                return 'public', [('Cache-Control', 'public, max-age=120')]
            with self.subTest(profile=profile), proxy(profile, origin, transform=owned_module, site_settings=site) as get:
                expected = ['MISS', 'HIT', 'HIT'] if profile == 'basic' else ['MISS', 'MISS', 'HIT']
                for value, wanted in zip(('first', 'second', 'first'), expected):
                    status, fields, body = get('/article', 'member_gold='+value)
                    self.assertEqual((status, cache(fields), body), (200, wanted, 'public'))
                self.assertEqual(calls, ['member_gold=first'] if profile == 'basic' else
                                 ['member_gold=first', 'member_gold=second'])
                for _ in range(2):
                    status, fields, _ = get('/article', 'member_silver=private')
                    self.assertEqual((status, cache(fields)), (200, 'PASS'))
                    self.assertEqual(dict(fields).get('X-Cache-Cookie-Action'), 'private')
                self.assertNotIn('site-cookie-rule', get.source)


if __name__ == '__main__':
    unittest.main()
