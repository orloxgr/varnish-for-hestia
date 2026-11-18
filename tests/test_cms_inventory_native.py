"""Native Hestia CMS detection runs only during explicit control-plane refresh."""
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'shared'))
import cms_cookies

@unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid()==0 and shutil.which('mysql'),'Native Linux root MariaDB required')
class NativeCMSInventory(unittest.TestCase):
    def sql(self, text):
        return subprocess.run(['/usr/bin/mysql', '--no-defaults', '--batch', '--skip-column-names'],
                              input=text, text=True, capture_output=True, check=True).stdout

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cms-session-native-',dir='/var/lib')
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name); self.folder.chmod(0o755)
        shutil.copytree(ROOT / 'shared', self.folder / 'shared', ignore=shutil.ignore_patterns('__pycache__'))
        self.root = self.folder / 'customer'; (self.root / 'libraries/src').mkdir(parents=True)
        self.name = 'cms_test_' + uuid.uuid4().hex[:10]
        self.sql('CREATE DATABASE `'+self.name+'`; CREATE USER \''+self.name+"'@'localhost' IDENTIFIED BY 'fixturepassword'; " +
                 'GRANT SELECT ON `'+self.name+"`.* TO '"+self.name+"'@'localhost';")
        self.addCleanup(lambda:self.sql('DROP DATABASE IF EXISTS `'+self.name+'`; DROP USER IF EXISTS \''+self.name+"'@'localhost';"))
        (self.root / 'libraries/src/Version.php').write_text("<?php const RELEASE='3.10';")
        (self.root / 'configuration.php').write_text("<?php class JConfig { public $secret='secret'; public $session_handler='database'; public $host='localhost'; public $user='"+self.name+"'; public $password='fixturepassword'; public $db='"+self.name+"'; public $dbprefix='j_'; }")
        self.account = pwd.getpwnam('nobody')
        self.cookie=cms_cookies.joomla_name(self.root)+'=fixture'

    def test_native_docroot_discovery_and_actual_alias_query_run_as_customer(self):
        sys.path.insert(0,str(ROOT/'src'))
        import cms_inventory
        shutil.copytree(ROOT/'src',self.folder/'src',ignore=shutil.ignore_patterns('__pycache__'))
        self.sql('CREATE TABLE `'+self.name+'`.j_languages (lang_code VARCHAR(20),sef VARCHAR(10),published INT); '+
                 'CREATE TABLE `'+self.name+'`.j_menu (id INT,path VARCHAR(100),link VARCHAR(200),language VARCHAR(20),client_id INT,published INT,type VARCHAR(20)); '+
                 'INSERT INTO `'+self.name+"`.j_languages VALUES ('el-GR','el',1); "+
                 'INSERT INTO `'+self.name+"`.j_menu VALUES (333,'members-area','index.php?option=com_users&view=login','el-GR',0,1,'component');")
        state={'owners':{'nobody':{'identity':str(self.account.pw_uid)+':native-birth','sites':{
            'example.test':{'aliases':[]}}}},'hosting_timeouts':{'connect':10000}}
        inventory={'nobody':{'sites':{'example.test':{'document_root':str(self.root)}}}}
        with patch.object(cms_inventory,'WORKER',self.folder/'src/cms_inventory.py'):
            cms_inventory.refresh(state,inventory,lambda *_:self.fail('Native list root should be sufficient'),'all')
        site=state['owners']['nobody']['sites']['example.test']
        self.assertEqual(site['cms_discovery']['status'],'complete',site['cms_discovery'])
        self.assertEqual(site['cms_installations'][0]['private_paths'],['/el/members-area','/members-area'])
        self.assertEqual(site['cms_installations'][0]['private_queries'],[{'name':'Itemid','value':'333','base':'/'}])
        self.assertEqual(site['cms_cookies'][0]['cookie_name'],self.cookie.split('=')[0])
        # A later failed native root lookup keeps last valid aliases and says why.
        inventory['nobody']['sites']['example.test']['document_root']='/missing-native-root'
        with patch.object(cms_inventory,'WORKER',self.folder/'src/cms_inventory.py'):
            cms_inventory.refresh(state,inventory,lambda *_:self.fail('Unexpected CLI fallback'),'all')
        self.assertEqual(site['cms_discovery']['status'],'unavailable')
        self.assertIn('/el/members-area',site['cms_installations'][0]['private_paths'])

