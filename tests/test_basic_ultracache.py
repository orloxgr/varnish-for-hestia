"""Public read reuse, real private state and the two-preset upgrade on Linux."""
import shutil
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_cache_policy as policy
import test_profile_compatibility as http
from registry import desired_state
from test_registry import fixture
import profile_settings
import service


class PresetUpgrade(unittest.TestCase):
    def test_old_presets_fold_once_without_losing_effective_rules_or_credentials(self):
        inventory = fixture(1, 4)
        previous = desired_state(None, inventory, 'varnish')
        sites = list(previous['owners']['user000']['sites'].values())
        names = ['general', 'wordpress', 'woocommerce', 'ultracache']
        rules = {name: dict(custom_recv='set req.http.X-User-Central = "'+name+'";',
                            custom_backend_response='set beresp.ttl = 30m;') for name in names}
        previous['profile_settings'] = dict(default_profile='woocommerce', rules=rules)
        for site, name in zip(sites, names):
            site.update(profile=name, custom_recv='set req.http.X-User-Local = "kept";',
                        custom_backend_response='set beresp.grace = 1m;', bypass_cookies=['membership_*'])
        result = desired_state(previous, inventory, 'varnish')
        upgraded = list(result['owners']['user000']['sites'].values())
        for old, new in zip(sites, upgraded):
            for key in ('id', 'token', 'enabled', 'bypass_cookies', 'settings'):
                self.assertEqual(old[key], new[key])
            self.assertEqual(new['profile'], 'ultracache' if old['profile'] == 'ultracache' else 'basic')
            if new['profile'] == 'basic':
                self.assertIn('"'+old['profile']+'"', new['custom_recv'])
                self.assertLess(new['custom_recv'].index('Central'), new['custom_recv'].index('Local'))
                self.assertIn('beresp.ttl', new['custom_backend_response'])
                self.assertIn('beresp.grace', new['custom_backend_response'])
            else:
                self.assertEqual(old, new)
        self.assertEqual(result['profile_settings']['default_profile'], 'basic')
        self.assertEqual(set(result['profile_settings']['rules']), {'basic', 'ultracache'})
        self.assertEqual(result, desired_state(result, inventory, 'varnish'))
        self.assertEqual(previous['profile_settings']['default_profile'], 'woocommerce')

    def test_renderer_has_only_two_presets_and_rejects_old_runtime_selection(self):
        self.assertEqual(http.PROFILES, ('basic', 'ultracache'))
        for old in ('general', 'wordpress', 'woocommerce'):
            with self.assertRaises(ValueError):
                http.program(old)
        with self.assertRaises(ValueError):
            profile_settings.choices({'profile_settings': {'default_profile': 'wordpress'}})

    def test_applying_converted_state_accepts_old_applied_profiles_and_invalidates_scope(self):
        inventory = fixture(1, 1)
        previous = desired_state(None, inventory, 'varnish')
        old = next(iter(previous['owners']['user000']['sites'].values()))
        old['profile'] = 'wordpress'
        previous['profile_settings'] = dict(default_profile='wordpress', rules={
            'wordpress': dict(custom_recv='set req.http.X-User-Kept = "yes";', custom_backend_response='')})
        after = desired_state(previous, inventory, 'varnish')
        config = {'origin_ip': '127.0.0.1', 'origin_port': 8080}
        source = http.render(after, config)
        generation = 'hvh_gen_' + hashlib.sha256(source.encode()).hexdigest()[:32]
        with tempfile.TemporaryDirectory() as folder:
            active = Path(folder) / 'active.vcl'
            active.write_text(source)
            with patch.object(service, 'ACTIVE', active), \
                 patch.object(service, 'vcls', return_value=[{'name': generation, 'status': 'active'}]), \
                 patch.object(service.routing, 'apply', return_value=({}, None)), \
                 patch.object(service.routing, 'apache_config', return_value=''), \
                 patch.object(service, 'purge') as purge, patch.object(service, 'prune'):
                result = service.apply(after, previous, {}, config, changes=[])
                self.assertEqual(result['invalidated_sites'], 1)
                self.assertEqual(purge.call_count, 1)
                self.assertEqual(purge.call_args.args[1]['token'], old['token'])


