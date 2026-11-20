"""Real Varnish choices: shared IDs, explicit variants, precedence and privacy."""
import shutil
import unittest
from unittest.mock import patch

from test_cookie_admin import settings
import cookie_admin
import test_profile_compatibility as compatibility
import test_cache_policy
from vcl import render


def program(profile, central=None, site=None, *, connected=False):
    state = {'cookie_policies': central, 'owners': {'alice': {
        'enabled': True, 'suspended': False, 'package': 'default', 'sites': {'example.test': {
            'id': 'a'*32, 'aliases': [], 'profile': profile, 'token': 'A'*32,
            'enabled': True, 'suspended': False, 'custom_recv': '', 'custom_backend_response': '',
            'cookie_policies': site, 'cookie_integration': {'enabled':connected,'url':'https://example.test/wp-json/ultracache/v1/cookie-policy-control'}}}}}}
    return render(state, {'origin_ip': '127.0.0.1', 'origin_port': 8080}).replace('"8080"', '"${s1_port}"', 1)


@unittest.skipUnless(shutil.which('varnishtest'), 'native varnishtest is required')
class CookieAdminNative(unittest.TestCase):
    run_policy = test_cache_policy.CachePolicy.run_policy

    def test_grouped_defaults_preserve_nested_prefixes_exact_exceptions_and_overrides(self):
        defaults={'schemaVersion':1,'rules':[]}
        for identity,name,action,kind in (
            ('root','app_','shared','prefix'),('private','app_secret_','private','prefix'),
            ('public','app_secret_public_','shared','prefix'),
            ('variant','app_secret_public_lang_','variant','prefix'),
            ('exact-public','app_secret_exact','shared','exact'),
            ('exact-private','app_public_account','private','exact')):
            defaults['rules']+=settings(name,action,kind=kind,identity='bundled:'+identity)['rules']
        with patch.object(cookie_admin,'defaults',return_value=defaults):
            for profile in compatibility.PROFILES:
                with self.subTest(profile=profile):
                    self.run_policy(profile,
                        [compatibility.response('/nested','public'),compatibility.response('/nested','private'),
                         compatibility.response('/nested','private-exact'),compatibility.response('/nested','EUR'),
                         compatibility.response('/nested','USD')],
                        [compatibility.request('/nested','public',headers=['Cookie: app_secret_public_id=A; app_other=A'],cache='MISS'),
                         compatibility.request('/nested','public',headers=['Cookie: app_secret_public_id=B; app_other=B'],cache='HIT'),
                         compatibility.request('/nested','private',headers=['Cookie: app_secret_token=A'],cache='PASS'),
                         compatibility.request('/nested','public',headers=['Cookie: app_secret_exact=A'],cache='HIT'),
                         compatibility.request('/nested','private-exact',headers=['Cookie: app_public_account=A'],cache='PASS'),
                         compatibility.request('/nested','EUR',headers=['Cookie: app_secret_public_lang_currency=EUR'],cache='MISS'),
                         compatibility.request('/nested','USD',headers=['Cookie: app_secret_public_lang_currency=USD'],cache='MISS'),
                         compatibility.request('/nested','EUR',headers=['Cookie: app_secret_public_lang_currency=EUR'],cache='HIT')],
                        program=program(profile))
                    self.run_policy(profile,[compatibility.response('/override','public')],
                        [compatibility.request('/override','public',headers=['Cookie: app_secret_token=A'],cache='MISS'),
                         compatibility.request('/override','public',headers=['Cookie: app_secret_token=B'],cache='HIT')],
                        program=program(profile,site=settings('app_secret_','shared',kind='prefix')))

    def test_bundled_tracker_hits_without_an_explicit_admin_choice(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [compatibility.response('/default','public',headers=['Vary: Cookie'],
                     expect=['expect req.http.Cookie == "__hstc=alice"'])],
                    [compatibility.request('/default','public',headers=['Cookie: __hstc=alice'],cache='MISS'),
                     compatibility.request('/default','public',headers=['Cookie: __hstc=bob'],cache='HIT')+
                     '\nexpect resp.http.X-Cache-Cookie-Scope == "bundled"\nexpect resp.http.X-Cache-Cookie-Action == "shared"'],
                    program=program(profile))

    def test_absent_and_shared_only_cookies_reuse_the_same_object(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,[compatibility.response('/same','public',headers=['Vary: Cookie'])],
                    [compatibility.request('/same','public',cache='MISS'),
                     compatibility.request('/same','public',headers=['Cookie: __hstc=alice'],cache='HIT'),
                     compatibility.request('/same','public',headers=['Cookie: __hstc=bob'],cache='HIT')],
                    program=program(profile))

    def test_bundled_public_currency_varies_without_origin_vary(self):
        self.run_policy('basic',
            [compatibility.response('/default','EUR'),compatibility.response('/default','USD')],
            [compatibility.request('/default','EUR',headers=['Cookie: cart_currency=EUR'],cache='MISS'),
             compatibility.request('/default','USD',headers=['Cookie: cart_currency=USD'],cache='MISS'),
             compatibility.request('/default','EUR',headers=['Cookie: cart_currency=EUR'],cache='HIT')],
            program=program('basic'))

    def test_bundled_auth0_literal_colon_is_private(self):
        self.run_policy('basic',[compatibility.response('/default','personal')],
            [compatibility.request('/default','personal',headers=['Cookie: a0_users:sess=private'],cache='PASS')+
             '\nexpect resp.http.X-Cache-Cookie-Action == "private"'],program=program('basic'))

    def test_literal_space_name_preserves_every_pair_and_variant(self):
        self.run_policy('basic',
            [compatibility.response('/literal','A',expect=['expect req.http.Cookie == "Site History=A; __hstc=one"']),
             compatibility.response('/literal','B')],
            [compatibility.request('/literal','A',headers=['Cookie: Site History=A; __hstc=one'],cache='MISS'),
             compatibility.request('/literal','B',headers=['Cookie: Site History=B; __hstc=two'],cache='MISS'),
             compatibility.request('/literal','A',headers=['Cookie: Site History=A; __hstc=three'],cache='HIT')],
            program=program('basic',settings('Site History','variant')))

    def test_shared_unknown_cookie_hits_with_vary_and_reaches_origin_unchanged(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [compatibility.response('/page', 'public', headers=['Vary: Cookie'],
                       expect=['expect req.http.Cookie == "tracking_id=alice; language=el"',
                               'expect req.http.X-SCP-Admin-Filtered == <undef>'])],
                    [compatibility.request('/page', 'public', headers=['Cookie: tracking_id=alice; language=el'], cache='MISS'),
                     compatibility.request('/page', 'public', headers=['Cookie: tracking_id=bob; language=el'], cache='HIT')],
                    program=program(profile, settings('tracking_id', 'shared')))

    def test_explicit_tracking_variant_separates_without_origin_vary(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [compatibility.response('/page', 'alice'), compatibility.response('/page', 'bob')],
                    [compatibility.request('/page', 'alice', headers=['Cookie: _ga=alice'], cache='MISS'),
                     compatibility.request('/page', 'bob', headers=['Cookie: _ga=bob'], cache='MISS'),
                     compatibility.request('/page', 'alice', headers=['Cookie: _ga=alice'], cache='HIT') +
                         '\nexpect resp.http.Vary ~ "Cookie"'],
                    program=program(profile, settings('_ga', 'variant')))

    def test_prefix_variant_includes_every_matching_cookie_pair(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [compatibility.response('/page', 'EUR'), compatibility.response('/page', 'USD')],
                    [compatibility.request('/page', 'EUR', headers=['Cookie: other=1; locale_lang=el; locale_currency=EUR'], cache='MISS'),
                     compatibility.request('/page', 'USD', headers=['Cookie: other=1; locale_lang=el; locale_currency=USD'], cache='MISS'),
                     compatibility.request('/page', 'EUR', headers=['Cookie: other=2; locale_lang=el; locale_currency=EUR'], cache='HIT')],
                    program=program(profile, settings('locale_', 'variant', kind='prefix')))

    def test_site_automatic_exact_protects_original_vary_from_central_shared_prefix(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [compatibility.response('/page', 'EUR', headers=['Vary: Cookie']),
                     compatibility.response('/page', 'USD', headers=['Vary: Cookie'])],
                    [compatibility.request('/page', 'EUR', headers=['Cookie: vendor_currency=EUR; vendor_id=a'], cache='MISS'),
                     compatibility.request('/page', 'USD', headers=['Cookie: vendor_currency=USD; vendor_id=b'], cache='MISS'),
                     compatibility.request('/page', 'EUR', headers=['Cookie: vendor_currency=EUR; vendor_id=c'], cache='HIT')],
                    program=program(profile, settings('vendor_', 'shared', kind='prefix'), settings('vendor_currency', 'automatic')))

    def test_explicit_and_default_private_choices_still_pass(self):
        for profile in compatibility.PROFILES:
            for cookie, choices in [('personal_session=A', settings('personal_session', 'private')),
                                    ('PHPSESSID=A', None)]:
                with self.subTest(profile=profile, cookie=cookie):
                    self.run_policy(profile,
                        [compatibility.response('/page', visitor) for visitor in ('A', 'B')],
                        [compatibility.request('/page', visitor, headers=['Cookie: '+cookie], cache='PASS') for visitor in ('A', 'B')],
                        program=program(profile, choices))

    def test_forged_internal_rules_do_not_change_lookup(self):
        self.run_policy('basic', [compatibility.response('/page', 'public')],
            [compatibility.request('/page', 'public', cache='MISS'), compatibility.request('/page', 'public', cache='HIT',
               headers=['X-SCP-Admin-Variant: forged=private', 'X-SCP-Admin-Rule: fake', 'X-SCP-Admin-Filtered: forged=1'])],
            program=program('basic'))

    def test_explicit_variant_without_cookie_has_downstream_vary(self):
        self.run_policy('basic', [compatibility.response('/page', 'public')],
            [compatibility.request('/page', 'public', cache='MISS') + '\nexpect resp.http.Vary ~ "Cookie"',
             compatibility.request('/page', 'public', cache='HIT') + '\nexpect resp.http.Vary ~ "Cookie"'],
            program=program('basic', settings('currency', 'variant')))

    def test_explicit_private_delivery_is_not_public_downstream(self):
        self.run_policy('basic', [compatibility.response('/page', 'personal')],
            [compatibility.request('/page', 'personal', headers=['Cookie: membership=alice'], cache='PASS') +
             '\nexpect resp.http.Cache-Control == "private, no-store"'],
            program=program('basic', settings('membership', 'private')))

    def test_later_private_match_reports_its_actual_cause_after_shared_match(self):
        choices = settings('analytics', 'shared')
        choices['rules'] += settings('membership', 'private', identity='custom:member')['rules']
        self.run_policy('basic', [compatibility.response('/page', 'personal')],
            [compatibility.request('/page', 'personal', headers=['Cookie: analytics=1; membership=alice'], cache='PASS') +
             '\nexpect resp.http.Cache-Control == "private, no-store"\nexpect resp.http.X-Cache-Cookie-Rule == "custom:member"'],
            program=program('basic', choices))

    def test_variant_diagnostic_takes_precedence_over_earlier_shared_rule(self):
        choices=settings('tracking_identifier','shared')
        choices['rules'] += settings('currency','variant',identity='custom:currency')['rules']
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,[compatibility.response('/page','EUR')],
                    [compatibility.request('/page','EUR',headers=['Cookie: tracking_identifier=private-id; currency=EUR'],cache='MISS')+
                     '\nexpect resp.http.X-Cache-Cookie-Rule == "custom:currency"\nexpect resp.http.X-Cache-Cookie-Names == "currency"\nexpect resp.http.X-Cache-Cookie-Action == "variant"'],
                    program=program(profile,choices))

    def test_prefix_variant_diagnostics_list_names_without_their_values(self):
        self.run_policy('basic',[compatibility.response('/page','EUR')],
            [compatibility.request('/page','EUR',headers=['Cookie: locale_language=el; locale_currency=EUR'],cache='MISS')+
             '\nexpect resp.http.X-Cache-Cookie-Names == "locale_language, locale_currency"'],
            program=program('basic',settings('locale_','variant',kind='prefix')))
