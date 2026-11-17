"""Old issuer settings cannot reactivate generation after an upgrade."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import service
from registry import desired_state
from test_cookie_rules import fixture
from vcl import render

class CookieDeliverySettings(unittest.TestCase):
    def test_scan_retires_old_issuer_and_preserves_every_other_site_setting(self):
        state, inventory = fixture()
        before = copy.deepcopy(state)
        for owner in state['owners'].values():
            for site in owner['sites'].values():
                site['cookie_delivery'] = {'fbp': {'enabled': True,
                    'consent_cookie': 'old_permission', 'consent_value': 'yes'}}
        self.assertEqual(desired_state(state, inventory, 'varnish'), before)
        for profile in ('basic', 'ultracache'):
            for owner in state['owners'].values():
                for site in owner['sites'].values():
                    site['profile'] = profile
            source = render(state, {'origin_ip': '127.0.0.1'})
            self.assertNotIn('_fbp=fb.', source)
            self.assertNotIn('sub scp_cookie_delivery', source)
            self.assertNotIn('old_permission', source)

    def test_old_update_action_is_no_longer_executable(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported Varnish action'):
            service.request(None, 'user000', 'configure-cookie-delivery',
                {'domain': 's0.user000.test', 'cookie_delivery': {'fbp': {'enabled': True}}})

if __name__ == '__main__':
    unittest.main()
