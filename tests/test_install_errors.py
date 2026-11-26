"""Installer diagnostics, without installing packages or modifying Hestia."""
import ast
import contextlib
import io
from pathlib import Path
import shlex
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import deployment
import progress


def installer_runner():
    # Load only the runner: importing the Linux installer initializes service
    # modules and requires native platform dependencies even on a test host.
    source = ROOT / 'tools/install.py'
    tree = ast.parse(source.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
    namespace = {'subprocess': subprocess, 'sys': sys, 'shlex': shlex, 'progress': progress}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['run']


def installer_function(name, namespace):
    source = ROOT / 'tools/install.py'
    tree = ast.parse(source.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace[name]


class InstallerErrors(unittest.TestCase):
    def test_handoff_reuses_matching_development_package_without_apt(self):
        native=Mock(build=Mock())
        process=Mock()
        process.run.side_effect=lambda args, **kwargs: Mock(returncode=0,
            stdout='9.1.0-2 installed' if args[-1]=='varnish-dev' else 'installed')
        namespace=dict(native_version=Mock(return_value='9.1.0-2'),subprocess=process,
                       run=Mock(),progress=Mock())
        with patch.dict(sys.modules,{'native_build':native}):
            installer_function('ensure_cookie_handoff',namespace)()
        namespace['run'].assert_not_called()
        native.build.assert_called_once_with()

    def test_handoff_installs_missing_zlib_with_matching_headers_without_restarting(self):
        native=Mock(build=Mock())
        process=Mock()
        process.run.side_effect=lambda args, **kwargs: Mock(returncode=0,
            stdout='9.1.0-2 installed' if args[-1]=='varnish-dev' else '')
        run=Mock(return_value=Mock(stdout=b'Inst zlib1g-dev (1.3.1 distro [amd64])'))
        namespace=dict(native_version=Mock(return_value='9.1.0-2'),subprocess=process,
                       run=run,progress=Mock(),os=Mock(environ={}),re=__import__('re'))
        with patch.dict(sys.modules,{'native_build':native}):
            installer_function('ensure_cookie_handoff',namespace)()
        self.assertEqual(run.call_args.args,('apt-get','install','-y','--no-remove',
                         'varnish=9.1.0-2','zlib1g-dev','zlib1g'))
        self.assertEqual(run.call_args.kwargs['env']['NEEDRESTART_MODE'],'l')
        native.build.assert_called_once_with()
        self.assertFalse(any('systemctl' in call.args for call in run.call_args_list))

    def test_handoff_dependency_transaction_cannot_upgrade_the_engine(self):
        process=Mock()
        process.run.return_value=Mock(returncode=1,stdout='')
        run=Mock(return_value=Mock(stdout=b'Inst varnish (9.2.0 official [amd64])'))
        namespace=dict(native_version=Mock(return_value='9.1.0-2'),subprocess=process,
                       run=run,progress=Mock(),os=Mock(environ={}),re=__import__('re'))
        with self.assertRaisesRegex(ValueError,'matching the existing'):
            installer_function('ensure_cookie_handoff',namespace)()
        self.assertEqual(run.call_count,1)
        self.assertIn('varnish=9.1.0-2',run.call_args.args)
        self.assertIn('varnish-dev=9.1.0-2',run.call_args.args)

    def test_handoff_zlib_preview_cannot_remove_another_service(self):
        native=Mock(build=Mock())
        process=Mock()
        process.run.side_effect=lambda args, **kwargs: Mock(returncode=0,
            stdout='9.1.0-2 installed' if args[-1]=='varnish-dev' else '')
        run=Mock(return_value=Mock(stdout=b'Remv apache2 [1.0]'))
        namespace=dict(native_version=Mock(return_value='9.1.0-2'),subprocess=process,
                       run=run,progress=Mock(),os=Mock(environ={}),re=__import__('re'))
        with patch.dict(sys.modules,{'native_build':native}):
            with self.assertRaisesRegex(ValueError,'matching the existing'):
                installer_function('ensure_cookie_handoff',namespace)()
        self.assertEqual(run.call_count,1)
        native.build.assert_not_called()

    def test_fresh_install_uses_signed_apt_candidate_without_a_version_pin(self):
        run = Mock(return_value=subprocess.CompletedProcess([], 0, b'Inst varnish (9.2.0 official [amd64])', b''))
        path = Mock(return_value=Mock(read_text=Mock(return_value='ID=ubuntu\nVERSION_CODENAME=resolute\n')))
        repository = Mock()
        namespace = dict(Path=path, run=run, repository=repository, os=Mock(environ={}), subprocess=Mock())
        namespace['subprocess'].run.return_value = subprocess.CompletedProcess([], 1, b'', b'')
        installer_function('install_package', namespace)()
        repository.setup.assert_called_once_with()
        self.assertEqual(run.call_args_list[1].args, ('apt-get', '-s', 'install', 'varnish', 'varnish-modules'))
        self.assertEqual(run.call_args_list[2].args, ('apt-get', 'install', '-y', 'varnish', 'varnish-modules'))
        self.assertEqual(len(run.call_args_list), 3)
        namespace['subprocess'].run.assert_not_called()

    def test_fresh_install_keeps_distro_boundary_and_refuses_removing_other_services(self):
        path = Mock(return_value=Mock(read_text=Mock(return_value='VERSION_CODENAME=other\n')))
        run, repository = Mock(), Mock()
        namespace = dict(Path=path, run=run, repository=repository, os=Mock(environ={}), subprocess=Mock())
        install = installer_function('install_package', namespace)
        with self.assertRaisesRegex(ValueError, 'matching Ubuntu resolute'):
            install()
        run.assert_not_called()
        repository.setup.assert_not_called()
        path.return_value.read_text.return_value = 'VERSION_CODENAME=resolute\n'
        run.return_value = subprocess.CompletedProcess([], 0, b'Remv apache2 [1.0]\n', b'')
        with self.assertRaisesRegex(ValueError, 'remove another service'):
            install()
        self.assertEqual(len(run.call_args_list), 2)

    def test_existing_native_modules_need_no_apt_or_repository_changes(self):
        namespace = dict(cookie_modules_available=Mock(return_value=True), repository=Mock(),
                         run=Mock(), progress=Mock())
        installer_function('ensure_cookie_modules', namespace)()
        namespace['repository'].setup.assert_not_called()
        namespace['run'].assert_not_called()

    def test_module_install_keeps_the_running_engine_and_does_not_restart_services(self):
        run = Mock(return_value=subprocess.CompletedProcess([], 0, b'Inst varnish-modules (9.1.0 official [amd64])\n', b''))
        namespace = dict(cookie_modules_available=Mock(side_effect=[False, True]), repository=Mock(),
                         run=run, progress=Mock(), os=Mock(environ={}), re=__import__('re'),
                         cookie_module_package=Mock(return_value='varnish-modules'),
                         native_version=Mock(return_value='9.1.0-official'))
        installer_function('ensure_cookie_modules', namespace)()
        self.assertEqual(run.call_args_list[-1].args,
                         ('apt-get','install','-y','--no-remove','varnish=9.1.0-official','varnish-modules'))
        self.assertEqual(run.call_args.kwargs['env']['NEEDRESTART_MODE'], 'l')
        namespace['repository'].setup.assert_not_called()

    def test_module_preview_cannot_replace_a_running_engine_or_another_service(self):
        for preview in (b'Inst varnish [9.1] (9.2 official)\n', b'Remv apache2 [1.0]\n'):
            run = Mock(return_value=subprocess.CompletedProcess([], 0, preview, b''))
            namespace = dict(cookie_modules_available=Mock(return_value=False), repository=Mock(),
                             run=run, progress=Mock(), os=Mock(environ={}), re=__import__('re'),
                             cookie_module_package=Mock(return_value='varnish-modules'),
                             native_version=Mock(return_value='9.1.0-official'))
            with self.assertRaisesRegex(ValueError, 'different Varnish engine'):
                installer_function('ensure_cookie_modules', namespace)()
            self.assertEqual(len(run.call_args_list), 2)

    def test_module_selection_uses_installed_abi_when_newer_module_needs_newer_engine(self):
        run = Mock(side_effect=[subprocess.CompletedProcess([],0,b'varnishabi-existing',b''),
            subprocess.CompletedProcess([],0,b'Package: varnish-modules\nVersion: 9.2\nDepends: varnishabi-new\n\nPackage: varnish-modules\nVersion: 9.1-rebuild\nDepends: varnishabi-existing, varnish (= 9.1-rebuild)\n\nPackage: varnish-modules\nVersion: 9.1\nDepends: varnishabi-existing, varnish (= 9.1), libc6\n',b'')])
        namespace = dict(run=run,re=__import__('re'))
        self.assertEqual(installer_function('cookie_module_package',namespace)('9.1'),'varnish-modules=9.1')

    def test_failed_child_preserves_output_exit_code_and_arguments(self):
        run = installer_runner()
        output = io.StringIO()
        script = 'import sys; print("installation progress"); print("Permission denied: panel/index.php", file=sys.stderr); sys.exit(7)'
        with contextlib.redirect_stderr(output), self.assertRaises(RuntimeError) as error:
            run(sys.executable, '-c', script)
        self.assertIn('installation progress', output.getvalue())
        self.assertIn('Permission denied: panel/index.php', output.getvalue())
        self.assertIn('exit 7', str(error.exception))
        self.assertIn(shlex.quote(script), str(error.exception))

    def test_success_remains_captured_and_quiet(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            result = installer_runner()(sys.executable, '-c', 'print("installed")')
        self.assertEqual(result.stdout.strip(), b'installed')
        self.assertEqual(output.getvalue(), '')

    def test_nested_python_traceback_reaches_administrator(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output), self.assertRaises(RuntimeError):
            installer_runner()(sys.executable, '-c', 'raise FileNotFoundError("missing integration dependency")')
        self.assertIn('Traceback (most recent call last)', output.getvalue())
        self.assertIn('FileNotFoundError: missing integration dependency', output.getvalue())

    def test_php_lint_failure_preserves_both_output_streams(self):
        result = subprocess.CompletedProcess([], 255, b'Errors parsing index.php', b'PHP Parse error on line 8')
        panel = Path('/example/panel/index.php')
        with patch.object(deployment.subprocess, 'run', return_value=result), self.assertRaises(RuntimeError) as error:
            deployment.check_panel(panel)
        for detail in ('exit 255', str(panel), 'Errors parsing index.php', 'PHP Parse error on line 8'):
            self.assertIn(detail, str(error.exception))

    def test_php_lint_success_is_quiet(self):
        result = subprocess.CompletedProcess([], 0, b'No syntax errors detected', b'')
        with patch.object(deployment.subprocess, 'run', return_value=result):
            self.assertIsNone(deployment.check_panel(Path('/example/panel/index.php')))


if __name__ == '__main__':
    unittest.main()
