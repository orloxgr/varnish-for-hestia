"""Real warmed HTTP objects must not answer private source collection requests."""
import http.client
import os
import shutil
import unittest
from test_cookie_delivery import proxy

SOURCE='v1:'+':'.join(value*64 for value in ('a','b','c','d'))
HEADERS={'X-UltraCache-Warm-Source':'raw-v1','X-UltraCache-Internal-Request':'1',
         'X-UltraCache-Warm':'1','X-UltraCache-Session-Source-Kind':'native',
         'X-UltraCache-Session-Source':SOURCE,'Cache-Control':'no-store',
         'X-UltraCache-Runtime-Token':'test-only-origin-validates-this','Accept':'text/html'}
REASON='ultracache-private-session-source'
PATH='/article?utm_source=unchanged&functional=1'
PORTS=tuple(int(value) for value in os.environ.get('HVH_SOURCE_TEST_PORTS','0,0').split(','))


@unittest.skipUnless(shutil.which('varnishd'),'Native Varnish required')
class PrivateSessionSource(unittest.TestCase):
    def test_source_get_passes_warmed_url_and_preserves_original_transport(self):
        for profile in ('basic','ultracache'):
            calls=[]
            def origin(path,headers):
                calls.append((path,dict(headers)))
                return ('raw source' if headers.get('X-UltraCache-Session-Source') else 'cached public'), [('Cache-Control','public, max-age=600')]
            with self.subTest(profile=profile),proxy(profile,origin,ports=PORTS) as get:
                self.assertEqual(dict(get(PATH)[1])['X-Cache'],'MISS')
                self.assertEqual(dict(get(PATH)[1])['X-Cache'],'HIT')
                for kind in ('native','observed'):
                    headers=dict(HEADERS,**{'X-UltraCache-Session-Source-Kind':kind})
                    _,fields,body=get(PATH,extra=headers)
                    self.assertEqual(dict(fields)['X-Cache'],'PASS');self.assertEqual(body,'raw source')
                    self.assertEqual(dict(fields)['X-Hestia-Varnish-Reason'],REASON)
                    self.assertEqual(calls[-1][0],PATH)
                    for name,value in headers.items():self.assertEqual(calls[-1][1][name],value)
                cookies='PHPSESSID=original-provider; esi_session=original-esi; ultracache_esi_optin=1; other=original'
                self.assertEqual(dict(get(PATH,cookies,extra=HEADERS)[1])['X-Cache'],'PASS')
                self.assertEqual(calls[-1][1]['Cookie'],cookies)
                # Private source PASS neither replaces nor invalidates public HTML.
                _,fields,body=get(PATH)
                self.assertEqual(dict(fields)['X-Cache'],'HIT');self.assertEqual(body,'cached public')
                self.assertEqual(len(calls),4)

    def test_near_matches_without_request_no_store_keep_existing_warm_lookup(self):
        invalid=[{}]
        for name in ('X-UltraCache-Warm-Source','X-UltraCache-Internal-Request','X-UltraCache-Warm',
                     'X-UltraCache-Session-Source-Kind','X-UltraCache-Session-Source'):
            row=dict(HEADERS);row.pop(name);invalid.append(row)
        for name,value in [('X-UltraCache-Warm-Source','raw-v2'),('X-UltraCache-Warm','true'),
                           ('X-UltraCache-Internal-Request','true'),('X-UltraCache-Session-Source-Kind','public'),
                           ('X-UltraCache-Session-Source','v2:'+SOURCE[3:]),
                           ('X-UltraCache-Session-Source',SOURCE+'0'),
                           ('X-UltraCache-Session-Source',SOURCE[:-1]),
                           ('X-UltraCache-Session-Source',SOURCE.replace('a','A',1))]:
            invalid.append(dict(HEADERS,**{name:value}))
        # Explicit no-store now independently requests PASS. Remove it to
        # isolate validation of the signed source routing shape below.
        invalid=[{k:v for k,v in row.items() if k!='Cache-Control'} for row in invalid]
        for profile in ('basic','ultracache'):
            calls=[]
            def origin(path,headers):
                calls.append(path);return 'cached public',[('Cache-Control','public, max-age=600')]
            with self.subTest(profile=profile),proxy(profile,origin,ports=PORTS) as get:
                get(PATH)
                for headers in invalid:
                    with self.subTest(headers=tuple(headers.items())):
                        fields=dict(get(PATH,extra=headers)[1])
                        self.assertEqual(fields['X-Cache'],'HIT')
                        self.assertNotEqual(fields['X-Hestia-Varnish-Reason'],REASON)
                client=http.client.HTTPConnection(*get.endpoint,timeout=10)
                try:
                    client.request('HEAD',PATH,headers={'Host':'example.test','X-Forwarded-Proto':'https',
                        **{k:v for k,v in HEADERS.items() if k!='Cache-Control'}})
                    response=client.getresponse();response.read()
                    self.assertEqual(response.getheader('X-Cache'),'HIT')
                    self.assertNotEqual(response.getheader('X-Hestia-Varnish-Reason'),REASON)
                finally:client.close()
                self.assertEqual(len(calls),1)

    def test_source_shape_is_not_authentication_and_response_cookies_are_not_shared(self):
        # A syntactically valid invalid signature must reach application refusal.
        bad=dict(HEADERS,**{'X-UltraCache-Session-Source':SOURCE[:-64]+'0'*64})
        for profile in ('basic','ultracache'):
            calls=[]
            def origin(path,headers):
                calls.append(dict(headers))
                if headers.get('X-UltraCache-Session-Source'):
                    return 'application refused signature',[('Cache-Control','private, no-store'),
                        ('Set-Cookie','PHPSESSID=origin-only; Path=/; HttpOnly'),
                        ('Set-Cookie','other=provider-only; Path=/; SameSite=Lax')]
                return 'cached public',[('Cache-Control','public, max-age=600')]
            with self.subTest(profile=profile),proxy(profile,origin,ports=PORTS) as get:
                get(PATH)
                for _ in range(2):
                    _,fields,body=get(PATH,extra=bad)
                    self.assertEqual(body,'application refused signature')
                    self.assertEqual(dict(fields)['X-Cache'],'PASS')
                    self.assertEqual([v for k,v in fields if k.lower()=='set-cookie'],
                        ['PHPSESSID=origin-only; Path=/; HttpOnly','other=provider-only; Path=/; SameSite=Lax'])
                _,fields,body=get(PATH)
                self.assertEqual(dict(fields)['X-Cache'],'HIT');self.assertEqual(body,'cached public')
                self.assertFalse(any(k.lower()=='set-cookie' for k,v in fields))
                self.assertEqual(len(calls),3)


if __name__=='__main__':unittest.main()
