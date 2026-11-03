import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from cli import command, AuthenticationError


@unittest.skipUnless(shutil.which('varnishd') and os.name=='posix', 'Native isolated Varnish')
class NativeCLI(unittest.TestCase):
    def test_authenticated_protocol_supports_native_commands_without_subprocess_deadline(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);root.chmod(0o755)
            secret=root/'secret';secret.write_text('isolated-native-admin-proof\n')
            active=root/'active.vcl';active.write_text('vcl 4.1; backend default { .host="127.0.0.1"; .port="1"; }')
            with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
            with (root/'native.log').open('wb') as log:
                child=subprocess.Popen(['varnishd','-F','-j','none','-a','127.0.0.1:0','-T','127.0.0.1:'+str(port),'-n',str(root),'-S',str(secret),'-f',str(active),'-s','malloc,64m'],stdout=log,stderr=log)
                try:
                    deadline=time.monotonic()+15
                    while True:
                        try:result=command(port,secret,['status']);break
                        except OSError:
                            if child.poll() is not None or time.monotonic()>deadline:self.fail((root/'native.log').read_text())
                            time.sleep(.05)
                    self.assertEqual(result.returncode,0)
                    rows=json.loads(command(port,secret,['vcl.list','-j']).stdout)
                    self.assertTrue(any(isinstance(row,dict) and row.get('status')=='active' for row in rows))
                    result=command(port,secret,['ban','obj.http.X-HVH-Site','==','a'*32])
                    self.assertEqual(result.returncode,0)
                    wrong=root/'wrong';wrong.write_text('incorrect-native-proof-secret')
                    with self.assertRaises(AuthenticationError):command(port,wrong,['status'])
                finally:
                    child.terminate()
                    try:child.wait(timeout=15)
                    except subprocess.TimeoutExpired:child.kill();child.wait()
