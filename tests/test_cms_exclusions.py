"""Retired CMS trees are skipped before file reads and database connections."""
import copy
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'shared')]
import cache_behavior
import cms_discovery
import cms_inventory


class ExclusionSettings(unittest.TestCase):
    def test_literal_paths_normalize_and_invalid_input_cannot_change_saved_choices(self):
        site={}
        cache_behavior.change(site,{'cms_excluded_directories':'/retired//site/\n/retired/site\n/παλιό'})
        self.assertEqual(site['cms_excluded_directories'],['/%CF%80%CE%B1%CE%BB%CE%B9%CF%8C','/retired/site'])
        before=copy.deepcopy(site)
        for value in ('relative','/../outside','/x/%2e%2e/y','/bad?query','/bad\\path',False,[]):
            with self.subTest(value=value),self.assertRaises(cache_behavior.CachePolicyError):
                cache_behavior.change(site,{'cms_excluded_directories':value})
            self.assertEqual(site,before)
        cache_behavior.change(site,{'aggressive':True})
        self.assertEqual(site['cms_excluded_directories'],before['cms_excluded_directories'])
        cache_behavior.change(site,{'cms_excluded_directories':''})
        self.assertEqual(site['cms_excluded_directories'],[])

    def test_excluded_metadata_is_removed_even_if_worker_fails(self):
        keep={'cms':'wordpress','base':'/','private_paths':['/checkout'],'private_queries':[]}
        retired={'cms':'joomla','base':'/old/site','private_paths':['/old/site/members'],'private_queries':[]}
        site={'aliases':[],'cms_excluded_directories':['/old'],
              'cms_installations':[keep,retired],
              'cms_cookies':[{'cms':'joomla','base':'/old/site','cookie_name':'a'*32,'supported':True}]}
        state={'owners':{'alice':{'identity':'1001:test','sites':{'example.test':site}}}}
        inventory={'alice':{'sites':{'example.test':{'document_root':'/fixture/root'}}}}
        account=SimpleNamespace(pw_uid=1001,pw_gid=1001,pw_dir='/fixture')
        with patch.object(cms_inventory.pwd,'getpwnam',return_value=account), \
             patch.object(cms_inventory.subprocess,'run',return_value=SimpleNamespace(returncode=1)) as run:
            cms_inventory.refresh(state,inventory,None,'all')
        self.assertEqual(site['cms_installations'],[keep])
        self.assertEqual(site['cms_cookies'],[])
        self.assertEqual(site['cms_discovery']['status'],'unavailable')
        self.assertEqual(json.loads(run.call_args.kwargs['input'])['excluded_directories'],['/old'])


@unittest.skipUnless(sys.platform.startswith('linux'),'Linux no-follow file reader required')
class DiscoveryExclusions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.root.chmod(0o755)
        self.write('wp-settings.php','<?php')
        self.write('wp-includes/version.php','<?php')
        self.write('wp-config.php',"<?php define('DB_HOST','localhost'); define('DB_USER','active_fixture'); define('DB_PASSWORD','fixture'); define('DB_NAME','active_fixture'); $table_prefix='wp_';")
        for base in ('old/site','old/site/child','old/site2','παλιό'):
            self.write(base+'/configuration.php',"<?php class JConfig { public $host='localhost'; public $user='retired_fixture'; public $password='fixture'; public $db='retired_fixture'; public $dbprefix='j_'; }")
            self.write(base+'/libraries/src/Version.php','<?php')

    def write(self,name,text):
        file=self.root/name
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(text)

    def test_subtree_is_never_read_while_root_and_same_prefix_sibling_remain(self):
        read=cms_discovery.read_literal
        def guarded(root,relative):
            self.assertFalse(Path(root).is_relative_to(self.root/'old/site'))
            self.assertFalse(Path(root).is_relative_to(self.root/'παλιό'))
            return read(root,relative)
        with patch.object(cms_discovery,'read_literal',side_effect=guarded):
            records=cms_discovery.discover(str(self.root),['/old/site/','/παλιό'])
        self.assertEqual({(r['cms'],r['base']) for r in records},{('wordpress','/'),('joomla','/old/site2')})
        with patch.object(cms_discovery,'read_literal',side_effect=AssertionError('Excluded root read')):
            self.assertEqual(cms_discovery.discover(str(self.root),['/']),[])

    def test_active_wordpress_queries_continue_but_retired_joomla_never_connects(self):
        connections=[]
        def query(connection,sql,timeout):
            connections.append(connection['database'])
            self.assertEqual(connection['database'],'active_fixture')
            self.assertTrue(sql.startswith('SELECT '))
            return [{'name':'home','value':'https://example.test'}]
        with patch.object(cms_inventory,'query',side_effect=query):
            result=cms_inventory.discover({'root':str(self.root),'hosts':['example.test'],
                'excluded_directories':['/old','/παλιό']})
        self.assertEqual(connections,['active_fixture'])
        self.assertEqual([(r['cms'],r['base']) for r in result['installations']],[('wordpress','/')])
        self.assertEqual(result['notices'],[])
        self.assertEqual(result['cookies'],[])

    @unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid()==0,'Linux root needed to start fixture as hosting UID')
    def test_unprivileged_worker_skips_dead_credentials_without_database_access(self):
        account=pwd.getpwnam('nobody')
        payload={'root':str(self.root),'hosts':['example.test'],'excluded_directories':['/old','/παλιό']}
        # This subprocess exercises real no-follow file reads under a hosting
        # UID. Query output is a fixture; no database or installed addon changes.
        script="""import json,sys
sys.path.insert(0,sys.argv[1])
import cms_inventory
def query(connection,sql,timeout):
    assert connection['database']=='active_fixture', 'Retired database attempted'
    return [{'name':'home','value':'https://example.test'}]
cms_inventory.query=query
print(json.dumps(cms_inventory.discover(json.load(sys.stdin))))
"""
        result=subprocess.run([sys.executable,'-I','-B','-c',script,str(ROOT/'src')],
            input=json.dumps(payload),text=True,capture_output=True,cwd='/',
            user=account.pw_uid,group=account.pw_gid,extra_groups=[],check=True)
        self.assertEqual(json.loads(result.stdout)['installations'][0]['cms'],'wordpress')
        self.assertEqual(len(json.loads(result.stdout)['installations']),1)


if __name__=='__main__':unittest.main()
