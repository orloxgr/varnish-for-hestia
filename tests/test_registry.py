"""Lifecycle/transaction invariants, run on Linux without a service dependency."""
import copy
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from registry import desired_state, reconcile


def fixture(count=1, sites=3):
    return {f'user{i:03}':{'identity':f'{1000+i}:2026-10-31:12:00:00', 'package':'default',
                         'role':'user', 'suspended':False,
                         'sites':{f's{j}.user{i:03}.test':{'aliases':[f'alias{j}.user{i:03}.test'],
                                                        'suspended':False} for j in range(sites)}}
            for i in range(count)}


def worker(directory):
    state, changed = reconcile(directory, fixture(20), 'dragonfly')
    return {name:row['id'] for name,row in state['owners'].items()}


class Lifecycle(unittest.TestCase):
    def test_two_hundred_accounts_multiple_sites(self):
        for kind in ('dragonfly', 'varnish'):
            snapshot = fixture(200, 4)
            first = desired_state(None, snapshot, kind)
            self.assertEqual(first, desired_state(first, snapshot, kind))
            self.assertEqual(len(first['owners']), 200)
            sites = [s for u in first['owners'].values() for s in u['sites'].values()]
            self.assertEqual(len({s['id'] for s in sites}), 800)
            if kind == 'dragonfly':
                self.assertEqual(len({u['database'] for u in first['owners'].values()}), 200)
                self.assertGreaterEqual(first['required_database_capacity'], 200)
                self.assertEqual(len({s['prefix'] for s in sites}), 800)
            else:
                self.assertEqual(len({s['token'] for s in sites}), 800)

    def test_choices_and_credentials_survive_changes(self):
        for kind in ('dragonfly','varnish'):
            snapshot = fixture(2)
            old = desired_state(None, snapshot, kind)
            owner = old['owners']['user000']
            owner['enabled'] = False
            owner['sites']['s0.user000.test']['enabled'] = False
            owner['sites']['s0.user000.test']['settings'] = {'custom':'preserve'}
            snapshot['user000'].update(package='another-package', suspended=True)
            snapshot['user000']['sites']['s0.user000.test']['aliases'].append('*.extra.test')
            new = desired_state(old, snapshot, kind)
            current = new['owners']['user000']
            for key in ('id','enabled','password','database'):
                if key in owner:
                    self.assertEqual(owner[key],current[key])
            self.assertEqual(current['sites']['s0.user000.test']['settings'],{'custom':'preserve'})
            self.assertFalse(current['sites']['s0.user000.test']['enabled'])
            self.assertTrue(current['suspended'])

    def test_deleted_recreated_accounts_do_not_inherit_scopes(self):
        snapshot = fixture(2)
        first = desired_state(None, snapshot, 'dragonfly')
        old = first['owners']['user000']
        snapshot.pop('user000')
        removed = desired_state(first, snapshot, 'dragonfly')
        snapshot.update(fixture(1))
        restored = desired_state(removed, snapshot, 'dragonfly')
        new = restored['owners']['user000']
        for key in ('id','username','password','database','prefix'):
            self.assertNotEqual(old[key],new[key])
        self.assertEqual(len(restored['retired']),1)
        self.assertNotIn('password',restored['retired'][0])

    def test_same_name_replaced_between_polls(self):
        snapshot = fixture(1)
        first = desired_state(None,snapshot,'dragonfly')
        snapshot['user000']['identity'] += ':replacement'
        second = desired_state(first,snapshot,'dragonfly')
        self.assertNotEqual(first['owners']['user000']['id'],second['owners']['user000']['id'])
        self.assertNotEqual(first['owners']['user000']['database'],second['owners']['user000']['database'])

    def test_domain_recreation_rotates_scope(self):
        for kind in ('dragonfly','varnish'):
            snapshot = fixture(1)
            first = desired_state(None,snapshot,kind)
            before = first['owners']['user000']['sites']['s0.user000.test']
            site = snapshot['user000']['sites'].pop('s0.user000.test')
            removed = desired_state(first,snapshot,kind)
            snapshot['user000']['sites']['s0.user000.test'] = site
            recreated = desired_state(removed,snapshot,kind)
            after = recreated['owners']['user000']['sites']['s0.user000.test']
            self.assertNotEqual(before['id'],after['id'])
            self.assertNotEqual(before.get('prefix',before.get('token')),after.get('prefix',after.get('token')))

    def test_failed_inventory_keeps_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            reconcile(directory,fixture(2),'dragonfly')
            before = (Path(directory)/'desired.json').read_bytes()
            for snapshot in ({}, {'invalid;name':{}}, {'user000':{'identity':'1','sites':None}}):
                with self.assertRaises(ValueError):
                    reconcile(directory,snapshot,'dragonfly')
                self.assertEqual(before,(Path(directory)/'desired.json').read_bytes())
            self.assertEqual(stat.S_IMODE((Path(directory)/'desired.json').stat().st_mode),0o600)
            self.assertEqual(stat.S_IMODE(Path(directory).stat().st_mode),0o700)

    def test_concurrent_reconcilers_keep_one_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            with ProcessPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(worker,[directory]*12))
            self.assertTrue(all(result == results[0] for result in results))
            state = json.loads((Path(directory)/'desired.json').read_text())
            self.assertEqual(len(state['owners']),20)


if __name__ == '__main__':
    unittest.main(verbosity=2)
