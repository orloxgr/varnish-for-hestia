"""Disposable real MariaDB + UID drop + UNIX socket checks, no live sites."""
import hashlib
import base64
import http.client
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

    def token_call(self,cookie='',host='example.test'):
        request={'schema':1,'op':'token','site':'a'*32,'path':'/el/page','cookie':cookie,
                 'host':host,'scheme':'https','user_agent':'Actual test browser','client_ip':'192.0.2.45'}
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(10);connection.connect(self.config['socket'])
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
        self.assertEqual(site['cms_installations'][0]['private_queries'],[{'name':'Itemid','value':'333','base':'/'}])
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

    def test_failed_policy_apply_removes_new_helper_and_restores_private_snapshot(self):
        sys.path.insert(0,str(ROOT/'src'))
        import cms_resolver
        import service
        folder=self.folder/'apply';folder.mkdir()
        config_dir=folder/'config';config_dir.mkdir()
        (config_dir/'active.vcl').write_text('previous runtime source')
        store=folder/'state';store.mkdir(mode=0o700)
        name='hvh-cms-rollback-'+uuid.uuid4().hex[:10]
        inventory={'nobody':{'identity':str(self.account.pw_uid)+':birth','package':'default','role':'user','suspended':False,
            'sites':{'example.test':{'aliases':[],'suspended':False,'origin_ip':'127.0.0.1','proxy_template':'default','proxy_extensions':'','document_root':str(self.root)}}}}
        def mutate(state,config):
            site=state['owners']['nobody']['sites']['example.test']
            site.update(aggressive=True,cms_document_root=str(self.root),cms_installations=[{'cms':'joomla','base':'/'}])
        def timeouts(state):state['hosting_timeouts']={'connect':10000,'read':10000,'send':10000}
        with patch.object(service,'CONFIG',config_dir),patch.object(service,'STORE',store),patch.object(service,'ACTIVE',config_dir/'active.vcl'), \
             patch.object(service,'collect',return_value=inventory),patch.object(service.hosting_timeouts,'refresh',side_effect=timeouts), \
             patch.object(service.routing,'plan',return_value=[]),patch.object(service,'apply',side_effect=service.ApplyRolledBack('compile rejected')), \
             patch.object(cms_resolver,'NAME',name),patch.object(cms_resolver,'UNIT',Path('/etc/systemd/system')/(name+'.service')), \
             patch.object(cms_resolver,'SOCKET','/run/'+name+'/sessions.sock'),patch.object(cms_resolver,'CODE',self.folder), \
             patch.object(cms_resolver,'frame_bytes',return_value=1000000):
            before=cms_resolver.snapshot()
            try:
                with self.assertRaises(service.ApplyRolledBack):
                    service.reconcile(None,mutate,config_override={'origin_ip':'127.0.0.1','origin_port':8080})
                self.assertFalse(cms_resolver.UNIT.exists())
                self.assertFalse(cms_resolver.configuration_path().exists())
                self.assertFalse((store/'apply.json').exists())
                self.assertEqual((config_dir/'active.vcl').read_text(),'previous runtime source')
            finally:cms_resolver.restore(before)

    @unittest.skipUnless(shutil.which('php8.3'),'Native PHP HTTP server required')
    def test_tokens_and_session_cookie_are_created_by_real_php_and_owned_by_each_client(self):
        web=self.folder/'component';web.mkdir()
        sessions=self.folder/'php-sessions';sessions.mkdir()
        os.chown(sessions,self.account.pw_uid,self.account.pw_gid);sessions.chmod(0o700)
        cookie_name=self.cookie.split('=')[0]
        code='''<?php
if ($_SERVER['HTTP_HOST'] === 'www.example.test') {
    header('Location: https://example.test'.$_SERVER['REQUEST_URI'], true, 301); exit;
}
ini_set('session.save_path', SESSION_FOLDER);
session_name(SESSION_COOKIE);
session_set_cookie_params(['path'=>'/', 'secure'=>true, 'httponly'=>true, 'samesite'=>'Lax']);
session_start();
if (!isset($_SESSION['token'])) $_SESSION['token']=bin2hex(random_bytes(16));
$db=new mysqli('localhost', DB_NAME, 'fixturepassword', DB_NAME);
$statement=$db->prepare('INSERT INTO j_session (session_id,guest,userid,client_id) VALUES (?,1,0,0) ON DUPLICATE KEY UPDATE guest=1,userid=0');
$id=session_id();$statement->bind_param('s',$id);$statement->execute();
$token=md5('secret'.'0'.$_SESSION['token']);
header('Content-Type: text/html; charset=UTF-8');
if (parse_url($_SERVER['REQUEST_URI'],PHP_URL_PATH)==='/page') {
    echo '<script type="application/json" class="joomla-script-options new">'.json_encode(['csrf.token'=>$token]).'</script><main>public page</main>';
} else {
    echo '<form method="post"><input type="hidden" name="'.$token.'" value="1"></form>';
}
session_write_close();
'''
        code=code.replace('SESSION_FOLDER',json.dumps(str(sessions))).replace('SESSION_COOKIE',json.dumps(cookie_name)).replace('DB_NAME',json.dumps(self.name))
        (web/'index.php').write_text(code)
        self.sql('GRANT INSERT,UPDATE ON `'+self.name+"`.* TO '"+self.name+"'@'localhost';")
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
        process=subprocess.Popen(['/usr/bin/php8.3','-S','127.0.0.1:'+str(port),'-t',str(web),str(web/'index.php')],
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,user=self.account.pw_uid,
                                 group=self.account.pw_gid,extra_groups=[],cwd='/',env={'PATH':'/usr/bin:/bin'})
        def stop():process.terminate();process.communicate(timeout=10)
        self.addCleanup(stop)
        deadline=time.monotonic()+10
        while True:
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.2):break
            except OSError:
                if time.monotonic()>deadline:self.fail('Fixture PHP component did not start')
                time.sleep(.02)
        site=self.config['sites']['a'*32]
        site.update(names=['example.test','www.example.test'],origins={
            'https':{'type':'tcp','address':'127.0.0.1','port':port}})
        self.config_path.write_text(json.dumps(self.config))
        first=self.token_call(host='www.example.test').rstrip('\n').split('\t')
        second=self.token_call().rstrip('\n').split('\t')
        self.assertEqual(first[0],'token');self.assertEqual(second[0],'token')
        self.assertRegex(first[1],r'^[a-f0-9]{32}$');self.assertNotEqual(first[1],second[1])
        cookie_a=base64.b64decode(first[2]).decode('latin-1').removeprefix('Set-Cookie: ')
        cookie_b=base64.b64decode(second[2]).decode('latin-1').removeprefix('Set-Cookie: ')
        self.assertIn('HttpOnly',cookie_a);self.assertIn('secure',cookie_a)
        header_a=cookie_a.split(';',1)[0];header_b=cookie_b.split(';',1)[0]
        self.assertNotEqual(header_a,header_b)
        returning=self.token_call(header_a).rstrip('\n').split('\t')
        self.assertEqual(returning,['token',first[1],''])
        self.assertEqual(self.call(header_a),'guest\tjoomla-guest-session\n')
        session_a=header_a.split('=',1)[1]
        self.assertRegex(session_a,r'^[A-Za-z0-9,-]+$')
        self.sql('UPDATE `'+self.name+"`.j_session SET guest=0,userid=77 WHERE session_id='"+session_a+"';")
        self.assertEqual(self.token_call(header_a),'private\tjoomla-authenticated-session\n')
        if shutil.which('varnishd'):
            import cms_resolver
            from test_cookie_delivery import proxy
            for profile in ('basic','ultracache'):
                full_requests=[]
                def origin(path,headers):
                    full_requests.append(path)
                    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=10)
                    try:
                        connection.request('GET',path,headers={'Host':'example.test','Cookie':headers.get('Cookie',''),
                            'User-Agent':headers.get('User-Agent',''),'X-Forwarded-Proto':'https'})
                        response=connection.getresponse();body=response.read().decode()
                        fields=[(name,value) for name,value in response.getheaders() if name.lower() not in ('content-length','connection','date','server','host')]
                        self.assertEqual(response.status,200)
                        return body,fields
                    finally:connection.close()
                settings={'aggressive':True,'cms_installations':[{'cms':'joomla','base':'/'}],
                          'cms_sessions':[{'cms':'joomla','base':'/','cookie_name':cookie_name,'supported':True}]}
                with self.subTest(profile=profile),patch.object(cms_resolver,'SOCKET',self.config['socket']),proxy(profile,origin,site_settings=settings) as get:
                    alpha=get('/page?utm_source=A',extra={'User-Agent':'Actual test browser','X-Real-IP':'192.0.2.45'})
                    beta=get('/page?utm_source=B',extra={'User-Agent':'Actual test browser','X-Real-IP':'192.0.2.46'})
                    self.assertEqual(dict(alpha[1])['X-Hestia-Varnish'],'MISS')
                    self.assertEqual(dict(beta[1])['X-Hestia-Varnish'],'HIT')
                    token_a=cms_session_server.cms_sessions.token_from_html(alpha[2])
                    token_b=cms_session_server.cms_sessions.token_from_html(beta[2])
                    self.assertNotEqual(token_a,token_b)
                    cookies_a=[value.split(';',1)[0] for name,value in alpha[1] if name.lower()=='set-cookie' and value.startswith(cookie_name+'=')]
                    cookies_b=[value.split(';',1)[0] for name,value in beta[1] if name.lower()=='set-cookie' and value.startswith(cookie_name+'=')]
                    self.assertTrue(cookies_a);self.assertTrue(cookies_b);self.assertNotEqual(cookies_a[-1],cookies_b[-1])
                    returning=get('/page?utm_source=C',cookies_a[-1],extra={'User-Agent':'Actual test browser','X-Real-IP':'192.0.2.45'})
                    self.assertEqual(dict(returning[1])['X-Hestia-Varnish'],'HIT')
                    self.assertEqual(cms_session_server.cms_sessions.token_from_html(returning[2]),token_a)
                    self.assertFalse(any(name.lower()=='set-cookie' for name,value in returning[1]))
                    self.assertEqual(full_requests,['/page?utm_source=A'])
                    self.assertEqual(alpha[2].replace(token_a,'SAME'),beta[2].replace(token_b,'SAME'))


if __name__ == '__main__':unittest.main()
