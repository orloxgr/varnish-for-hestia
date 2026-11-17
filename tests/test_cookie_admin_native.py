"""Real Varnish choices: shared IDs, explicit variants, precedence and privacy."""
import shutil
import unittest

from test_cookie_admin import settings
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

    def test_private_custom_and_builtin_auth_still_pass(self):
        for profile in compatibility.PROFILES:
            for cookie, choices in [('personal_session=A', settings('personal_session', 'private')),
                                    ('PHPSESSID=A', settings('PHPSESSID', 'shared'))]:
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
