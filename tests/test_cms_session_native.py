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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared'))
import cms_session_server


@unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid() == 0 and shutil.which('mysql'), 'Native Linux/root MariaDB required')
class NativeSessionResolver(unittest.TestCase):
    def sql(self, text):
        return subprocess.run(['/usr/bin/mysql', '--no-defaults', '--batch', '--skip-column-names'],
                              input=text, text=True, capture_output=True, check=True).stdout

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cms-session-native-')
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

    def test_configuration_permissions_and_unknown_scope_are_rejected(self):
        self.config_path.chmod(0o644)
        with self.assertRaises(ValueError):cms_session_server.configuration(self.config_path)
        self.config_path.chmod(0o600)
        self.assertEqual(self.call(self.cookie+'; '+self.cookie), 'unresolved\tjoomla-session-unavailable\n')


if __name__ == '__main__':unittest.main()
