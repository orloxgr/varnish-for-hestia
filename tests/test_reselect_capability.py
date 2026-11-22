"""Explicit supported reselection is visible only in authenticated UC probes."""
import shutil
import unittest
from test_cookie_delivery import proxy
from test_public_selection_runtime import control

MARKER='X-UltraCache-VCL-Publication-Reselect-Version'


@unittest.skipUnless(shutil.which('varnishd'),'Native Varnish required; skips are not acceptance')
class ReselectCapability(unittest.TestCase):
    def test_authenticated_uc_capability_and_plain_probe_preserve_registration(self):
        def origin(path,headers):
            return 'plain',[('Cache-Control','public, max-age=120'),(MARKER,'origin-forged')]
        for profile in ('basic','ultracache'):
            with self.subTest(profile=profile),proxy(profile,origin)as get:
                status,fields,_=control(get)
                self.assertEqual(status,200)
                self.assertEqual(fields.get(MARKER),'1'if profile=='ultracache'else None)
                for path in ('/ordinary','/wp-admin/'):
                    response=get(path,extra={MARKER:'client-forged','X-UltraCache-Operation':'capabilities'})
                    self.assertEqual(response[0],200)
                    self.assertNotIn(MARKER,dict(response[1]))
                status,fields,_=control(get,operation='exact-purge',path='/ordinary')
                self.assertEqual(status,200)
                self.assertNotIn(MARKER,fields)
                if profile=='ultracache':
                    self.assertEqual(control(get,enabled=True,names='')[0],200)
                    declared=control(get)[1]
                    self.assertEqual(declared[MARKER],'1')
                    self.assertRegex(declared['X-UltraCache-VCL-Public-Selection-WordPress-Policy'],r'^[a-f0-9]{64}$')

    def test_failed_auth_wrong_endpoint_and_invalid_declaration_do_not_advertise(self):
        with proxy('ultracache',lambda path,headers:('plain',[]))as get:
            for options in ({'token':False},{'path':'/wrong-capabilities-endpoint'},
                {'enabled':True,'names':'','wordpress_policy':'invalid'}):
                status,fields,_=control(get,extra={MARKER:'client-forged'},**options)
                self.assertIn(status,(400,403))
                self.assertNotIn(MARKER,fields)


if __name__=='__main__':unittest.main()
