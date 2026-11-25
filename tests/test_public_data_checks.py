"""The publication gate rejects private data without exposing its value."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('public_data_check', Path(__file__).resolve().parents[1] / 'tools/check-public-tree.py')
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class PublicDataChecks(unittest.TestCase):
    def test_private_artifact_names_cannot_be_force_added_unnoticed(self):
        for name in ('.env', '.env.production', 'keys/server.pem', 'backup.sql.gz', 'evidence/result.json'):
            self.assertTrue(CHECK.private_filename(name), name)
        for name in ('.env.example', 'tests/fixtures/private_mutation_wire_v1.json', 'docs/example.md'):
            self.assertFalse(CHECK.private_filename(name), name)

    def test_personal_paths_and_unreserved_addresses_are_rejected(self):
        personal = '/'.join(['C:', 'Users', 'SyntheticPerson', 'Desktop'])
        address = '.'.join(['10', '42', '43', '44'])
        found = list(CHECK.findings('docs/example.md', personal + '\n' + address))
        self.assertEqual(found, [(1, 'personal-or-deployed-home-path'), (2, 'non-documentation-ipv4')])
        self.assertNotIn(address, repr(found))
        self.assertNotIn('SyntheticPerson', repr(found))

    def test_synthetic_home_exception_is_limited_to_path_and_value(self):
        home = '/'.join(['', 'home', 'alice', ''])
        self.assertEqual(list(CHECK.findings('tests/test_native_docroot.py', home)), [])
        self.assertTrue(list(CHECK.findings('docs/new.md', home)))
        other = '/'.join(['', 'home', 'SyntheticCustomer', ''])
        self.assertTrue(list(CHECK.findings('tests/test_native_docroot.py', other)))

    def test_documentation_ip_and_browser_version_are_distinct(self):
        self.assertEqual(list(CHECK.findings('test.py', '192.0.2.5 Chrome/142.0.0.0')), [])
        self.assertTrue(list(CHECK.findings('test.py', '142' + '.0.0.0')))

    def test_external_identifiers_and_private_keys_are_rejected(self):
        self.assertEqual(list(CHECK.findings('notes.md', 'A synthetic customer', ('Synthetic Customer',))), [(1, 'private-denylist-match')])
        key = '-----BEGIN ' + 'PRIVATE KEY-----'
        self.assertEqual(list(CHECK.findings('notes.md', key)), [(1, 'private-key-material')])


if __name__ == '__main__':
    unittest.main()
