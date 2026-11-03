"""Real PHP/Python pipe transport: complete large requests, stdout and stderr."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which('php') and Path('/usr/bin/python3').exists(), 'Native Linux PHP and Python')
class BridgeTransport(unittest.TestCase):
    def test_large_payload_and_both_output_streams_complete_without_deadlock(self):
        repo=Path(__file__).resolve().parents[1]
        source=(repo/'panel/index.php').read_text()
        begin=source.index('$bridge = static function')
        end=source.index('\n};',begin)+3
        bridge=source[begin:end]
        bridge=re.sub(r'proc_open\(\[[^\n]+\],', "proc_open(['/usr/bin/python3', __DIR__ . '/child.py'],", bridge)
        invocation="$value=$bridge(['large'=>str_repeat('a',1100000)]);"
        if repo.name!='hestia-de-noise':invocation="[$code,$value]=$bridge(['large'=>str_repeat('a',1100000)]);"
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'child.py').write_text("import sys,json\nv=json.load(sys.stdin)\nsys.stderr.write('e'*2500000)\nprint(json.dumps(dict(ok=True,request_length=len(v['large']),large='x'*3100000)))\n")
            (root/'bridge.php').write_text("<?php $root='unused';$meta=[];\n"+bridge+'\n'+invocation+"echo json_encode([strlen($value['large']),$value['request_length']]);")
            value=subprocess.run(['php',str(root/'bridge.php')],capture_output=True,text=True,timeout=15)
        self.assertEqual(value.returncode,0,value.stderr)
        self.assertEqual(json.loads(value.stdout),[3100000,1100000])
