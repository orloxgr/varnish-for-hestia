"""Native Hestia public caching, selected TTL and unchanged origin/browser data."""
import copy
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from test_cookie_delivery import proxy
from test_cookie_rules import fixture
import aggressive
import cache_behavior
import cms_routes
import cms_inventory
from vcl import render
import service


class SiteCacheSettings(unittest.TestCase):
    def test_defaults_do_not_enable_or_migrate_existing_sites(self):
        state,_=fixture(); before=copy.deepcopy(state)
        render(state,{'origin_ip':'127.0.0.1','origin_port':8080})
        self.assertEqual(state,before)
        self.assertEqual(aggressive.settings({}),{'aggressive':False,'aggressive_ttl':86400})

    def test_change_is_site_scoped_and_retains_token_profile_browser_settings(self):
        state,_=fixture(); before=copy.deepcopy(state)
        site=state['owners']['user000']['sites']['s0.user000.test']
        cache_behavior.change(site,{'aggressive':True,'aggressive_ttl':604800,'custom_private_paths':'/members\n/custom-checkout/\n/members'})
        self.assertEqual(site['custom_private_paths'],['/members','/custom-checkout/'])
        self.assertEqual(site['token'],before['owners']['user000']['sites']['s0.user000.test']['token'])
        self.assertEqual(state['owners']['user001'],before['owners']['user001'])
        for value in (0,-1,True,1.5,'123'):
            with self.assertRaises(cache_behavior.CachePolicyError):cache_behavior.change(site,{'aggressive':True,'aggressive_ttl':value})
        for value in ('relative','/../escape','/path?query','/bad\\path'):
            with self.assertRaises(cache_behavior.CachePolicyError):cache_behavior.change(site,{'custom_private_paths':value})

    def test_scan_timestamp_alone_does_not_invalidate_cache(self):
        first={'cms_discovery':{'checked_utc':'old'}}
        second={'cms_discovery':{'checked_utc':'new'}}
        self.assertEqual(cache_behavior.execution(first),cache_behavior.execution(second))

    def test_changed_native_docroot_is_refreshed_once_without_repeated_panel_scans(self):
        site={'cms_document_root':'/old/root'}
        state={'owners':{'alice':{'sites':{'example.test':site}}}}
        inventory={'alice':{'sites':{'example.test':{'document_root':'/new/root'}}}}
        self.assertEqual(cms_inventory.changed_roots(state,inventory),{('alice','example.test')})
        self.assertEqual(site['cms_pending_root'],'/new/root')
        self.assertEqual(cms_inventory.changed_roots(state,inventory),set())
        inventory['alice']['sites']['example.test']['document_root']='/old/root'
        self.assertEqual(cms_inventory.changed_roots(state,inventory),set())
        self.assertNotIn('cms_pending_root',site)

    def test_site_action_checks_ownership_and_refreshes_only_selected_native_site(self):
        state,_=fixture(); scopes=[]
        def reconcile(hestia,mutation=None,**kwargs):
            if mutation:mutation(state,{})
            scopes.append(kwargs.get('cms_scope'))
            return state,{},{}
        with patch.object(service,'reconcile',side_effect=reconcile):
            result=service.request(None,'user000','configure-cache-policy',{
                'domain':'s0.user000.test','aggressive':True,'aggressive_ttl':604800,'custom_private_paths':'/members/'})
            self.assertEqual(scopes,[{('user000','s0.user000.test')}])
            self.assertTrue(result['sites'][0]['aggressive'])
            self.assertEqual(result['sites'][0]['aggressive_ttl'],604800)
            with self.assertRaises(ValueError):service.request(None,'user000','configure-cache-policy',{
                'domain':'s0.user001.test','aggressive':True})

    def test_effective_cache_change_invalidates_only_its_site_and_scans_do_not(self):
        for change,expected in [('enable',1),('timestamp',0)]:
            previous,_=fixture();state=copy.deepcopy(previous)
            site=state['owners']['user000']['sites']['s0.user000.test']
            if change=='enable':site.update(aggressive=True,aggressive_ttl=604800)
            else:site['cms_discovery']={'checked_utc':'new','status':'complete'}
            config={'origin_ip':'127.0.0.1','origin_port':8080}
            program=render(state,config)
            name='hvh_gen_'+hashlib.sha256(program.encode()).hexdigest()[:32]
            with tempfile.TemporaryDirectory() as directory:
                active=Path(directory)/'active.vcl';active.write_text(program)
                with patch.object(service,'ACTIVE',active),patch.object(service,'vcls',return_value=[{'name':name,'status':'active'}]), \
                     patch.object(service.routing,'apply',return_value=({},None)),patch.object(service.routing,'apache_config',return_value=''), \
                     patch.object(service,'purge') as purge,patch.object(service,'prune'):
                    result=service.apply(state,previous,{},config,changes=[])
                    self.assertEqual(result['invalidated_sites'],expected)
                    self.assertEqual(purge.call_count,expected)
                    if expected:purge.assert_called_once_with(config,site)


