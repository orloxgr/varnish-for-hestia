"""Installer diagnostics, without installing packages or modifying Hestia."""
import ast
import contextlib
import io
from pathlib import Path
import shlex
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import deployment


def installer_runner():
    # Load only the runner: importing the Linux installer initializes service
    # modules and requires native platform dependencies even on a test host.
    source = ROOT / 'tools/install.py'
    tree = ast.parse(source.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
    namespace = {'subprocess': subprocess, 'sys': sys, 'shlex': shlex}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['run']


class InstallerErrors(unittest.TestCase):
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
