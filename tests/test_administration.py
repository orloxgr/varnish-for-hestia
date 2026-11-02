"""Bulk scope validation, tenant boundaries and preservation of other choices."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import administration
import addon


def fixture():
    def site():
        return {'enabled': True, 'suspended': False, 'profile': 'general',
                'custom_recv': 'return (pass);', 'custom_backend_response': '',
                'token': 'example-test-token', 'aliases': [], 'settings': {}}
    def owner(domains):
        return {'enabled': True, 'suspended': False, 'package': 'default',
                'password': 'example-test-password', 'sites': {name: site() for name in domains}}
    return {'owners': {'alice': owner(['one.example', 'two.example']),
                       'bob': owner(['three.example'])}}


class Administration(unittest.TestCase):
    def setUp(self):
        self.state = fixture()
        self.before = copy.deepcopy(self.state)

    def apply(self, **payload):
        return administration.mutate(self.state, {'scope': 'selected', **payload}, 'varnish')

    def test_profile_changes_selected_owner_sites_preserving_vcl_tokens_and_other_owners(self):
        changed = self.apply(operation='set-profile', profile='ultracache', accounts=['alice'])
        self.assertEqual(changed, {'accounts': 1, 'sites': 2})
        expected = self.before
        for site in expected['owners']['alice']['sites'].values():
            site['profile'] = 'ultracache'
        self.assertEqual(self.state, expected)

    def test_all_scope_covers_every_existing_site(self):
        changed = self.apply(scope='all', operation='set-profile', profile='woocommerce')
        self.assertEqual(changed['sites'], 3)
        self.assertTrue(all(site['profile'] == 'woocommerce' for owner in self.state['owners'].values() for site in owner['sites'].values()))

    def test_mixed_selection_deduplicates(self):
        self.assertEqual(self.apply(operation='disable-sites', accounts=['alice'],
            targets=[{'owner': 'alice', 'domain': 'one.example'}, {'owner': 'bob', 'domain': 'three.example'}])['sites'], 3)
        self.assertTrue(self.state['owners']['alice']['enabled'])

    def test_account_disable_keeps_individual_choices(self):
        self.apply(operation='disable-accounts', accounts=['bob'])
        self.assertFalse(self.state['owners']['bob']['enabled'])
        self.assertEqual(self.state['owners']['bob']['sites'], self.before['owners']['bob']['sites'])

    def test_invalid_later_target_does_not_partially_change_state(self):
        with self.assertRaises(ValueError):
            self.apply(operation='disable-sites', targets=[{'owner': 'alice', 'domain': 'one.example'},
                                                          {'owner': 'alice', 'domain': 'three.example'}])
        self.assertEqual(self.state, self.before)

    def test_empty_unknown_scope_invalid_profile_and_account_are_rejected_without_changes(self):
        for payload in [dict(operation='enable-sites'), dict(operation='enable-sites', accounts=['missing']),
                        dict(operation='enable-sites', scope='unknown'),
                        dict(operation='set-profile', scope='all', profile='invalid')]:
            with self.assertRaises(ValueError):
                self.apply(**payload)
            self.assertEqual(self.state, self.before)

    def test_native_suspension_not_removed(self):
        self.state['owners']['bob']['suspended'] = True
        self.apply(scope='all', operation='enable-accounts')
        self.assertTrue(self.state['owners']['bob']['suspended'])

    def test_overview_never_includes_credentials_or_full_vcl(self):
        response = administration.overview(self.state, {}, 'varnish')
        self.assertEqual(response['total_accounts'], 2)
        self.assertEqual(response['total_sites'], 3)
        for account in response['accounts']:
            self.assertNotIn('password', account)
            for site in account['sites']:
                self.assertNotIn('token', site)
                self.assertNotIn('custom_recv', site)

    def test_native_role_not_caller_flag_controls_global_access(self):
        for role, suspended in [('user', 'no'), ('admin', 'yes')]:
            with patch.object(addon, 'hestia', return_value={'alice': {'ROLE': role, 'SUSPENDED': suspended}}), \
                 patch.object(administration, 'request') as request:
                for action in ('admin-bulk','admin-server-settings','admin-memory'):
                    with self.assertRaises(addon.RequestError):
                        addon.dispatch({'actor': 'alice', 'owner': 'alice', 'action': action, 'admin': True})
                request.assert_not_called()
        with patch.object(addon, 'hestia', return_value={'alice': {'ROLE': 'admin', 'SUSPENDED': 'no'}}), \
             patch.object(administration, 'request', return_value={'ok': True}) as request:
            self.assertTrue(addon.dispatch({'actor': 'alice', 'owner': 'alice', 'action': 'admin-inventory'})['ok'])
            request.assert_called_once()


if __name__ == '__main__':
    unittest.main()
