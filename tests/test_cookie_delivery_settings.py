"""Delivery configuration, ownership and persistence without an HTTP daemon."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import cookie_policy
import service
from registry import desired_state
from test_cookie_rules import fixture


class CookieDeliverySettings(unittest.TestCase):
    def test_default_is_explicitly_disabled_and_domains_stay_in_account_scope(self):
        self.assertFalse(cookie_policy.normalize_delivery(None,'shop.example.test')['fbp']['enabled'])
        self.assertEqual(cookie_policy.normalize_delivery({'fbp':{'domain':'.example.test'}},
            'shop.example.test',['example.test'])['fbp']['domain'], 'example.test')
        for domain in ('other.test','example.test','test','example.test; Secure'):
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                cookie_policy.normalize_delivery({'fbp':{'domain':domain}},'shop.example.test')

    def test_header_and_vcl_source_cannot_be_injected_through_consent(self):
        for setting in [{'consent_cookie':'x"};return(pass);#'}, {'consent_value':'allow; other=1'},
                        {'consent_value':'allow\r\nSet-Cookie: stolen=1'}, {'enabled':'true'}, {'unknown':True}]:
            with self.subTest(setting=setting), self.assertRaises(ValueError):
                cookie_policy.normalize_delivery({'fbp':setting},'example.test')
        result = cookie_policy.recv_configuration({'fbp':{'enabled':True,'consent_cookie':'cookie.with+regex',
            'consent_value':'a|b'}},'example.test')
        self.assertIn(r'cookie\.with\+regex=a\|b(;|$)', result)

    def test_save_is_site_scoped_and_survives_scan_without_changing_tokens(self):
        state, inventory = fixture()
        before = copy.deepcopy(state)
        def reconcile(hestia, mutate):
            candidate = copy.deepcopy(state)
            mutate(candidate, {'origin_ip':'127.0.0.1'})
            state.clear(); state.update(candidate)
            return state, {}, {}
        value = {'fbp':{'enabled':True,'consent_cookie':'permission','consent_value':'yes'}}
        with patch.object(service,'reconcile',side_effect=reconcile):
            response = service.request(None,'user000','configure-cookie-delivery',
                {'domain':'s0.user000.test','cookie_delivery':value})
            with self.assertRaises(ValueError):
                service.request(None,'user000','configure-cookie-delivery',
                    {'domain':'s0.user001.test','cookie_delivery':value})
        expected = copy.deepcopy(before)
        expected['owners']['user000']['sites']['s0.user000.test']['cookie_delivery'] = cookie_policy.normalize_delivery(value,'s0.user000.test')
        self.assertEqual(state, expected)
        self.assertEqual(desired_state(state,inventory,'varnish'), state)
        self.assertEqual(response['sites'][0]['cookie_delivery'], expected['owners']['user000']['sites']['s0.user000.test']['cookie_delivery'])


if __name__ == '__main__':
    unittest.main()
