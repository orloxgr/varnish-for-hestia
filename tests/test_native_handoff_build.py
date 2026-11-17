"""Native build failure retains the existing library; code-only updates activate."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import concurrent.futures
import re
import threading
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shared'))
import cookie_catalogue


class HandoffIdentity(unittest.TestCase):
    def test_native_source_only_change_changes_the_generated_vcl(self):
        catalogue=cookie_catalogue.load_catalogue()
        source=(ROOT/'shared/cache-policy.vcl').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copytree(ROOT/'shared/native',root/'native')
            shutil.copyfile(ROOT/'shared/native_build.py',root/'native_build.py')
            with patch.object(cookie_catalogue,'__file__',str(root/'cookie_catalogue.py')):
                before=cookie_catalogue.render_policy(source,catalogue)
                with (root/'native/cookie_handoff.c').open('a') as stream:stream.write('\n/* Code-only change */\n')
                after=cookie_catalogue.render_policy(source,catalogue)
            self.assertNotEqual(before,after)


@unittest.skipUnless(shutil.which('varnishd') and Path('/usr/include/varnish/vmod_abi.h').exists(),
                     'Native Varnish development package required')
class NativeHandoffBuild(unittest.TestCase):
    def test_c_only_update_loads_new_code_while_old_client_task_is_held(self):
        from test_cookie_delivery import proxy,cookies
        from test_profile_compatibility import program
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copytree(ROOT/'shared/native',root/'native')
            shutil.copyfile(ROOT/'shared/native_build.py',root/'native_build.py')
            output=root/'vmods';output.mkdir()
            spec=importlib.util.spec_from_file_location('owned_reload_native_build',root/'native_build.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            command=module.command;identities=[]
            def run(*args,cwd=None):
                if args[:2]==('pkg-config','--variable=vmoddir'):return str(output)
                result=command(*args,cwd=cwd)
                if args[0]=='python3':
                    generated=(Path(cwd)/'vcc_if.c').read_text()
                    identities.append(re.search(r'\.file_id\s*=\s*"([0-9a-f]+)"',generated).group(1))
                return result
            started=threading.Event();finish=threading.Event()
            def origin(path,headers):
                if path=='/held':
                    started.set();finish.wait(10)
                return 'public',[('Cache-Control','public, max-age=120'),('Set-Cookie','_fbp=original-'+path[1:]+'; Path=/')]
            with patch.object(module,'command',side_effect=run):
                library=module.build()
                def transform(source):
                    return source.replace('import cookie_handoff;','import cookie_handoff from "'+str(library)+'";').replace(
                        'call scp_deliver;','call scp_deliver; set resp.http.X-Test-Module = cookie_handoff.pending();')
                with proxy('basic',origin,transform=transform,management=True) as get:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as workers:
                        held=workers.submit(get,'/held')
                        try:
                            self.assertTrue(started.wait(5))
                            c=root/'native/cookie_handoff.c'
                            source=c.read_text();self.assertEqual(source.count('count = live;'),1)
                            c.write_text(source.replace('count = live;','count = live + 100;'))
                            self.assertEqual(module.build(),library)
                            self.assertNotEqual(identities[0],identities[1])
                            get.activate('updated',transform(program('basic')).replace('${s1_port}',str(get.origin_port)))
                            _,fields,_=get('/new')
                            self.assertEqual(dict(fields)['X-Test-Module'],'101')
                            self.assertEqual(cookies(fields),['_fbp=original-new; Path=/'])
                        finally:finish.set()
                        _,fields,_=held.result(timeout=10)
                        self.assertEqual(dict(fields)['X-Test-Module'],'1')
                        self.assertEqual(cookies(fields),['_fbp=original-held; Path=/'])
                    _,fields,_=get('/new')
                    self.assertEqual(dict(fields)['X-Test-Module'],'100')
                    self.assertEqual(cookies(fields),[])

    def test_repeated_build_reuses_library_and_failed_compile_keeps_it(self):
        from native_build import build
        library=build()
        receipt=library.with_name('cookie_handoff.build.json')
        before=(library.read_bytes(),receipt.read_bytes(),library.stat().st_mtime_ns)
        self.assertEqual(build(),library)
        self.assertEqual(library.stat().st_mtime_ns,before[2])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copytree(ROOT/'shared/native',root/'native')
            shutil.copyfile(ROOT/'shared/native_build.py',root/'native_build.py')
            with (root/'native/cookie_handoff.c').open('a') as stream:stream.write('\n#error Intentional failed candidate\n')
            spec=importlib.util.spec_from_file_location('owned_failed_native_build',root/'native_build.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with self.assertRaisesRegex(RuntimeError,'Native cookie module build failed'):
                module.build()
        self.assertEqual((library.read_bytes(),receipt.read_bytes(),library.stat().st_mtime_ns),before)


if __name__=='__main__':unittest.main()