@unittest.skipUnless(shutil.which('varnishtest'), 'native varnishtest required')
class PublicReads(unittest.TestCase):
    run_policy = policy.CachePolicy.run_policy

    def test_search_rest_ajax_and_ref_are_public_candidates_with_distinct_query_values(self):
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                responses, requests = [], []
                for path in ['/?s=boots', '/?s=books', '/wp-json/wp/v2/posts',
                             '/?rest_route=/wp/v2/posts', '/public-api?query=one',
                             '/?ref=alice', '/?ref=bob', '/?utm_source=newsletter&product=2']:
                    responses.append(http.response(path, path))
                    requests.extend([http.request(path, path, headers=['X-Requested-With: XMLHttpRequest'], cache='MISS'),
                                     http.request(path, path, headers=['Cookie: _ga=visitor-B'], cache='HIT')])
                self.run_policy(profile, responses, requests)

    def test_referral_cookie_is_delivered_to_each_visitor_and_never_replayed(self):
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [http.response('/?ref=alice', 'A', headers=['Set-Cookie: affiliate=alice; Path=/']),
                     http.response('/?ref=alice', 'B', headers=['Set-Cookie: affiliate=alice; Path=/']),
                     http.response('/?ref=bob', 'bob-public')],
                    [http.request('/?ref=alice', 'A', cache='PASS'),
                     'expect resp.http.Set-Cookie == "affiliate=alice; Path=/"',
                     http.request('/?ref=alice', 'B', cache='PASS'),
                     'expect resp.http.Set-Cookie == "affiliate=alice; Path=/"',
                     http.request('/?ref=bob', 'bob-public', cache='MISS'),
                     http.request('/?ref=bob', 'bob-public', cache='HIT')])

    def test_vary_cookie_ignores_only_analytics_and_preserves_unknown_functional_values(self):
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [http.response('/page', 'public', headers=['Vary: Cookie'],
                         expect=['expect req.http.Cookie == <undef>']),
                     http.response('/page', 'el', headers=['Vary: Cookie'],
                         expect=['expect req.http.Cookie == "_ga=one; locale=el; sbjs_session=one"']),
                     http.response('/page', 'en', headers=['Vary: Cookie'],
                         expect=['expect req.http.Cookie == "locale=en; _gid=one"'])],
                    [http.request('/page', 'public', cache='MISS'),
                     http.request('/page', 'public', headers=['Cookie: _ga=one; sbjs_session=one'], cache='HIT'),
                     http.request('/page', 'el', headers=['Cookie: _ga=one; locale=el; sbjs_session=one'], cache='MISS'),
                     http.request('/page', 'el', headers=['Cookie: locale=el; _ga=two; sbjs_session=two'], cache='HIT'),
                     'expect resp.http.Vary ~ "Cookie"',
                     'expect resp.http.Vary !~ "X-HVH"',
                     http.request('/page', 'en', headers=['Cookie: locale=en; _gid=one'], cache='MISS'),
                     http.request('/page', 'en', headers=['Cookie: _gid=two; locale=en'], cache='HIT')])

    def test_equivalent_accept_spacing_reuses_variant_and_q_zero_keeps_its_meaning(self):
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [http.response('/negotiate', 'html', headers=['Vary: Accept', 'Content-Type: text/html'],
                         expect=['expect req.http.Accept == "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"']),
                     http.response('/negotiate', 'json', headers=['Vary: Accept', 'Content-Type: application/json'],
                         expect=['expect req.http.Accept == "text/html;q=0, application/json"']),
                     http.response('/negotiate', 'webp', headers=['Vary: Accept', 'Content-Type: image/webp'],
                         expect=['expect req.http.Accept == "image/avif;q=0, image/webp;q=0.5"'])],
                    [http.request('/negotiate', 'html', headers=['Accept: text/html,application/xhtml+xml;q=0.9,*/*;q=0.8'], cache='MISS'),
                     http.request('/negotiate', 'html', headers=['Accept: text/html, application/xhtml+xml; q=0.9, */*; q=0.8'], cache='HIT'),
                     http.request('/negotiate', 'json', headers=['Accept: text/html;q=0, application/json'], cache='MISS'),
                     http.request('/negotiate', 'webp', headers=['Accept: image/avif;q=0, image/webp;q=0.5'], cache='MISS'),
                     http.request('/negotiate', 'html', headers=['Accept: text/html,application/xhtml+xml;q=0.9,*/*;q=0.8'], cache='HIT')])

    def test_warmup_and_browser_reuse_parent_without_a_declared_accept_variant(self):
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [http.response('/index.html', '<html>shared</html>',
                        headers=['Content-Type: text/html', 'Vary: Cookie'],
                        expect=['expect req.http.User-Agent == "UltraCacheWarm"'])],
                    [http.request('/index.html', '<html>shared</html>',
                        headers=['User-Agent: UltraCacheWarm', 'Accept: text/html'], cache='MISS'),
                     http.request('/index.html', '<html>shared</html>',
                        headers=['User-Agent: Mozilla/5.0', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                                 'Cookie: _ga=browser; sbjs_current=campaign'], cache='HIT')])

    def test_two_woo_sessions_cannot_reuse_notices_from_ordinary_parent_or_store_api(self):
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                responses = [http.response('/product', 'public')]
                requests = [http.request('/product', 'public', cache='MISS')]
                for path in ['/product', '/wp-json/wc/store/v1/cart',
                             '/?rest_route=%2Fwc%2Fstore%2Fv1%2Fcart', '/?wc-ajax=get_refreshed_fragments']:
                    for visitor in ['A', 'B']:
                        cookie = 'wp_woocommerce_session_demo='+visitor
                        if profile == 'ultracache': cookie += '; ultracache_esi_optin=1'
                        responses.append(http.response(path, 'notice-'+visitor))
                        requests.append(http.request(path, 'notice-'+visitor, headers=['Cookie: '+cookie], cache='PASS'))
                requests.append(http.request('/product', 'public', cache='HIT'))
                self.run_policy(profile, responses, requests)

    def test_private_rest_routes_and_credentials_always_pass_even_after_public_warmup(self):
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                paths = ['/wp-json/wc/store/v1/cart', '/wp-json/wc/store/v1/checkout',
                         '/?rest_route=/wc/store/v1/cart', '/wp-json/wp/v2/users/me',
                         '/?context=edit', '/?add-to-cart=42', '/?remove_item=abc']
                responses, requests = [], []
                for path in paths:
                    for who in ['A', 'B']:
                        responses.append(http.response(path, who))
                        requests.append(http.request(path, who, cache='PASS'))
                for header in ['X-WP-Nonce: A', 'Cart-Token: A', 'Nonce: A']:
                    responses.append(http.response('/wp-json/wc/store/v1/products', 'private'))
                    requests.append(http.request('/wp-json/wc/store/v1/products', 'private', headers=[header], cache='PASS'))
                self.run_policy(profile, responses, requests)

    def test_status_and_reason_are_consistent_for_origin_and_request_privacy(self):
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [http.response('/public', 'public'),
                     http.response('/cookie', 'private', headers=['Set-Cookie: sid=A']),
                     http.response('/private', 'private', policy='private, no-store'),
                     http.response('/wp-login.php', 'login')],
                    [http.request('/public', 'public', cache='MISS'),
                     'expect resp.http.X-Cache == "MISS"',
                     'expect resp.http.X-Hestia-Varnish-Reason == "fetch-required"',
                     http.request('/public', 'public', cache='HIT'),
                     'expect resp.http.X-Cache == "HIT"',
                     http.request('/cookie', 'private', cache='PASS'),
                     'expect resp.http.X-Cache == "PASS"',
                     'expect resp.http.X-Hestia-Varnish-Reason == "origin-set-cookie"',
                     'expect resp.http.Cache-Control == "public, max-age=120"',
                     http.request('/private', 'private', cache='PASS'),
                     'expect resp.http.X-Hestia-Varnish-Reason == "origin-cache-policy"',
                     http.request('/wp-login.php', 'login', cache='PASS'),
                     'expect resp.http.X-Hestia-Varnish-Reason == "wordpress-private-route"',
                     'expect resp.http.X-HVH-Pass-Reason == <undef>'])

    def test_esi_cannot_erase_downstream_privacy_of_composed_or_unapproved_parent(self):
        for headers, cookie, reason in [
            (['Content-Type: text/html', 'Surrogate-Control: ESI/1.0, no-store'], None, 'origin-surrogate-control'),
            (['Content-Type: text/html'], 'wp_woocommerce_session_demo=A; ultracache_esi_optin=1', 'unapproved-private-parent')]:
            with self.subTest(reason=reason):
                request_headers = ['Cookie: '+cookie] if cookie else []
                self.run_policy('ultracache',
                    [http.response('/parent', '<html>private</html>', headers=headers)],
                    [http.request('/parent', '<html>private</html>', headers=request_headers, cache='PASS'),
                     'expect resp.http.Cache-Control == "private, no-store"',
                     'expect resp.http.X-Hestia-Varnish-Reason == "'+reason+'"'])

    def test_client_cannot_forge_esi_capability_or_private_transport_in_basic(self):
        self.run_policy('basic',
            [http.response('/parent', 'public', expect=[
                'expect req.http.Surrogate-Capability == <undef>',
                'expect req.http.X-UltraCache-ESI-Candidate == <undef>',
                'expect req.http.X-ESI-Private-Request == <undef>',
                'expect req.http.X-ESI-Original-Cookie == <undef>'])],
            [http.request('/parent', 'public', headers=[
                'Surrogate-Capability: varnish=ESI/1.0',
                'X-SCP-Profile: ultracache', 'X-SCP-Key-URL: /forged',
                'X-SCP-Pass: 1', 'X-SCP-Reason: forged',
                'X-UltraCache-ESI-Candidate: 1', 'X-ESI-Private-Request: 1',
                'X-ESI-Original-Cookie: wp_woocommerce_session_demo=forged'], cache='MISS'),
             http.request('/parent', 'public', cache='HIT')])

    def test_gzip_q_zero_is_respected_when_reusing_compressed_object(self):
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    ['accept\nrxreq\nexpect req.url == "/compressed"\n'
                     'txresp -hdr "Connection: close" -hdr "Cache-Control: public, max-age=120" '
                     '-hdr "Content-Type: text/html" -gzipbody {<html>compressed</html>}'],
                    ['txreq -url /compressed -hdr "Host: example.test" -hdr "Accept-Encoding: gzip"\n'
                     'rxresp\nexpect resp.http.Content-Encoding == "gzip"\ngunzip\n'
                     'expect resp.body == {<html>compressed</html>}',
                     http.request('/compressed', '<html>compressed</html>',
                         headers=['Accept-Encoding: gzip;q=0, identity;q=1'], cache='HIT'),
                     'expect resp.http.Content-Encoding == <undef>'])
