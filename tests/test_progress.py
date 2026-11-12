"""Installer reporting cannot alter panel JSON, deadlines or completed work."""
import contextlib
import io
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import progress
import routing
from test_install_errors import installer_runner


class Progress(unittest.TestCase):
    def test_disabled_reporting_is_silent(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            progress.stage('Not a panel response')
        self.assertEqual(output.getvalue(), '')

    def test_slow_command_reports_current_stage_without_stopping_work_or_changing_stdout(self):
        output = io.StringIO()
        run = installer_runner()
        with progress.reporting(output, interval=.02):
            result = run(sys.executable, '-c', 'import time; time.sleep(.12); print("completed")')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), b'completed')
        self.assertIn('Command:', output.getvalue())
        self.assertIn('Still working', output.getvalue())
        text = output.getvalue()
        time.sleep(.04)
        self.assertEqual(output.getvalue(), text)

    def test_closed_console_does_not_turn_success_into_failure(self):
        output = io.StringIO(); output.close()
        with progress.reporting(output, interval=.01):
            progress.stage('Executing native work')
            time.sleep(.03)
            result = installer_runner()(sys.executable, '-c', 'print("completed")')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), b'completed')

    def test_exception_stops_reporting_and_quiet_mode_is_restored(self):
        output = io.StringIO()
        with self.assertRaisesRegex(RuntimeError, 'native error'):
            with progress.reporting(output, interval=.01):
                progress.stage('Compiling VCL')
                raise RuntimeError('native error')
        previous = output.getvalue()
        progress.stage('Should be silent again')
        time.sleep(.02)
        self.assertEqual(output.getvalue(), previous)

    def test_domain_counts_and_reload_are_actual_operations(self):
        changes = [('alice', 'one.example.test', 'old', 'new', 'css'),
                   ('bob', 'two.example.test', 'old', 'new', 'css')]
        with contextlib.ExitStack() as stack:
            folder = stack.enter_context(__import__('tempfile').TemporaryDirectory())
            path = Path(folder) / 'apache.conf'
            path.write_bytes((routing.MARKER + '\n').encode())
            stack.enter_context(patch.object(routing, 'APACHE', path))
            set_template = stack.enter_context(patch.object(routing, 'set_template'))
            stack.enter_context(patch.object(routing, 'run'))
            reload = stack.enter_context(patch.object(routing, 'reload_nginx'))
            output = io.StringIO()
            with progress.reporting(output):
                result, _ = routing.apply(changes, routing.MARKER + '\n')
            self.assertEqual(result['route_updates'], 2)
            self.assertEqual(set_template.call_count, 2)
            reload.assert_called_once()
            self.assertIn('Domain 1/2: one.example.test (alice)', output.getvalue())
            self.assertIn('Domain 2/2: two.example.test (bob)', output.getvalue())
            self.assertIn('Validating Apache and Nginx', output.getvalue())


if __name__ == '__main__': unittest.main()
