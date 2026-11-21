"""Every displayed default is executable, versioned and overrideable."""
import copy
import json
from pathlib import Path
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'shared'),str(ROOT/'src')]
import cookie_admin as admin
import cookie_control as control
import cookie_defaults as defaults
from cookie_catalogue import load_catalogue
from test_cookie_admin import settings


class CookieDefaults(unittest.TestCase):
    def test_all_source_records_have_concrete_active_decisions(self):
        policy,data=defaults.bundle()
        self.assertEqual(len(data['records']),2288)
        self.assertEqual({r['actions'][p] for r in policy['rules'] for p in ('basic','ultracache')},{'shared','variant','private'})
        active=admin.active()
        for row in data['records'].values():
            match=admin._recognition_match(row)
            winner=next(r for r in active if admin._matches(r['match'],match))
            # A broader reviewed rule can override a record, exactly as runtime.
            self.assertIn(winner['action'],('shared','variant','private'))
            self.assertTrue(defaults.valid_name(match['value']))
        database=json.loads((ROOT/'shared/cookie-recognition/recognition.json').read_text(encoding='utf-8'))
        rows=admin.table(database,load_catalogue())
        self.assertEqual(len(rows),2305)
        self.assertNotIn('automatic',{row['action'] for row in rows})
        self.assertTrue(all(row['scope']=='bundled' and row['default_version']==data['version'] for row in rows))

    def test_legacy_automatic_prefix_does_not_take_first_child_action(self):
        value=settings('brand_', 'automatic',kind='prefix')
        self.assertEqual(admin.concrete(value)['rules'][0]['actions']['basic'],'variant')
        self.assertEqual(value['rules'][0]['action'],'automatic')
        self.assertEqual(admin.concrete(settings('_ga','automatic'))['rules'][0]['actions']['basic'],'shared')
        self.assertEqual(admin.concrete(settings('wordpress_logged_in_','automatic',kind='prefix'))['rules'][0]['actions']['basic'],'private')

    def test_global_and_site_choices_override_defaults_in_wire_and_native(self):
        central=settings('_ga','private')
        site=settings('_ga','variant')
        snapshot=control.materialized_snapshot(central,site)
        self.assertEqual(control.snapshot(),{'schemaVersion':1,'central':{'schemaVersion':1,'rules':[]},'site':{'schemaVersion':1,'rules':[]}})
        self.assertEqual(admin.resolve(snapshot['central'],snapshot['site']),admin.active(central,site))
        winner=next(r for r in admin.active(central,site) if admin._matches(r['match'],{'kind':'exact','value':'_ga'}))
        self.assertEqual((winner['scope'],winner['action']),('site','variant'))
        self.assertEqual(set(snapshot),{'schemaVersion','central','site'})
        self.assertFalse(any(r['action']=='automatic' for scope in ('central','site') for r in snapshot[scope]['rules']))

    def test_literal_legacy_names_are_escaped_not_interpreted(self):
        for name in ('a0_users:sess','barometric[cuid]','crisp-client/','Site History','logglytracking\u00adsession','../literal'):
            with self.subTest(name=name):
                source=admin.compile_vcl(settings(name,'variant'))
                self.assertIn(admin._pattern({'kind':'exact','value':name}),source)
        for name in ('bad;pair','bad=name','bad"name','bad}name','bad\nname',' name','name\t'):
            with self.subTest(name=name),self.assertRaises(ValueError):admin.normalize(settings(name,'shared'))

    def test_duplicate_provider_names_have_one_editorial_decision(self):
        groups={}
        for row in defaults.bundle()[1]['records'].values():
            key=(row['name'],row['wildcard'])
            groups.setdefault(key,set()).add(tuple(row['actions'][p] for p in ('basic','ultracache')))
        self.assertTrue(all(len(actions)==1 for actions in groups.values()))

    def test_daily_recognition_cannot_hide_rules_or_claim_uncompiled_defaults(self):
        rows=admin.table({'records':[{'id':'new','name':'brand_new_cookie','provider':'New provider'}]},load_catalogue())
        bundled=[r for r in rows if r['id']!='ocd:new']
        self.assertEqual(len(bundled),2305)
        self.assertTrue(all(r['active_rule'] for r in bundled))
        new=next(r for r in rows if r['id']=='ocd:new')
        self.assertEqual((new['action'],new['scope'],new['effective_action']),('variant','recognition','existing-policy'))
        self.assertFalse(new['active_rule'])
        overridden=next(r for r in admin.table({'records':[{'id':'new','name':'brand_new_cookie'}]},load_catalogue(),
            site=settings('brand_new_cookie','variant',identity='ocd:new')) if r['id']=='ocd:new')
        self.assertEqual((overridden['scope'],overridden['effective_action']),('site','variant'))
        self.assertTrue(overridden['active_rule'])

    def test_generated_standalone_artifact_matches_native_defaults(self):
        artifact=json.loads((ROOT/'shared/cookie-defaults.json').read_text(encoding='utf-8'))
        self.assertEqual(admin.normalize({'schemaVersion':artifact['schemaVersion'],'rules':artifact['rules']}),admin.normalize(defaults.defaults()))
        self.assertEqual(artifact['version'],defaults.bundle()[1]['version'])

    def test_multi_site_native_vcl_does_not_repeat_the_entire_bundle(self):
        from vcl import render
        example=dict(id='a'*32,aliases=[],profile='basic',token='A'*32,enabled=True,suspended=False,custom_recv='',custom_backend_response='')
        owner=dict(enabled=True,suspended=False,package='default',sites={})
        state={'owners':{'fixture':owner}}
        for n in range(48):
            site=copy.deepcopy(example);site['id']=f'{n:032x}';site['aliases']=[]
            owner['sites'][f'site{n}.example']=site
        source=render(state,{'origin_ip':'127.0.0.1','origin_port':8080})
        self.assertEqual(source.count('set req.http.X-SCP-Admin-Remaining = req.http.Cookie;'),1)
        self.assertEqual(source.count('set req.http.X-HVH-Site = '),sum(len(o['sites']) for o in state['owners'].values()))
        for n,site in enumerate(owner['sites'].values()):
            site['cookie_policies']=settings('custom_'+str(n),'variant')
        different=render(state,{'origin_ip':'127.0.0.1','origin_port':8080})
        self.assertEqual(different.count('sub scp_bundled_cookie_rules {'),1)
        self.assertEqual(different.count('set req.http.X-SCP-Admin-Rule = "bundled:shared";'),source.count('set req.http.X-SCP-Admin-Rule = "bundled:shared";'))
        self.assertEqual(different.count('call scp_bundled_cookie_rules;'),48)


if __name__=='__main__':unittest.main()
