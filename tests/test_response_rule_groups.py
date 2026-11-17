"""Different editorial IDs must not duplicate the same native response rules."""
import re
import shutil
import unittest

from test_cookie_delivery import proxy,cookies
from test_cookie_admin import settings
from vcl import render


def state():
    sites={}
    for i in range(48):
        sites['site-'+str(i)+'.example.test']={
            'id':format(i,'032x'),'aliases':[],'profile':'basic','token':'A'*32,
            'enabled':True,'suspended':False,'custom_recv':'','custom_backend_response':'',
            'cookie_policies':settings('tracking_choice','shared' if i%2 else 'variant',identity='row:'+str(i))}
    return {'owners':{'alice':{'enabled':True,'suspended':False,'package':'default','sites':sites}}}


class ResponseRuleGroups(unittest.TestCase):
    def test_identical_execution_is_emitted_once_while_request_diagnostics_remain_scoped(self):
        source=render(state(),{'origin_ip':'127.0.0.1','origin_port':8080})
        self.assertEqual(source.count('cookie_handoff.detach('),2)
        self.assertIn('row:0',source);self.assertIn('row:47',source)

    @unittest.skipUnless(shutil.which('varnishd'),'Native Varnish required')
    def test_many_site_overrides_keep_shared_and_variant_response_behavior(self):
        def origin(path,headers):
            return headers['Host'],[('Cache-Control','public, max-age=120'),('Set-Cookie','tracking_choice=original; Path=/')]
        def transform(source):
            port=int(re.search(r'\.port = "(\d+)"',source).group(1))
            return render(state(),{'origin_ip':'127.0.0.1','origin_port':port})
        with proxy('basic',origin,transform=transform) as get:
            for i in range(48):
                host='site-'+str(i)+'.example.test'
                for attempt in range(2):
                    _,fields,body=get('/page',extra={'Host':host})
                    self.assertEqual(body,host)
                    expected=('MISS' if attempt==0 else 'HIT') if i%2 else 'PASS'
                    self.assertEqual(dict(fields)['X-Cache'],expected)
                    self.assertEqual(cookies(fields),[] if expected=='HIT' else ['tracking_choice=original; Path=/'])


if __name__=='__main__':unittest.main()
