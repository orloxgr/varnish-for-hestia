"""Hestia installation scope/ingress using its actual generated native VCL."""
import hashlib
import json
import os
import shutil
import unittest

from test_cookie_delivery import proxy
from test_fragment_batch_runtime import NativeFragmentBatch
from test_fragment_batch_wire import payload, token
from test_public_selection_runtime import control
from test_public_fragment_ttl import fields as public_fragment_fields


@unittest.skipUnless(shutil.which('varnishd') and os.environ.get('SCP_TEST_COOKIE_MODULE'),
                     'An isolated matching native module is required')
class HestiaFragmentIngress(unittest.TestCase):
    def test_registered_subset_selects_signed_rows_and_rejects_invalid_membership_before_origin(self):
        value = payload()
        value['sourceUrl'] = '/shop/catalog/'
        value['context']['policy'] = 'b' * 64
        for item in value['fragments']:
            item['url'] = '/shop' + item['url']
        value['fragments'].sort(key=lambda item: item['url'])
        wire = token(value).decode()
        batch_uri = '/shop/index.php?ultracache_fragment_delivery=' + wire
        selected_uri = batch_uri + '&ultracache_fragment_subset=1'
        digest = hashlib.sha256(('ultracache-fragment-delivery-subset-v1\n' + wire + '\n1').encode()).hexdigest()
        seen = []

        def origin(path, headers):
            seen.append(path)
            self.assertEqual(path, selected_uri)
            self.assertEqual(headers.get('X-UltraCache-Delivery-Phase'), 'fragment-prepare')
            self.assertEqual(headers.get('X-UltraCache-Delivery-Authorization'), 'A' * 32)
            self.assertEqual(headers.get('X-UltraCache-Fragment-Delivery-Request-Digest'), digest)
            reply = dict(schemaVersion=2,
                         requestId=headers['X-UltraCache-Delivery-Request'],
                         originalUrl=headers['X-UltraCache-Delivery-Original-URL'],
                         requestDigest=digest,
                         renderedFragments=[dict(value['fragments'][1], html='only-activated-signed-row')],
                         failedFragments=[])
            return json.dumps(reply), [
                ('Content-Type', 'application/vnd.ultracache.fragment-delivery+json; version=1'),
                ('X-UltraCache-Fragment-Delivery-Version', '1'),
                ('Cache-Control', 'private, no-store')]

        with proxy('ultracache', origin) as get:
            declaration = {
                'X-UltraCache-Public-Selection-Reuse-Version': '1',
                'X-UltraCache-Public-Selection-Reuse-Policy': 'c' * 64,
                'X-UltraCache-Fragment-Delivery-Version': '1',
                'X-UltraCache-Fragment-Delivery-Route': '/shop/index.php',
                'X-UltraCache-Fragment-Caching-Enabled': '1',
            }
            registered = control(get, enabled=True, names='', scope='/shop/', extra=declaration)
            self.assertEqual(registered[0], 200, registered)
            self.assertEqual(registered[1].get('X-UltraCache-VCL-Fragment-Subset'), 'indices-v1')
            for selector in ('', '0,0', '1,0', '00', '2', '-1', '%2530', '0,2',
                             '%2B0', '%200', '18446744073709551616'):
                with self.subTest(selector=selector):
                    reply = get(batch_uri + '&ultracache_fragment_subset=' + selector)
                    self.assertEqual(reply[0], 400, reply)
            duplicate = get(selected_uri + '&ultracache_fragment_subset=0')
            self.assertEqual(duplicate[0], 400, duplicate)
            self.assertEqual(seen, [], 'Invalid selection cannot render a full batch at the origin')
            reply = get(selected_uri)
            self.assertEqual(reply[0], 200, reply)
            rows = json.loads(reply[2])['results']
            self.assertEqual([(row['url'], row['html']) for row in rows],
                             [(value['fragments'][1]['url'], 'only-activated-signed-row')])
            self.assertEqual(seen, [selected_uri])

    def test_public_ajax_get_and_esi_share_the_same_native_fragment_object(self):
        parent = '/shop/public-parent/'
        fragment = '/shop/index.php?ultracache_esi=public-fixture&esi_scope=public'
        body = '<html><esi:include src="' + fragment.replace('&', '&amp;') + '"/></html>'
        calls = []

        def origin(path, headers):
            calls.append(path)
            self.assertIsNone(headers.get('X-UltraCache-Delivery-Phase'),
                              'Public fragment delivery must not prepare a document')
            if path == parent:
                return body, [('Cache-Control', 'public, max-age=120'),
                              ('Surrogate-Control', 'ESI/1.0')]
            self.assertEqual(path, fragment)
            self.assertIsNone(headers.get('Cookie'), 'Public fragment context is cookie-free')
            return 'one-public-fragment', public_fragment_fields(30)

        with proxy('ultracache', origin) as get:
            self.assertEqual(get(parent)[2], '<html>one-public-fragment</html>')
            self.assertEqual(calls, [parent, fragment])
            ajax = {'Accept': 'text/html', 'Sec-Fetch-Dest': 'empty'}
            reply = get(fragment, extra=ajax)
            self.assertEqual(reply[2], 'one-public-fragment')
            self.assertEqual(dict(reply[1])['X-Hestia-Varnish'], 'HIT')
            self.assertEqual(calls, [parent, fragment], 'ESI fill must serve Ajax without PHP')
            self.assertEqual(control(get, 'exact-purge', path=fragment)[0], 200)
            self.assertEqual(get(fragment, extra=ajax)[2], 'one-public-fragment')
            self.assertEqual(calls, [parent, fragment, fragment])
            self.assertEqual(get(parent)[2], '<html>one-public-fragment</html>')
            self.assertEqual(calls, [parent, fragment, fragment],
                             'Ajax fill must serve the ESI child without another origin request')

    def test_registered_subdirectory_private_operation_and_inactive_profiles(self):
        value = payload()
        value['sourceUrl'] = '/shop/catalog/'
        value['context']['policy'] = 'b' * 64
        for item in value['fragments']:
            item['url'] = '/shop' + item['url']
        wire = token(value).decode()
        query = '?ultracache_fragment_delivery=' + wire
        uri = '/shop/index.php' + query
        seen = []
        helper = NativeFragmentBatch()

        def origin(path, headers):
            phase = headers.get('X-UltraCache-Delivery-Phase')
            seen.append((path, phase, headers.get('Cookie')))
            if (phase == 'fragment-prepare' and
                    headers.get('X-UltraCache-Delivery-Authorization') == 'A' * 32):
                self.assertEqual(path, uri)
                self.assertEqual(headers.get('X-UltraCache-Delivery-Authorization'), 'A' * 32)
                return helper.response(headers, wire, [dict(item, html='owned output')
                                                        for item in value['fragments']])
            return 'ordinary route', [('Cache-Control', 'public, max-age=120')]

        extra = {
            'X-UltraCache-Public-Selection-Reuse-Version': '1',
            'X-UltraCache-Public-Selection-Reuse-Policy': 'c' * 64,
            'X-UltraCache-Fragment-Delivery-Version': '1',
            'X-UltraCache-Fragment-Delivery-Route': '/shop/index.php',
            'X-UltraCache-Fragment-Caching-Enabled': '1',
        }
        cookie = 'wordpress_logged_in_fixture=actual-owner'
        with proxy('ultracache', origin) as get:
            self.assertEqual(get(uri, cookie)[2], 'ordinary route',
                             'The URL alone cannot negotiate fragment support')
            reply = control(get, enabled=True, names='', scope='/shop/', extra=extra)
            self.assertEqual(reply[0], 200, reply)
            self.assertEqual(reply[1].get('X-UltraCache-VCL-Fragment-Delivery-Route'),
                             '/shop/index.php')
            seen.clear()
            for _ in range(2):
                status, fields, body = get(uri, cookie)
                self.assertEqual(status, 200, (status, fields, body))
                self.assertEqual(len(json.loads(body)['results']), 2)
                self.assertIn('no-store', dict(fields)['Cache-Control'])
            self.assertEqual(seen, [(uri, 'fragment-prepare', cookie)] * 2,
                             'A private operation must retain actual cookies and never cache its JSON')
            seen.clear()
            other = '/other/index.php' + query
            self.assertEqual(get(other, cookie)[2], 'ordinary route')
            self.assertEqual(seen, [(other, None, cookie)],
                             'Another installation must not borrow the registered route')

        for profile, settings in (('basic', {}), ('ultracache', {'enabled': False})):
            with self.subTest(profile=profile, settings=settings):
                seen.clear()
                with proxy(profile, origin, site_settings=settings) as get:
                    self.assertEqual(get(uri, cookie, extra={
                        'X-UltraCache-Fragment-Delivery-Version': '1',
                        'X-UltraCache-Delivery-Phase': 'fragment-prepare',
                        'X-UltraCache-Delivery-Authorization': 'forged',
                    })[2], 'ordinary route')
                    self.assertEqual(len(seen), 1)
                    self.assertEqual((seen[0][0], seen[0][2]), (uri, cookie))


if __name__ == '__main__':
    unittest.main()
