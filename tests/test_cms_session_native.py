"""Disposable real MariaDB + UID drop + UNIX socket checks, no live sites."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))
import cms_session_server


@unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid() == 0 and shutil.which('mysql'), 'Native Linux/root MariaDB required')
class NativeSessionResolver(unittest.TestCase):
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
                 'CREATE TABLE `'+self.name+'`.j_session (session_id VARCHAR(128) PRIMARY KEY, guest INT, userid INT, client_id INT); '+
                 'GRANT SELECT ON `'+self.name+"`.* TO '"+self.name+"'@'localhost'; "+
                 'INSERT INTO `'+self.name+"`.j_session VALUES ('same-opaque-id',1,0,0);")
        self.addCleanup(lambda:self.sql('DROP DATABASE IF EXISTS `'+self.name+'`; DROP USER IF EXISTS \''+self.name+"'@'localhost';"))
        (self.root / 'libraries/src/Version.php').write_text("<?php const RELEASE='3.10';")
        (self.root / 'configuration.php').write_text("<?php class JConfig { public $secret='secret'; public $session_handler='database'; public $host='localhost'; public $user='"+self.name+"'; public $password='fixturepassword'; public $db='"+self.name+"'; public $dbprefix='j_'; }")
        self.account = pwd.getpwnam('nobody')
        self.config = {'schema':1, 'socket':str(self.folder/'resolver.sock'), 'allowed_uids':[self.account.pw_uid],
                       'query_timeout':10, 'max_frame_bytes':1000000,
                       'sites':{'a'*32:{'uid':self.account.pw_uid,'gid':self.account.pw_gid,'home':self.account.pw_dir,
                                'installations':[{'cms':'joomla','base':'/','root':str(self.root)}]}}}
        self.config_path = self.folder/'config.json'; self.config_path.write_text(json.dumps(self.config));self.config_path.chmod(0o600)
        self.process = subprocess.Popen([sys.executable, str(self.folder/'shared/cms_session_server.py'), '--config', str(self.config_path)],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def stop():
            self.process.terminate()
            self.process.communicate(timeout=10)
        self.addCleanup(stop)
        deadline=time.monotonic()+10
        while not (self.folder/'resolver.sock').exists():
            if self.process.poll() is not None:self.fail('Resolver failed to start')
            if time.monotonic()>deadline:self.fail('Resolver socket did not appear')
            time.sleep(.02)
        self.cookie=hashlib.md5(hashlib.md5(b'secretsite').hexdigest().encode()).hexdigest()+'=same-opaque-id'

    def call(self, cookie=None):
        request={'schema':1,'site':'a'*32,'path':'/public?utm_source=original','cookie':self.cookie if cookie is None else cookie}
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(10); connection.connect(self.config['socket'])
            connection.sendall((json.dumps(request)+'\n').encode())
            return connection.makefile('rb').readline().decode()

    def test_real_sql_guest_becomes_auth_on_same_cookie_without_state_marker(self):
        self.assertEqual(self.call(), 'guest\tjoomla-guest-session\n')
        self.sql('UPDATE `'+self.name+'`.j_session SET guest=0,userid=77;')
        self.assertEqual(self.call(), 'private\tjoomla-authenticated-session\n')

    def test_customer_database_root_cannot_inherit_broker_socket_auth(self):
        path=self.root/'configuration.php'
        path.write_text(path.read_text().replace("$user='"+self.name+"'", "$user='root'").replace("$password='fixturepassword'", "$password=''"))
        self.assertEqual(self.call(), 'unresolved\tjoomla-session-unavailable\n')

    def test_real_expired_session_does_not_force_anonymous_pass(self):
        self.sql('DELETE FROM `'+self.name+'`.j_session;')
        self.assertEqual(self.call(),'guest\tjoomla-expired-session\n')

    def test_configuration_permissions_and_unknown_scope_are_rejected(self):
        self.config_path.chmod(0o644)
        with self.assertRaises(ValueError):cms_session_server.configuration(self.config_path)
        self.config_path.chmod(0o600)
        self.assertEqual(self.call(self.cookie+'; '+self.cookie), 'unresolved\tjoomla-session-unavailable\n')

    @unittest.skipUnless(shutil.which('systemctl'), 'Native systemd required')
    def test_actual_systemd_sandbox_socket_permissions_and_idempotent_prepare(self):
        sys.path.insert(0,str(ROOT/'src'))
        import cms_resolver
        name='hvh-cms-test-'+uuid.uuid4().hex[:10]
        socket_path='/run/'+name+'/sessions.sock'
        owner={'enabled':True,'suspended':False,'sites':{'example.test':{
            'id':'a'*32,'enabled':True,'suspended':False,'aggressive':True,
            'cms_document_root':str(self.root),'cms_installations':[{'cms':'joomla','base':'/'}]}}}
        state={'owners':{'nobody':owner},'hosting_timeouts':{'connect':10000}}
        with patch.object(cms_resolver,'NAME',name),patch.object(cms_resolver,'UNIT',Path('/etc/systemd/system')/(name+'.service')), \
             patch.object(cms_resolver,'SOCKET',socket_path),patch.object(cms_resolver,'CODE',self.folder), \
             patch.object(cms_resolver,'configuration_path',return_value=self.config_path),patch.object(cms_resolver,'frame_bytes',return_value=1000000):
            before=cms_resolver.snapshot()
            try:
                cms_resolver.prepare(state,{})
                deadline=time.monotonic()+10
                while not Path(socket_path).exists():
                    if time.monotonic()>deadline:self.fail('Sandboxed session service socket did not appear')
                    time.sleep(.02)
                self.config['socket']=socket_path
                self.assertEqual(self.call(),'guest\tjoomla-guest-session\n')
                self.assertEqual(Path(socket_path).stat().st_mode & 0o777,0o660)
                first=cms_resolver.run('systemctl','show',name,'--property=MainPID','--value')
                cms_resolver.prepare(state,{})
                self.assertEqual(cms_resolver.run('systemctl','show',name,'--property=MainPID','--value'),first)
            finally:
                cms_resolver.restore(before)
            self.assertFalse(cms_resolver.UNIT.exists())

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
        self.assertEqual(site['cms_installations'][0]['private_queries'],[{'name':'Itemid','value':'333'}])
        self.assertEqual(site['cms_sessions'][0]['cookie_name'],self.cookie.split('=')[0])
        # A later failed native root lookup keeps last valid aliases and says why.
        inventory['nobody']['sites']['example.test']['document_root']='/missing-native-root'
        with patch.object(cms_inventory,'WORKER',self.folder/'src/cms_inventory.py'):
            cms_inventory.refresh(state,inventory,lambda *_:self.fail('Unexpected CLI fallback'),'all')
        self.assertEqual(site['cms_discovery']['status'],'unavailable')
        self.assertIn('/el/members-area',site['cms_installations'][0]['private_paths'])

    @unittest.skipUnless(shutil.which('varnishd'),'Native Varnish required')
    def test_warm_shared_object_cannot_hide_real_database_login_transition(self):
        sys.path.insert(0,str(ROOT/'src'))
        import cms_resolver
        from test_cookie_delivery import proxy
        cookie_name=self.cookie.split('=')[0]
        self.sql('INSERT INTO `'+self.name+"`.j_session VALUES ('bob-guest',1,0,0);")
        for profile in ('basic','ultracache'):
            self.sql('UPDATE `'+self.name+"`.j_session SET guest=1,userid=0 WHERE session_id='same-opaque-id';")
            authenticated=False
            def origin(path,headers):
                body='<html>private account</html>' if authenticated else '<html>public page</html>'
                fields=[('Cache-Control','private, no-store'),('Vary','Cookie')]
                if not headers.get('Cookie'):fields.append(('Set-Cookie',self.cookie+'; Path=/; HttpOnly'))
                return body,fields
            settings={'aggressive':True,'aggressive_ttl':86400,
                      'cms_installations':[{'cms':'joomla','base':'/'}],
                      'cms_sessions':[{'cms':'joomla','base':'/','cookie_name':cookie_name,'supported':True}]}
            with self.subTest(profile=profile),patch.object(cms_resolver,'SOCKET',self.config['socket']),proxy(profile,origin,site_settings=settings) as get:
                first=get('/page')
                self.assertEqual(dict(first[1])['X-Hestia-Varnish'],'MISS')
                self.assertIn(('Set-Cookie',self.cookie+'; Path=/; HttpOnly'),first[1])
                warm=get('/page',self.cookie)
                self.assertEqual(dict(warm[1])['X-Hestia-Varnish'],'HIT')
                self.assertFalse(any(k.lower()=='set-cookie' for k,v in warm[1]))
                self.sql('UPDATE `'+self.name+"`.j_session SET guest=0,userid=77 WHERE session_id='same-opaque-id';")
                authenticated=True
                private=get('/page',self.cookie)
                self.assertEqual(dict(private[1])['X-Hestia-Varnish'],'PASS')
                self.assertEqual(dict(private[1])['X-Hestia-Varnish-Reason'],'joomla-authenticated-session')
                self.assertEqual(private[2],'<html>private account</html>')
                bob=get('/page',cookie_name+'=bob-guest')
                self.assertEqual(dict(bob[1])['X-Hestia-Varnish'],'HIT')
                self.assertEqual(bob[2],'<html>public page</html>')
                self.assertFalse(any(k.lower()=='set-cookie' for k,v in bob[1]))


if __name__ == '__main__':unittest.main()
