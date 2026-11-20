import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))
import cookie_admin as admin
from cookie_catalogue import load_catalogue


def settings(name, action, *, kind='exact', identity='custom:fixture'):
    return {'schemaVersion': 1, 'rules': [{'id': identity, 'match': {'kind': kind, 'value': name},
                                         'description': 'Fixture choice', 'action': action}]}


class CookieAdmin(unittest.TestCase):
    def test_scope_specificity_and_explicit_automatic(self):
        central = settings('vendor_', 'private', kind='prefix')
        site = settings('vendor_id', 'automatic')
        result = admin.resolve(central, site)
        self.assertEqual([(r['scope'], r['action']) for r in result], [('site', 'automatic'), ('central', 'private')])
        self.assertEqual(admin.normalize(site), site)

    def test_conflicting_same_scope_choices_are_rejected_without_changing_input(self):
        value = settings('currency', 'variant')
        other = copy.deepcopy(value['rules'][0]); other.update(id='custom:other', action='shared')
        value['rules'].append(other)
        before = copy.deepcopy(value)
        with self.assertRaises(ValueError):
            admin.normalize(value)
        self.assertEqual(value, before)

    def test_untrusted_metadata_never_becomes_source(self):
        for name in ['x"};return(pass);#', 'x\ninclude', 'a=b', 'a;b']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                admin.compile_vcl(settings(name, 'private'))
        value = settings('literal.+name', 'shared')
        value['rules'][0]['description'] = '</textarea><script>alert(1)</script>'
        source = admin.compile_vcl(value)
        self.assertNotIn('<script>', source)
        self.assertIn(r'literal\.\+name', source)

    def test_database_is_visible_and_user_snapshot_survives_metadata_changes(self):
        catalogue = load_catalogue()
        database = {'records': [{'id': 'fixture', 'name': 'custom_cookie', 'provider': 'Example', 'category': 'Analytics'}]}
        choices = settings('custom_cookie', 'variant', identity='ocd:fixture')
        rows = admin.table(database, catalogue, site=choices)
        row = next(r for r in rows if r['id'] == 'ocd:fixture')
        self.assertEqual((row['action'], row['scope'], row['proposal']), ('variant', 'site', 'variant'))
        self.assertTrue(row['override'])
        database['records'][0]['category'] = 'Security'
        self.assertIn(('site', 'exact', 'custom_cookie', 'variant'), admin.executable(site=choices))
        self.assertEqual(next(r for r in admin.table(database, catalogue, site=choices) if r['id'] == 'ocd:fixture')['action'], 'variant')

    def test_bundled_actions_compile_and_metadata_edits_do_not_purge(self):
        value = settings('currency', 'variant')
        before = admin.executable(value)
        value['rules'][0].update(description='A better description', id='custom:renamed')
        self.assertEqual(before, admin.executable(value))
        self.assertIn('bundled:shared', admin.compile_vcl())
        self.assertIn('bundled:variant', admin.compile_vcl())
        self.assertIn('bundled:private', admin.compile_vcl())

    def test_shadowed_central_changes_do_not_invalidate_site(self):
        site = settings('foo', 'shared')
        self.assertEqual(admin.executable(settings('foo', 'variant'), site),
                         admin.executable(settings('foo', 'private'), site))
        self.assertNotEqual(admin.executable(settings('fo', 'variant', kind='prefix'), site),
                            admin.executable(settings('fo', 'private', kind='prefix'), site))

    def test_renamed_snapshot_does_not_inherit_unrelated_private_claim(self):
        catalogue = load_catalogue()
        private = next(p for p in catalogue['policies'] if p['consumers']['varnishPrivate'])
        rule = settings('campaign_id', 'shared', identity='policy:' + private['id'])
        row = next(row for row in admin.table({'records': []}, catalogue, site=rule)
                   if row['id'] == 'policy:' + private['id'])
        self.assertEqual((row['action'], row['effective_action'], row['proposal']), ('shared', 'shared', 'variant'))
        self.assertEqual(row['provider'], '')
        self.assertEqual(row['reset_match'], private['match'])
        self.assertNotIn('requires private handling', row['core_precedence'])
        self.assertNotIn('requires private handling',row['reset_metadata']['core_precedence'])
        self.assertEqual(row['reset_metadata']['effective_action'],'private')


if __name__ == '__main__':
    unittest.main()
