"""Native build failure retains the existing library; code-only updates activate."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
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
