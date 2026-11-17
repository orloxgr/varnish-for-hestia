"""Only matching connected application-owned Vary can use canonical variants."""
import shutil
import unittest

from test_cookie_admin import settings
from test_cookie_admin_native import program
import test_cache_policy
import test_profile_compatibility as http
import cookie_control


@unittest.skipUnless(shutil.which('varnishtest'),'native Varnish required')
class CookieVaryContract(unittest.TestCase):
    run_policy=test_cache_policy.CachePolicy.run_policy

    def headers(self,choices,marker='policy-only',digest=None):
        digest=digest or cookie_control.effective_digest('example.test',cookie_control.snapshot(choices))
        return ['Vary: Cookie','X-UltraCache-Cookie-Settings: '+digest,'X-UltraCache-Cookie-Vary: '+marker]

    def test_matching_policy_shares_unknown_automatic_ids_without_losing_variants(self):
        choices=settings('currency','variant')
        for profile in http.PROFILES:
            for connected in (False,True):
                with self.subTest(profile=profile,connected=connected):
                    # Same four visits, two currencies and four unrelated IDs:
                    # ordinary origin Cookie Vary gives four MISSes; the matching
                    # explicit app contract gives two MISSes and two HITs.
                    fetched=('EUR','USD') if connected else ('EUR','EUR','USD','EUR')
                    responses=[http.response('/page',currency,headers=self.headers(choices),
                        expect=['expect req.http.Cookie == "currency=EUR; vendor_id=alice"'] if index==0 else [])
                        for index,currency in enumerate(fetched)]
                    self.run_policy(profile,responses,
                        [http.request('/page','EUR',headers=['Cookie: currency=EUR; vendor_id=alice'],cache='MISS'),
                         http.request('/page','EUR',headers=['Cookie: currency=EUR; vendor_id=bob'],cache='HIT' if connected else 'MISS')+'\nexpect resp.http.Vary ~ "Cookie"',
                         http.request('/page','USD',headers=['Cookie: currency=USD; vendor_id=carol'],cache='MISS'),
                         http.request('/page','EUR',headers=['Cookie: currency=EUR; vendor_id=dave'],cache='HIT' if connected else 'MISS')],
                        program=program(profile,choices,connected=connected))

    def test_mixed_or_mismatched_or_unconnected_origin_vary_remains_authoritative(self):
        choices=settings('currency','variant')
        for profile in http.PROFILES:
            for connected,marker,digest in [(True,'mixed',None),(True,'policy-only','0'*64),(False,'policy-only',None)]:
                with self.subTest(profile=profile,connected=connected,marker=marker,digest=digest):
                    self.run_policy(profile,
                        [http.response('/page',visitor,headers=self.headers(choices,marker,digest)) for visitor in ('alice','bob')],
                        [http.request('/page',visitor,headers=['Cookie: currency=EUR; vendor_id='+visitor],cache='MISS') for visitor in ('alice','bob')],
                        program=program(profile,choices,connected=connected))

    def test_origin_private_policy_still_passes_with_matching_contract(self):
        choices=settings('currency','variant')
        self.run_policy('basic',
            [http.response('/page',visitor,policy='private, no-store',headers=self.headers(choices)) for visitor in ('alice','bob')],
            [http.request('/page',visitor,headers=['Cookie: currency=EUR; vendor_id='+visitor],cache='PASS') for visitor in ('alice','bob')],
            program=program('basic',choices,connected=True))

    def test_browser_cannot_supply_origin_provenance(self):
        choices=settings('currency','variant')
        digest=cookie_control.effective_digest('example.test',cookie_control.snapshot(choices))
        forged=['X-UltraCache-Cookie-Settings: '+digest,'X-UltraCache-Cookie-Vary: policy-only','X-SCP-Cookie-Contract: forged']
        self.run_policy('basic',
            [http.response('/page',visitor,headers=['Vary: Cookie'],expect=[
                'expect req.http.X-UltraCache-Cookie-Settings == <undef>',
                'expect req.http.X-UltraCache-Cookie-Vary == <undef>']) for visitor in ('alice','bob')],
            [http.request('/page',visitor,headers=['Cookie: currency=EUR; vendor_id='+visitor,*forged],cache='MISS') for visitor in ('alice','bob')],
            program=program('basic',choices,connected=True))

    def test_private_only_selector_varies_public_delivery_even_when_cookie_is_absent(self):
        choices=settings('membership','private')
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,[http.response('/page','public')],
                    [http.request('/page','public',cache='MISS')+'\nexpect resp.http.Vary ~ "Cookie"',
                     http.request('/page','public',cache='HIT')+'\nexpect resp.http.Vary ~ "Cookie"'],
                    program=program(profile,choices))

    def test_matching_private_only_contract_shares_public_visitors_and_keeps_private_pass(self):
        choices=settings('membership','private')
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [http.response('/page','public',headers=self.headers(choices)),
                     http.response('/page','personal',headers=self.headers(choices))],
                    [http.request('/page','public',headers=['Cookie: vendor_id=alice'],cache='MISS'),
                     http.request('/page','public',headers=['Cookie: vendor_id=bob'],cache='HIT')+'\nexpect resp.http.Vary ~ "Cookie"',
                     http.request('/page','personal',headers=['Cookie: membership=private; vendor_id=carol'],cache='PASS')+'\nexpect resp.http.Cache-Control == "private, no-store"',
                     http.request('/page','public',headers=['Cookie: vendor_id=dave'],cache='HIT')],
                    program=program(profile,choices,connected=True))

    def test_private_only_unconfirmed_origin_vary_keeps_functional_differences(self):
        choices=settings('membership','private')
        for connected,digest in ((False,None),(True,'0'*64)):
            with self.subTest(connected=connected,digest=digest):
                self.run_policy('basic',
                    [http.response('/page',visitor,headers=self.headers(choices,digest=digest)) for visitor in ('alice','bob')],
                    [http.request('/page',visitor,headers=['Cookie: vendor_id='+visitor],cache='MISS') for visitor in ('alice','bob')],
                    program=program('basic',choices,connected=connected))

    def test_newer_origin_policy_cannot_be_collapsed_by_older_shared_choice(self):
        for name,old in [('preference',settings('preference','shared')),
                         ('_ga',settings('preference','automatic'))]:
            newer=settings(name,'variant')
            for profile in http.PROFILES:
                with self.subTest(profile=profile,name=name):
                    self.run_policy(profile,
                        [http.response('/page',visitor,headers=self.headers(newer)) for visitor in ('alice','bob')],
                        [http.request('/page','alice',headers=['Cookie: '+name+'=alice'],cache='MISS'),
                         http.request('/page','bob',headers=['Cookie: '+name+'=bob'],cache='MISS'),
                         http.request('/page','alice',headers=['Cookie: '+name+'=alice'],cache='HIT'),
                         http.request('/page','bob',headers=['Cookie: '+name+'=bob'],cache='HIT')],
                        program=program(profile,old,connected=True))

    def test_agreed_shared_only_policy_keeps_original_downstream_cookie_vary(self):
        choices=settings('preference','shared')
        self.run_policy('basic',[http.response('/page','public',headers=self.headers(choices))],
            [http.request('/page','public',headers=['Cookie: preference=alice'],cache='MISS'),
             http.request('/page','public',headers=['Cookie: preference=bob'],cache='HIT')+'\nexpect resp.http.Vary ~ "Cookie"'],
            program=program('basic',choices,connected=True))
