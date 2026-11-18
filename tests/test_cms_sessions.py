"""Current database authentication beats a removable browser marker."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
import cms_sessions
import cms_session_server


class JoomlaSessions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'libraries/src').mkdir(parents=True)
        (self.root / 'libraries/src/Version.php').write_text("<?php const RELEASE = '3.10';")
        (self.root / 'configuration.php').write_text("""<?php class JConfig {
            public $secret='test-secret'; public $session_handler='database';
            public $host='localhost'; public $user='customer'; public $password='not-logged';
            public $db='cms'; public $dbprefix='j_'; }""")
        self.name = hashlib.md5(hashlib.md5(b'test-secretsite').hexdigest().encode()).hexdigest()

    def test_current_row_changes_guest_to_auth_without_marker(self):
        rows = [{'guest': 1, 'userid': 0}]
        calls = []
        def query(connection, session):
            calls.append(session)
            self.assertEqual(connection['prefix'], 'j_')
            return rows
        header = self.name + '=opaque123; _ga=personal'
        self.assertEqual(cms_sessions.classify(self.root, header, query), ('guest', 'joomla-guest-session'))
        rows[0] = {'guest': 0, 'userid': 42}
        self.assertEqual(cms_sessions.classify(self.root, header, query), ('private', 'joomla-authenticated-session'))
        self.assertEqual(calls, ['opaque123', 'opaque123'])

    def test_unrelated_hash_cookie_is_not_a_session(self):
        self.assertEqual(cms_sessions.classify(self.root, 'a'*32+'=tracking', self.fail), ('guest', 'joomla-no-session'))

    def test_missing_ambiguous_invalid_and_database_errors_are_unresolved(self):
        for header, query in [(self.name+'=abc', lambda *_: []),
                              (self.name+'=a; '+self.name+'=b', self.fail),
                              (self.name+'=bad/value', self.fail)]:
            self.assertEqual(cms_sessions.classify(self.root, header, query)[0], 'unresolved')
        def broken(*_):raise OSError('secret should never appear')
        result = cms_sessions.classify(self.root, self.name+'=abc', broken)
        self.assertEqual(result, ('unresolved', 'joomla-session-unavailable'))

    def test_logged_in_marker_and_positive_user_are_private(self):
        self.assertEqual(cms_sessions.classify(self.root, 'joomla_user_state=logged_in', self.fail)[0], 'private')
        self.assertEqual(cms_sessions.classify(self.root, self.name+'=abc', lambda *_:[{'guest':1,'userid':12}])[0], 'private')

    def test_unsupported_handler_or_version_is_not_guessed(self):
        path = self.root / 'configuration.php'
        path.write_text(path.read_text().replace("'database'", "'redis'"))
        self.assertEqual(cms_sessions.classify(self.root, '', self.fail)[0], 'unresolved')
        (self.root / 'libraries/src/Version.php').write_text('<?php const MAJOR_VERSION=5;')
        self.assertEqual(cms_sessions.classify(self.root, '', self.fail)[0], 'unresolved')

    def test_database_parameter_and_password_stay_out_of_argv(self):
        class Result:
            returncode = 0
            stdout = '{"guest":1,"userid":0}\n'
        with patch.object(cms_sessions.os, 'geteuid', return_value=1001), patch.object(cms_sessions.subprocess, 'run', return_value=Result()) as run:
            settings = {'prefix':'j_','host':'localhost','user':'customer','password':'privatepassword','database':'cms'}
            self.assertEqual(cms_sessions.mysql_session(settings, 'opaqueid'), [{'guest':1,'userid':0}])
            argv = run.call_args.args[0]
            self.assertNotIn('privatepassword', str(argv))
            self.assertNotIn('opaqueid', str(argv))
            sql = run.call_args.kwargs['input']
            self.assertIn('PREPARE cms_lookup FROM @cms_query', sql)
            self.assertIn('EXECUTE cms_lookup USING @cms_session', sql)
            self.assertNotIn('opaqueid', sql)

    def test_broker_identity_site_boundary_and_longest_base(self):
        nested = {'cms':'joomla','base':'/shop','root':'/safe/shop'}
        site = {'uid':1001,'gid':1001,'home':'/home/customer','installations':[
            {'cms':'joomla','base':'/','root':'/safe'}, nested]}
        self.assertEqual(cms_session_server.select_installation(site, '/shop/page?x=1'), nested)
        self.assertEqual(cms_session_server.select_installation(site, '/shopping')['root'], '/safe')
        self.assertEqual(cms_session_server.resolve({'sites':{}}, {'schema':1,'site':'a'*32,'path':'/','cookie':''}), 'unresolved\tcms-session-site\n')
        with patch.object(cms_session_server.pwd, 'getpwuid') as user, patch.object(cms_session_server.subprocess, 'run') as run:
            user.return_value.pw_gid=1001; user.return_value.pw_dir='/home/customer'
            run.return_value.returncode=0; run.return_value.stdout='guest\tjoomla-guest-session\n'
            answer = cms_session_server.resolve({'sites':{'a'*32:site}}, {'schema':1,'site':'a'*32,'path':'/shop','cookie':'personal=id'})
            self.assertEqual(answer, 'guest\tjoomla-guest-session\n')
            self.assertEqual(run.call_args.kwargs['user'], 1001)
            self.assertEqual(run.call_args.kwargs['group'], 1001)
            self.assertEqual(run.call_args.kwargs['extra_groups'], [])
            self.assertNotIn('personal=id', str(run.call_args.args))
            self.assertEqual(json.loads(run.call_args.kwargs['input'])['root'], '/safe/shop')


if __name__ == '__main__':
    unittest.main()
