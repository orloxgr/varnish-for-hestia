"""Real Varnish async-cart parent sharing and private response regressions."""
import shutil
import unittest
import test_cache_policy as policy
import test_profile_compatibility as compatibility


def origin(path, body, headers=(), expect=(), cache='public, max-age=120'):
    return compatibility.response(path, body, headers=['Content-Type: text/html', *headers], expect=expect, policy=cache)


def get(path, body, headers=(), cache=None):
    return compatibility.request(path, body, headers=headers, cache=cache)


@unittest.skipUnless(shutil.which('varnishtest'), 'native varnishtest required')
class AsyncCart(unittest.TestCase):
    run_policy = policy.CachePolicy.run_policy

    def test_warmed_async_parent_is_shared_but_private_cart_endpoints_stay_private(self):
        cart='/?wc-ajax=get_refreshed_fragments'
        self.run_policy('ultracache',
            [origin('/parent','shared-async',['X-UltraCache-Woo-Async-Parent: 1']),
             origin(cart,'cart-A'),origin(cart,'cart-B')],
            [get('/parent','shared-async',cache='MISS'),
             *[get('/parent','shared-async',['Cookie: wp_woocommerce_session_demo='+visitor+'; woocommerce_items_in_cart=1; ultracache_esi_optin=1'],cache='HIT') for visitor in ('A','B')],
             *[get(cart,'cart-'+visitor,['Cookie: wp_woocommerce_session_demo='+visitor+'; ultracache_esi_optin=1'],cache='BYPASS') for visitor in ('A','B')]])
    def test_async_parent_marker_does_not_approve_a_private_cold_miss(self):
        # Even a response marker cannot replace the private-miss ESI handshake.
        self.run_policy('ultracache',
            [origin('/parent',visitor,['X-UltraCache-Woo-Async-Parent: 1'],
                    expect=['expect req.http.X-UltraCache-ESI-Candidate == "1"']) for visitor in ('A','B')],
            [get('/parent',visitor,['Cookie: wp_woocommerce_session_demo='+visitor+'; ultracache_esi_optin=1'],cache='BYPASS') for visitor in ('A','B')])
    def test_async_warmup_does_not_relax_login_no_optin_or_unapproved_object_guards(self):
        cookie='wp_woocommerce_session_demo=A; ultracache_esi_optin=1'
        self.run_policy('ultracache',
            [origin('/parent','approved',['X-UltraCache-Woo-Async-Parent: 1']),
             origin('/parent','logged-in'),origin('/parent','no-optin'),origin('/parent','postpass'),
             origin('/unapproved','anonymous'),origin('/unapproved','private')],
            [get('/parent','approved',cache='MISS'),
             get('/parent','logged-in',['Cookie: '+cookie+'; wordpress_logged_in_demo=admin'],cache='BYPASS'),
             get('/parent','no-optin',['Cookie: wp_woocommerce_session_demo=A'],cache='BYPASS'),
             get('/parent','postpass',['Cookie: '+cookie+'; wp-postpass_demo=secret'],cache='BYPASS'),
             get('/parent','approved',['Cookie: '+cookie],cache='HIT'),
             get('/unapproved','anonymous',cache='MISS'),
             get('/unapproved','private',['Cookie: '+cookie,'X-UltraCache-Woo-Async-Parent: 1'],cache='BYPASS')])
    def test_async_approval_never_overrides_origin_privacy_or_cookie_variation(self):
        for extra,cache in [(['Set-Cookie: PHPSESSID=private'],'public, max-age=120'),
                            ([], 'private, no-store'),(['Surrogate-Control: no-store'],'public, max-age=120')]:
            with self.subTest(extra=extra,cache=cache):self.run_policy('ultracache',
                [origin('/parent','anonymous',['X-UltraCache-Woo-Async-Parent: 1',*extra],cache=cache),
                 origin('/parent','private',extra,cache=cache)],
                [get('/parent','anonymous',cache='BYPASS'),
                 get('/parent','private',['Cookie: wp_woocommerce_session_demo=A; ultracache_esi_optin=1'],cache='BYPASS')])
        self.run_policy('ultracache',
            [origin('/parent','anonymous',['X-UltraCache-Woo-Async-Parent: 1','Vary: Cookie']),origin('/parent','private')],
            [get('/parent','anonymous',cache='MISS'),
             get('/parent','private',['Cookie: wp_woocommerce_session_demo=A; ultracache_esi_optin=1'],cache='BYPASS')])
