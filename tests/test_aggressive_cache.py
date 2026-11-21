"""Native Hestia public caching, selected TTL and unchanged origin/browser data."""
import copy
import hashlib
import json
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

    def test_equivalent_native_docroot_spellings_never_trigger_recurring_scan(self):
        site={'cms_document_root':'/home/alice/web/example.test/public_html',
              'cms_pending_root':'/home/alice/web/example.test/public_html/'}
        state={'owners':{'alice':{'sites':{'example.test':site}}}}
        inventory={'alice':{'sites':{'example.test':{'document_root':'/home/alice//web/example.test/./public_html/'}}}}
        for _ in range(3):
            self.assertEqual(cms_inventory.changed_roots(state,inventory),set())
            self.assertNotIn('cms_pending_root',site)
        inventory['alice']['sites']['example.test']['document_root']='/new/root/'
        self.assertEqual(cms_inventory.changed_roots(state,inventory),{('alice','example.test')})
        site['cms_document_root']='/new/root'
        site.pop('cms_pending_root')
        self.assertEqual(cms_inventory.changed_roots(state,inventory),set())

    def test_repeated_reconcile_never_invokes_worker_for_unchanged_roots(self):
        state,inventory=fixture()
        for owner,row in state['owners'].items():
            for domain,site in row['sites'].items():
                root='/fixture/'+owner+'/'+domain
                site['cms_document_root']=root
                inventory[owner]['sites'][domain]['document_root']=root+'/'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'desired.json').write_text(json.dumps(state))
            (root/'applied.json').write_text(json.dumps(state))
            with patch.object(service,'STORE',root),patch.object(service,'ACTIVE',root/'active.vcl'), \
                 patch.object(service,'recover_pending'),patch.object(service,'collect',return_value=inventory), \
                 patch.object(service.hosting_timeouts,'refresh'),patch.object(service.routing,'APACHE',root/'apache.conf'), \
                 patch.object(service.routing,'plan',return_value=[]),patch.object(service,'apply',return_value={}), \
                 patch.object(service.legacy_cms,'snapshot',return_value={}),patch.object(service.legacy_cms,'retire'), \
                 patch.object(cms_inventory,'refresh') as refresh:
                for _ in range(3):
                    service.reconcile(None,config_override={'origin_ip':'127.0.0.1','origin_port':8080})
                refresh.assert_not_called()

    def test_site_action_checks_ownership_and_refreshes_only_selected_native_site(self):
        state,_=fixture(); scopes=[]
        def reconcile(hestia,mutation=None,**kwargs):
            if mutation:mutation(state,{})
            scopes.append(kwargs.get('cms_scope'))
            return state,{},{}
        with patch.object(service,'reconcile',side_effect=reconcile):
            result=service.request(None,'user000','configure-cache-policy',{
                'domain':'s0.user000.test','aggressive':True,'aggressive_ttl':604800,'custom_private_paths':'/members/',
                'cms_excluded_directories':'/retired/site/'})
            self.assertEqual(scopes,[{('user000','s0.user000.test')}])
            self.assertTrue(result['sites'][0]['aggressive'])
            self.assertEqual(result['sites'][0]['aggressive_ttl'],604800)
            self.assertEqual(result['sites'][0]['cms_excluded_directories'],['/retired/site'])
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
    def test_public_hit_with_origin_stopped_and_original_joomla_html_unchanged(self):
        page='<script type="application/json" class="joomla-script-options">{"csrf.token":"0123456789abcdef0123456789abcdef"}</script><form><input type="hidden" name="0123456789abcdef0123456789abcdef" value="1"></form><main>original</main>'
        for profile in ('basic','ultracache'):
            calls=[]
            def origin(path,headers):
                calls.append((path,headers.get('Cookie')))
                return page,[('Cache-Control','private, no-store'),('Set-Cookie','PHPSESSID=origin-A; Path=/; HttpOnly')]
            settings={'aggressive':True,'cms_installations':[{'cms':'joomla','base':'/'}],
                      'cms_cookies':[{'cms':'joomla','base':'/','cookie_name':'a'*32,'supported':True}],
                      'cookie_policies':{'schemaVersion':1,'rules':[
                          dict(id='custom:'+name,match=dict(kind='exact',value=name),description='Explicit Shared choice',action='shared')
                          for name in ('PHPSESSID','a'*32)]}}
            def no_runtime(source):
                for marker in ('X-SCP-Session','ensure_token','joomla-token','session_state','token_fragment'):
                    self.assertNotIn(marker,source)
                return source
            with self.subTest(profile=profile),proxy(profile,origin,site_settings=settings,transform=no_runtime) as get:
                first=get('/article?utm_source=A','a'*32+'=opaque-A; PHPSESSID=A')
                self.assertEqual(dict(first[1])['X-Cache'],'MISS');self.assertEqual(first[2],page)
                get.stop_origin()
                for visitor in ('B','C'):
                    result=get('/article?utm_source='+visitor,'a'*32+'=opaque-'+visitor+'; PHPSESSID='+visitor)
                    self.assertEqual(result[0],200);self.assertEqual(dict(result[1])['X-Cache'],'HIT')
                    self.assertEqual(result[2],page)
                    self.assertFalse(any(k.lower()=='set-cookie' for k,v in result[1]))
                    self.assertEqual(dict(result[1])['Cache-Control'],'private, no-store')
                self.assertEqual(calls,[('/article?utm_source=A','a'*32+'=opaque-A; PHPSESSID=A')])

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
