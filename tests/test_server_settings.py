"""Global timeout validation, lifecycle persistence and native Varnish behavior."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import server_settings
import service
import administration
from registry import desired_state
from vcl import render


def fixture():
    inventory = {'alice': dict(identity='one',package='default',role='user',suspended=False,
                               sites={'example.test':dict(aliases=[],suspended=False)})}
    return desired_state(None,inventory,'varnish'),inventory


class ServerSettings(unittest.TestCase):
    def test_global_timeout_is_validated_and_rendered_on_every_origin(self):
        state,_=fixture()
        self.assertNotIn('.first_byte_timeout',render(state,{'origin_ip':'127.0.0.1'}))
        server_settings.change(state,{'first_byte_timeout_seconds':300})
        site=copy.deepcopy(state['owners']['alice']['sites']['example.test'])
        site.update(id='a'*32,origin_ip='127.0.0.2')
        state['owners']['alice']['sites']['second.test']=site
        text=render(state,{'origin_ip':'127.0.0.1'})
        self.assertEqual(text.count('.first_byte_timeout = 300s;'),2)
        for value in [True,0,-1,3601,'300',1.5,'300; return (pass);']:
            with self.assertRaises(ValueError):server_settings.change(state,{'first_byte_timeout_seconds':value})

    def test_lifecycle_keeps_choice_and_change_preserves_all_site_settings(self):
        state,inventory=fixture();before=copy.deepcopy(state['owners'])
        server_settings.change(state,{'first_byte_timeout_seconds':300})
        self.assertEqual(state['owners'],before)
        inventory['alice']['sites']['new.test']=dict(aliases=[],suspended=False)
        after=desired_state(state,inventory,'varnish')
        self.assertEqual(after['server_settings'],state['server_settings'])

    def test_server_choice_commits_through_existing_journal(self):
        state,inventory=fixture()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);active=root/'active.vcl';active.write_text('old')
            (root/'desired.json').write_text(json.dumps(state))
            (root/'applied.json').write_text(json.dumps(state))
            with patch.object(service,'STORE',root),patch.object(service,'ACTIVE',active), \
                 patch.object(service,'recover_pending'),patch.object(service,'settings',return_value={'origin_ip':'127.0.0.1'}), \
                 patch.object(service,'collect',return_value=inventory),patch.object(service.routing,'plan',return_value=[]), \
                 patch.object(service.routing,'APACHE',root/'apache.inc'),patch.object(service,'apply',return_value={}) as apply:
                service.reconcile(None,lambda state,config:server_settings.change(state,{'first_byte_timeout_seconds':300}))
                self.assertEqual(json.loads((root/'applied.json').read_text())['server_settings']['first_byte_timeout_seconds'],300)
                self.assertFalse((root/'apply.json').exists())
                before=(root/'desired.json').read_bytes()
                apply.side_effect=service.ApplyRolledBack('Rejected')
                with self.assertRaises(service.ApplyRolledBack):
                    service.reconcile(None,lambda state,config:server_settings.change(state,{'first_byte_timeout_seconds':600}))
                self.assertEqual((root/'desired.json').read_bytes(),before)

    def test_memory_snapshot_is_one_native_command_and_has_no_request_data(self):
        raw=json.dumps({'counters':{'SMA.s0.g_bytes':{'value':2048},'SMA.s0.g_space':{'value':4096},
                                    'SMA.Transient.g_bytes':{'value':999}}})
        with patch.object(server_settings.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=raw)) as run:
            self.assertEqual(server_settings.memory({'memory_mb':8192}),dict(used_bytes=2048,free_bytes=4096,budget_mb=8192))
            run.assert_called_once_with(['varnishstat','-1','-j'],capture_output=True,text=True,timeout=5)

    def test_memory_action_does_not_reconcile_or_apply_policy(self):
        state,_=fixture()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'applied.json').write_text(json.dumps(state))
            with patch.object(service,'STORE',root),patch.object(service,'settings',return_value={'memory_mb':8192}), \
                 patch.object(service,'reconcile') as reconcile,patch.object(service,'admin',return_value=SimpleNamespace(stdout=b'Value is: 60.000 [seconds]')), \
                 patch.object(server_settings,'memory',return_value={'used_bytes':1,'free_bytes':2}):
                result=administration.request(None,'admin-memory',{},'varnish')
                self.assertIn('memory',result);reconcile.assert_not_called()

    @unittest.skipUnless(shutil.which('varnishtest'),'Native Varnish required')
    def test_backend_override_allows_slow_post_despite_lower_service_default(self):
        state,_=fixture();server_settings.change(state,{'first_byte_timeout_seconds':1})
        vcl=render(state,{'origin_ip':'127.0.0.1','origin_port':8080}).replace('"8080"','"${s1_port}"',1)
        script='''varnishtest "Configured first-byte timeout applies to bypass POSTs"
server s1 { rxreq
 expect req.method == "POST"
 delay 0.3
 txresp -body {ok}
} -start
varnish v1 -arg "-p first_byte_timeout=0.1" -vcl {
'''+vcl+'''
} -start
client c1 { txreq -req POST -url /wp-json/example/action -hdr "Host: example.test"
 rxresp
 expect resp.status == 200
 expect resp.body == "ok"
 expect resp.http.X-Hestia-Varnish == "BYPASS"
} -run
server s1 -wait
'''
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'timeout.vtc';path.write_text(script)
            result=subprocess.run(['varnishtest','-t','10',str(path)],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
