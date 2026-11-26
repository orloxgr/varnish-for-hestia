"""Hestia installation scope/ingress using its actual generated native VCL."""
import json
import os
import shutil
import unittest

from test_cookie_delivery import proxy
from test_fragment_batch_runtime import NativeFragmentBatch
from test_fragment_batch_wire import payload, token
from test_public_selection_runtime import control


@unittest.skipUnless(shutil.which('varnishd') and os.environ.get('SCP_TEST_COOKIE_MODULE'),
                     'An isolated matching native module is required')
class HestiaFragmentIngress(unittest.TestCase):
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
