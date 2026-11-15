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
    def test_fresh_install_uses_signed_apt_candidate_without_a_version_pin(self):
        run = Mock(return_value=subprocess.CompletedProcess([], 0, b'Inst varnish (9.2.0 official [amd64])', b''))
        path = Mock(return_value=Mock(read_text=Mock(return_value='ID=ubuntu\nVERSION_CODENAME=resolute\n')))
        repository = Mock()
        namespace = dict(Path=path, run=run, repository=repository, os=Mock(environ={}), subprocess=Mock())
        namespace['subprocess'].run.return_value = subprocess.CompletedProcess([], 1, b'', b'')
        installer_function('install_package', namespace)()
        repository.setup.assert_called_once_with()
        self.assertEqual(run.call_args_list[1].args, ('apt-get', '-s', 'install', 'varnish'))
        self.assertEqual(run.call_args_list[2].args, ('apt-get', 'install', '-y', 'varnish'))
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
