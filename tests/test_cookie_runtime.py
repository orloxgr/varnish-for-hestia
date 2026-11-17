"""Actual native boot/reload source, independently restored disk configuration."""
import hashlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

if sys.platform != 'linux':
    raise unittest.SkipTest('Native Linux Varnish lifecycle')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import service
from test_cookie_rules import fixture


def port():
    with socket.socket() as connection:
        connection.bind(('127.0.0.1',0))
        return connection.getsockname()[1]


@unittest.skipUnless(shutil.which('varnishd') and os.geteuid()==0, 'Native root Varnish required')
class CookieRuntime(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hvh-runtime-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.root.chmod(0o755)
        self.state, _ = fixture()
        self.config = {'origin_ip':'127.0.0.1','origin_port':8080,
                       'admin_port':port(),'listen_port':port()}
        self.program = service.render(self.state,self.config).encode()
        self.active = self.root/'active.vcl'
        (self.root/'generations').mkdir()
        (self.root/'admin.secret').write_text('native-test-key')

    def start(self, runtime):
        source = self.root/'boot.vcl'; source.write_bytes(runtime)
        log = (self.root/'native.log').open('wb')
        self.addCleanup(log.close)
        process = subprocess.Popen(['varnishd','-F','-n',str(self.root/'instance'),'-f',str(source),
            '-a','127.0.0.1:'+str(self.config['listen_port']),'-T','127.0.0.1:'+str(self.config['admin_port']),
            '-S',str(self.root/'admin.secret'),'-s','malloc,64m'],stdout=log,stderr=log)
        def stop():
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
        self.addCleanup(stop)
        for _ in range(100):
            if process.poll() is not None:
                self.fail('Native startup failed: '+(self.root/'native.log').read_text())
            try:
                service.admin(self.config,'status')
                return process
            except (OSError,RuntimeError,subprocess.SubprocessError):time.sleep(.05)
        self.fail('Native test startup did not expose its CLI')

    def apply(self):
        with patch.object(service.routing,'apply',return_value=({},None)), \
             patch.object(service.routing,'apache_config',return_value=''), \
             patch.object(service,'purge') as purge:
            result=service.apply(self.state,self.state,{},self.config,changes=[])
        purge.assert_not_called()
        return result

    def test_matching_boot_source_is_adopted_once_without_restart(self):
        with patch.object(service,'CONFIG',self.root),patch.object(service,'ACTIVE',self.active):
            process=self.start(self.program)
            self.active.write_bytes(b'outdated durable file')
            result=self.apply()
            self.assertTrue(result['vcl_activated'])
            before=service.vcls(self.config)
            self.assertFalse(self.apply()['vcl_activated'])
            self.assertEqual(service.vcls(self.config),before)
            self.assertEqual(self.active.read_bytes(),self.program)
            self.assertIsNone(process.poll())

    def test_restored_disk_does_not_hide_different_active_boot_or_reload_source(self):
        with patch.object(service,'CONFIG',self.root),patch.object(service,'ACTIVE',self.active):
            old=b'# Earlier actual runtime\n'+self.program
            process=self.start(old)
            self.active.write_bytes(self.program)
            result=self.apply()
            self.assertTrue(result['vcl_activated'])
            name=next(row['name'] for row in service.vcls(self.config) if row['status']=='active')
            self.assertEqual(service.admin(self.config,'vcl.show',name).stdout,self.program)
            # Repeat the same mismatch under the normal external reload prefix.
            runtime=self.root/'reload.vcl';runtime.write_bytes(old)
            service.admin(self.config,'vcl.load','hvh_reload_external_fixture',str(runtime))
            service.admin(self.config,'vcl.use','hvh_reload_external_fixture')
            self.assertTrue(self.apply()['vcl_activated'])
            self.assertEqual(self.active.read_bytes(),self.program)
            self.assertIsNone(process.poll())

    def test_large_active_policy_upgrades_without_a_cli_source_dump(self):
        with patch.object(service,'CONFIG',self.root),patch.object(service,'ACTIVE',self.active):
            # Native vcl.show truncates an otherwise valid large program. A
            # multi-site upgrade must not depend on dumping that whole source.
            old=(b'# Existing multi-site policy source '+b'x'*80+b'\n')*4096+self.program
            process=self.start(old)
            self.active.write_bytes(old)
            import cli
            statuses=[]
            read_response=cli.response
            def record_response(stream):
                status,body=read_response(stream)
                statuses.append(status)
                return status,body
            with patch.object(cli,'response',side_effect=record_response):
                shown=service.admin(self.config,'vcl.show','boot',required=False)
            self.assertNotEqual(shown.returncode,0)
            self.assertEqual(statuses[-1],201)  # Native CLIS_TRUNCATED.
            self.assertLess(len(shown.stdout),len(old))
            result=self.apply()
            self.assertTrue(result['vcl_activated'])
            self.assertEqual(self.active.read_bytes(),self.program)
            self.assertFalse(self.apply()['vcl_activated'])
            # Upgrades also encounter an older managed digest name, rather
            # than boot: neither path should retrieve the large source.
            old_name='hvh_gen_'+hashlib.sha256(old).hexdigest()[:32]+'_12345678'
            service.admin(self.config,'vcl.load',old_name,str(self.root/'boot.vcl'))
            service.admin(self.config,'vcl.use',old_name)
            with patch.object(service,'admin',wraps=service.admin) as native:
                self.assertTrue(self.apply()['vcl_activated'])
                self.assertFalse(any(call.args[1]=='vcl.show' for call in native.call_args_list))
            self.assertFalse(self.apply()['vcl_activated'])
            self.assertIsNone(process.poll())

    def test_failed_route_rollback_retains_native_recovery_phase(self):
        import copy
        changed=copy.deepcopy(self.state)
        site=next(site for owner in changed['owners'].values() for site in owner['sites'].values())
        site['cookie_policies']={'schemaVersion':1,'rules':[{'id':'custom:currency',
            'match':{'kind':'exact','value':'currency'},'description':'Currency','action':'variant'}]}
        phases=[]
        with patch.object(service,'CONFIG',self.root),patch.object(service,'ACTIVE',self.active):
            process=self.start(self.program)
            self.active.write_bytes(self.program)
            before=next(row['name'] for row in service.vcls(self.config) if row['status']=='active')
            with patch.object(service.routing,'apply',return_value=({},([],None))), \
                 patch.object(service.routing,'apache_config',return_value=''), \
                 patch.object(service.routing,'rollback',side_effect=RuntimeError('route restore failed')), \
                 patch.object(service,'purge',side_effect=RuntimeError('purge failed')):
                with self.assertRaisesRegex(RuntimeError,'route restore failed'):
                    service.apply(changed,self.state,{},self.config,changes=[],
                        journal=lambda **values:phases.append(values))
            self.assertEqual(phases,[{'local_started':True}])
            self.assertEqual(next(row['name'] for row in service.vcls(self.config) if row['status']=='active'),before)
            self.assertEqual(self.active.read_bytes(),self.program)
            self.assertIsNone(process.poll())

    def test_module_only_change_activates_and_published_program_boots_without_sources(self):
        import vcl_source
        source=self.root/'source-shared'
        shutil.copytree(ROOT/'shared',source,ignore=shutil.ignore_patterns('__pycache__'))
        coordinator=(source/'cache-policy.vcl').read_bytes()
        with patch.object(service,'CONFIG',self.root),patch.object(service,'ACTIVE',self.active), \
             patch.object(vcl_source,'__file__',str(source/'vcl_source.py')):
            process=self.start(self.program)
            self.active.write_bytes(self.program)
            module=source/'vcl/cookies.vcl'
            module.write_text(module.read_text(encoding='utf-8')+'\n# Native module-only revision\n',encoding='utf-8')
            self.assertEqual((source/'cache-policy.vcl').read_bytes(),coordinator)
            self.assertTrue(self.apply()['vcl_activated'])
            self.assertIsNone(process.poll())
            published=self.active.read_bytes()
            self.assertIn(b'# Native module-only revision',published)
            self.assertNotIn(b'include "',published)
            active=next(row['name'] for row in service.vcls(self.config) if row['status']=='active')
            generations=set((self.root/'generations').iterdir())
            module.write_text(module.read_text(encoding='utf-8')+'\ninvalid candidate syntax;\n',encoding='utf-8')
            with self.assertRaises(service.ApplyRolledBack):self.apply()
            self.assertEqual(next(row['name'] for row in service.vcls(self.config) if row['status']=='active'),active)
            self.assertEqual(self.active.read_bytes(),published)
            self.assertEqual(set((self.root/'generations').iterdir()),generations)
            shutil.rmtree(source)
            # Reboot/startup consumes the complete durable artifact, without
            # needing any files from the generating code checkout.
            process.terminate();process.wait(timeout=10)
            restarted=self.start(published)
            self.assertEqual(service.admin(self.config,'vcl.show','boot').stdout,published)
            self.assertIsNone(restarted.poll())