@unittest.skipUnless(shutil.which('varnishd'),'Native Varnish required')
class AggressiveNative(unittest.TestCase):
    def test_selected_lifetime_origin_headers_and_cookie_url_preserved(self):
        for profile in ('basic','ultracache'):
            with self.subTest(profile=profile):
                received=[]
                def origin(path,headers):
                    received.append((path,headers.get('Cookie')))
                    return '<html>public</html>',[('Cache-Control','private, no-store'),('Surrogate-Control','no-store'),
                        ('Pragma','no-cache'),('Expires','Thu, 01 Jan 1970 00:00:00 GMT'),('Vary','Cookie'),
                        ('Set-Cookie','PHPSESSID='+('A' if '/first' in path else 'B')+'; Path=/; HttpOnly')]
                with proxy(profile,origin,site_settings={'aggressive':True,'aggressive_ttl':604800}) as get:
                    _,fields,body=get('/first?utm_source=A','PHPSESSID=A; _ga=clientA')
                    self.assertEqual(dict(fields)['X-Hestia-Varnish'],'MISS')
                    self.assertIn(('Set-Cookie','PHPSESSID=A; Path=/; HttpOnly'),fields)
                    _,fields2,body2=get('/first?utm_source=B','PHPSESSID=B; _ga=clientB')
                    self.assertEqual(dict(fields2)['X-Hestia-Varnish'],'HIT')
                    self.assertEqual(body2,body)
                    self.assertFalse(any(k.lower()=='set-cookie' for k,v in fields2))
                    self.assertEqual(dict(fields2)['Cache-Control'],'private, no-store')
                    self.assertEqual(dict(fields2)['Surrogate-Control'],'no-store')
                    self.assertEqual(dict(fields2)['Pragma'],'no-cache')
                    self.assertEqual(received,[('/first?utm_source=A','PHPSESSID=A; _ga=clientA')])
                    _,fields3,_=get('/second','PHPSESSID=B')
                    self.assertIn(('Set-Cookie','PHPSESSID=B; Path=/; HttpOnly'),fields3)

    def test_actual_cms_aliases_and_actions_pass_while_public_html_hits(self):
        for profile in ('basic','ultracache'):
            with self.subTest(profile=profile):
                settings={'aggressive':True,'aggressive_ttl':604800,'cms_installations':[
                    {'cms':'wordpress','base':'/core','private_paths':['/checkout-2'],'private_queries':[{'name':'page_id','value':'73'}]},
                    {'cms':'joomla','base':'/joomla','private_paths':['/el/members-area']},
                    {'cms':'magento','base':'/shop','private_paths':['/shop/secret-admin']}],
                    'custom_private_paths':['/custom-private/']}
                def origin(path,headers):return '<html>origin</html>',[('Cache-Control','private, no-store')]
                with proxy(profile,origin,site_settings=settings) as get:
                    for path,reason in [('/checkout-2','wordpress-private-route'),('/?page_id=73','wordpress-private-route'),
                                        ('/el/members-area','joomla-private-route'),('/shop/secret-admin','magento-private-route'),
                                        ('/custom-private/test','custom-private-path')]:
                        _,fields,_=get(path)
                        self.assertEqual(dict(fields)['X-Hestia-Varnish'],'PASS')
                        self.assertEqual(dict(fields)['X-Hestia-Varnish-Reason'],reason)
                    self.assertEqual(dict(get('/public')[1])['X-Hestia-Varnish'],'MISS')
                    self.assertEqual(dict(get('/public')[1])['X-Hestia-Varnish'],'HIT')


if __name__=='__main__':unittest.main()
