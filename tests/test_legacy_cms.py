"""Owned helper retirement, native systemd removal and failed-apply recovery."""
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import legacy_cms
import service
from test_cookie_rules import fixture


class ApplyLifecycle(unittest.TestCase):
    def test_retirement_follows_activation_and_failed_apply_retains_previous_helper(self):
        for fail in (False,True):
            state,inventory=fixture();events=[]
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'desired.json').write_text(json.dumps(state));(root/'applied.json').write_text(json.dumps(state))
                (root/'active.vcl').write_text('previous')
                before={'configuration':None,'unit':None,'running':False}
                def apply(*args,**kwargs):
                    events.append('activate')
                    if fail:raise service.ApplyRolledBack('native compile rejected')
                    return {'generation':'new'}
                with patch.object(service,'STORE',root),patch.object(service,'ACTIVE',root/'active.vcl'), \
                     patch.object(service,'collect',return_value=inventory),patch.object(service.hosting_timeouts,'refresh'), \
                     patch.object(service.routing,'APACHE',root/'apache.conf'),patch.object(service.routing,'plan',return_value=[]), \
                     patch.object(service,'apply',side_effect=apply),patch.object(legacy_cms,'snapshot',return_value=before), \
                     patch.object(legacy_cms,'retire',side_effect=lambda:events.append('retire')) as retire, \
                     patch.object(legacy_cms,'restore') as restore:
                    if fail:
                        with self.assertRaises(service.ApplyRolledBack):service.reconcile(None,config_override={'origin_ip':'127.0.0.1','origin_port':8080})
                        retire.assert_not_called();restore.assert_called_once_with(before)
                        self.assertEqual(events,['activate'])
                    else:
                        service.reconcile(None,config_override={'origin_ip':'127.0.0.1','origin_port':8080})
                        self.assertEqual(events,['activate','retire'])
                    self.assertFalse((root/'apply.json').exists())


@unittest.skipUnless(sys.platform.startswith('linux') and os.geteuid()==0 and shutil.which('systemctl'),'Native root systemd required')
class NativeRetirement(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='hvh-legacy-retirement-',dir='/var/lib')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o755)
        self.name='hvh-retire-test-'+uuid.uuid4().hex[:10]
        self.unit=Path('/etc/systemd/system')/(self.name+'.service')
        self.config=self.root/'config.json';self.sock=Path('/run')/self.name/'sessions.sock'
        self.code=self.root/'old-code';(self.code/'shared').mkdir(parents=True)
        # A disposable legacy process proves resource lifecycle, not caching.
        (self.code/'shared/cms_session_server.py').write_text('''import argparse,json,os,socket
p=argparse.ArgumentParser();p.add_argument('--config');a=p.parse_args()
path=json.load(open(a.config))['socket'];s=socket.socket(socket.AF_UNIX);s.bind(path);os.chmod(path,0o660);s.listen()
while True:
 c,_=s.accept();c.close()
''')
        self.stack=__import__('contextlib').ExitStack();self.addCleanup(self.stack.close)
        for name,value in [('NAME',self.name),('UNIT',self.unit),('CODE',self.code),('SOCKET',self.sock)]:
            self.stack.enter_context(patch.object(legacy_cms,name,value))
        self.stack.enter_context(patch.object(legacy_cms,'configuration_path',return_value=self.config))
        self.addCleanup(legacy_cms.retire)

    def start_old(self):
        self.config.write_text(json.dumps({'socket':str(self.sock)}));self.config.chmod(0o600)
        self.unit.write_text(legacy_cms.unit());self.unit.chmod(0o644)
        legacy_cms.run('systemctl','daemon-reload');legacy_cms.run('systemctl','enable','--now',self.name)
        self.ready()

    def ready(self):
        deadline=time.monotonic()+10
        while True:
            try:
                with socket.socket(socket.AF_UNIX) as client:client.connect(str(self.sock))
                return
            except OSError:
                if time.monotonic()>deadline:self.fail('Disposable legacy service did not start')
                time.sleep(.02)

    def test_old_native_service_removed_and_rollback_restores_it(self):
        self.start_old();before=legacy_cms.snapshot();self.assertTrue(before['running'])
        legacy_cms.retire()
        for path in (self.unit,self.config,self.sock,self.sock.parent):self.assertFalse(path.exists())
        self.assertNotEqual(legacy_cms.run('systemctl','show',self.name,'--property=ActiveState','--value'),'active')
        legacy_cms.restore(before);self.ready()
        self.assertTrue(legacy_cms.snapshot()['running'])
        self.assertEqual(self.config.read_text().strip(),json.dumps(before['configuration'],sort_keys=True,indent=2))
        legacy_cms.retire();legacy_cms.retire()

    def test_unrelated_unit_is_never_removed(self):
        self.unit.write_text('independent service\n')
        try:
            with self.assertRaises(ValueError):legacy_cms.retire()
            self.assertEqual(self.unit.read_text(),'independent service\n')
        finally:self.unit.unlink()

    def test_failed_upgrade_restores_previous_code_before_starting_legacy_service(self):
        self.start_old();before=legacy_cms.snapshot();legacy_cms.retire()
        old=self.code/'shared/cms_session_server.py';saved=old.read_bytes();old.unlink()
        import deployment
        with patch.object(deployment,'rollback',side_effect=lambda:old.write_bytes(saved)) as rollback:
            legacy_cms.restore(before);self.ready();rollback.assert_called_once_with()
        self.assertTrue(legacy_cms.snapshot()['running'])


if __name__=='__main__':unittest.main()
