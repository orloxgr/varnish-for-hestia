"""Native editor reports profile/legacy precedence rather than a false choice."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'shared'))
import cookie_views
from test_cookie_admin import settings


class CookieViews(unittest.TestCase):
    def view(self,profile='basic',choices=None,bypass=None,central=False,aggressive=False):
        state={'owners':{'alice':{'sites':{'example.test':{'profile':profile,'aliases':[],
            'cookie_policies':choices,'bypass_cookies':bypass or [],'aggressive':aggressive}}}}}
        from cookie_migration import migrate_site
        migrate_site(state['owners']['alice']['sites']['example.test'])
        with patch.object(cookie_views.cookie_database,'database',return_value={'records':[]}), \
             patch.object(cookie_views.cookie_database,'directory',return_value=ROOT/'shared/cookie-recognition'):
            return cookie_views.view(state,None if central else 'alice',None if central else 'example.test')

    def test_basic_cart_rule_reports_the_saved_shared_choice(self):
        data=self.view(choices=settings('woocommerce_cart_hash','shared'))
        row=next(row for row in data['cookie_policy_rows'] if row['id']=='custom:fixture')
        self.assertEqual((row['action'],row['effective_action']),('shared','shared'))
        self.assertNotIn('takes precedence over the table',row['core_precedence'])

    def test_ultracache_and_central_show_each_profile_action_independently(self):
        for central in (False,True):
            with self.subTest(central=central):
                data=self.view(profile='ultracache',central=central)
                row=next(row for row in data['cookie_policy_rows'] if row['name']=='woocommerce_cart_hash')
                self.assertEqual(row['effective_action'],'private' if central else 'shared')
                self.assertEqual(row['profile_actions']['basic']['effective_action'],'private')
                self.assertEqual(row['profile_actions']['ultracache']['effective_action'],'shared')
                self.assertIn('independent of cookie classification',row['core_precedence'])

    def test_saved_rename_reset_preserves_actual_legacy_rule_explanation(self):
        choice=settings('campaign_id','shared',identity='policy:woocommerce-cart-hash')
        data=self.view(choices=choice,bypass=['woocommerce_*'])
        row=next(row for row in data['cookie_policy_rows'] if row['id']=='policy:woocommerce-cart-hash')
        self.assertEqual(row['effective_action'],'shared')
        self.assertEqual(row['reset_metadata']['effective_action'],'private')
        self.assertNotIn('additional bypass cookie rule',row['reset_metadata']['core_precedence'])

    def test_explicit_private_cart_choice_does_not_claim_optional_esi_sharing(self):
        data=self.view(profile='ultracache',choices=settings('woocommerce_cart_hash','private'))
        row=next(row for row in data['cookie_policy_rows'] if row['id']=='custom:fixture')
        self.assertEqual(row['effective_action'],'private')
        self.assertIsNone(row['mode_default_action'])
        self.assertIn('independent of cookie classification',row['core_precedence'])
        self.assertEqual(row['reset_metadata']['effective_action'],'shared')

    def test_aggressive_generic_session_effective_action_and_explicit_private(self):
        data=self.view(aggressive=True)
        row=next(row for row in data['cookie_policy_rows'] if row['name']=='PHPSESSID')
        self.assertEqual(row['effective_action'],'shared')
        self.assertEqual(row['mode_default_action'],'shared')
        self.assertIn('Aggressive caching',row['core_precedence'])
        data=self.view(aggressive=True,choices=settings('PHPSESSID','private'))
        row=next(row for row in data['cookie_policy_rows'] if row['id']=='custom:fixture')
        self.assertEqual(row['effective_action'],'private')
        self.assertEqual(row['mode_default_action'],'shared')
        self.assertEqual(row['reset_metadata']['mode_default_action'],'shared')


if __name__=='__main__':unittest.main()
