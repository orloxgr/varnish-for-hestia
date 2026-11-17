"""Restore recovery preserves remote identity and healthy native services."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
if sys.platform != 'linux':
    raise unittest.SkipTest('Native Linux restore integration')
import maintenance
import cookie_control


def record(local_started=False):
    return {'before': [], 'extra': {'installed': True, 'local_started': local_started,
        'repository': None, 'config': {}, 'routes': [], 'apache': None,
        'cookie_operations': [{'request_id': 'a'*32, 'base_digest': 'b'*64,
                               'target_digest': 'c'*64, 'phase': 'committing'}]}}


class CookieRestore(unittest.TestCase):
    def test_remote_only_failed_restore_does_not_restart_working_services(self):
        data = record()
        events = []
        def rollback(operations, persist):
            events.append('remote-rollback')
            self.assertEqual(operations[0]['phase'], 'committing')
            operations[0]['phase'] = 'rolled-back'
            persist()
        with patch.object(maintenance.transaction, 'read', return_value=data), \
             patch.object(maintenance.cookie_bridge, 'rollback', side_effect=rollback), \
             patch.object(maintenance, 'write_json') as write, \
             patch.object(maintenance.transaction, 'restore_files', side_effect=lambda _:events.append('files')), \
             patch.object(maintenance.transaction, 'finish', side_effect=lambda *a,**k:events.append('finish')), \
             patch.object(maintenance.routing, 'run') as run, \
             patch.object(maintenance.routing, 'rollback') as routes, \
             patch.object(maintenance.repository, 'restore') as repository:
            maintenance.recover_restore()
        self.assertEqual(events, ['remote-rollback', 'files', 'finish'])
        self.assertEqual(write.call_args.args[1]['extra']['cookie_operations'][0]['phase'], 'rolled-back')
        run.assert_not_called(); routes.assert_not_called(); repository.assert_not_called()

    def test_failed_remote_rollback_retains_durable_record_and_native_state(self):
        data = record(True); before = copy.deepcopy(data)
        with patch.object(maintenance.transaction, 'read', return_value=data), \
             patch.object(maintenance.cookie_bridge, 'rollback', side_effect=cookie_control.ControlError('Offline')), \
             patch.object(maintenance.transaction, 'restore_files') as files, \
             patch.object(maintenance.transaction, 'finish') as finish, \
             patch.object(maintenance.routing, 'run') as run:
            with self.assertRaisesRegex(cookie_control.ControlError, 'Offline'):
                maintenance.recover_restore()
        files.assert_not_called(); finish.assert_not_called(); run.assert_not_called()
        self.assertEqual(data, before)

    def test_native_restore_recovery_rolls_app_back_before_restart(self):
        data = record(True); events = []
        with patch.object(maintenance.transaction, 'read', return_value=data), \
             patch.object(maintenance.cookie_bridge, 'rollback', side_effect=lambda *a:events.append('remote')), \
             patch.object(maintenance.transaction, 'restore_files', side_effect=lambda _:events.append('files')), \
             patch.object(maintenance.transaction, 'finish', side_effect=lambda *a,**k:events.append('finish')), \
             patch.object(maintenance.routing, 'run', side_effect=lambda *a:events.append(a)), \
             patch.object(maintenance.routing, 'rollback'), \
             patch.object(maintenance.repository, 'restore'), \
             patch.object(maintenance.subprocess, 'run'), \
             patch.object(maintenance.service, 'wait_healthy'), \
             patch.object(maintenance.deployment, 'rollback'):
            maintenance.recover_restore()
        self.assertEqual(events[0], 'remote')
        self.assertLess(events.index('files'), events.index(('systemctl', 'start', 'varnish')))
        self.assertEqual(events[-1], 'finish')
