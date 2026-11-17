import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import cookie_policy
import cookie_bridge as bridge
import cookie_control as control
from test_cookie_admin import settings


def fixture():
    return {'owners': {'alice': {'sites': {'one.example': {
        'id': 'a'*32, 'domain': 'one.example', 'aliases': [], 'token': 'fixture-token',
        'cookie_integration': {'enabled': True, 'url': 'https://one.example'+control.PATH}}}}}}


class CookieBridge(unittest.TestCase):
    def test_lost_alias_ownership_disables_connection_without_contacting_new_owner(self):
        before=fixture();entry=before['owners']['alice']['sites']['one.example']
        entry['aliases']=['old.example'];entry['cookie_integration']['url']='https://old.example'+control.PATH
        after=copy.deepcopy(before);after['owners']['alice']['sites']['one.example']['aliases']=[]
        bridge.reconcile_inventory(after)
        site=after['owners']['alice']['sites']['one.example']
        self.assertFalse(site['cookie_integration']['enabled'])
        self.assertIn('no longer assigned',site['cookie_integration_notice'])
        self.assertEqual(bridge.plan(after,before),[])

    def test_unchanged_or_unconnected_sites_make_no_plan(self):
        state = fixture()
        self.assertEqual(bridge.plan(state, copy.deepcopy(state)), [])
        del state['owners']['alice']['sites']['one.example']['cookie_integration']
        self.assertEqual(bridge.plan(state, None), [])

    def test_restore_forces_signed_resync_even_when_native_snapshot_is_unchanged(self):
        state = fixture()
        result = bridge.plan(state, copy.deepcopy(state), force=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['kind'], 'apply')

    def test_explicit_save_resyncs_only_selected_connected_site(self):
        state = fixture()
        other = copy.deepcopy(state['owners']['alice']['sites']['one.example'])
        other.update(id='b'*32,domain='two.example',cookie_integration={'enabled':True,'url':'https://two.example'+control.PATH})
        state['owners']['alice']['sites']['two.example'] = other
        result = bridge.plan(state, copy.deepcopy(state), force_sites={'a'*32})
        self.assertEqual([row['site_id'] for row in result], ['a'*32])

    def test_disable_clears_previous_managed_snapshot(self):
        before = fixture(); after = copy.deepcopy(before)
        after['owners']['alice']['sites']['one.example']['cookie_integration']['enabled'] = False
        result = bridge.plan(after, before)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['kind'], 'disconnect')
        self.assertEqual(result[0]['policy'], control.snapshot())
        self.assertTrue(result[0]['configuration']['enabled'])

    def test_shadowed_changes_and_descriptions_do_not_contact_application(self):
        before = fixture(); before['cookie_policies'] = settings('foo', 'shared')
        before['owners']['alice']['sites']['one.example']['cookie_policies'] = settings('foo', 'variant')
        after = copy.deepcopy(before); after['cookie_policies']['rules'][0]['action'] = 'private'
        self.assertEqual(bridge.plan(after, before), [])
        after['cookie_policies']['rules'][0]['description'] = 'Updated description'
        self.assertEqual(bridge.plan(after, before), [])

    def test_lost_commit_reply_is_rolled_back_from_journal_identity(self):
        before = fixture(); after = copy.deepcopy(before)
        after['cookie_policies'] = settings('currency', 'variant')
        operations = bridge.plan(after, before)
        events, saved = [], []
        class Client:
            def __init__(self, configuration, host, token, policy, request_id=None, aliases=()):
                self.request_id = request_id or 'a'*32
                self.base_digest = 'b'*64; self.target_digest = 'c'*64
            def call(self, operation):
                events.append(operation)
                if operation == 'status':
                    return {'capabilities': {'scopedCookiePolicies': True}}
                if operation == 'commit':
                    raise control.ControlError('Lost reply')
                if operation == 'rollback':
                    return {'rollbackState':'restored','activeDigest':self.base_digest}
        def persist():
            saved.append(copy.deepcopy(operations))
        with patch.object(control, 'Client', Client):
            bridge.inspect(operations)
            bridge.prepare(operations, persist)
            with self.assertRaises(control.ControlError):
                bridge.commit(operations, persist)
            journal = saved[-1]
            self.assertEqual(journal[0]['phase'], 'committing')
            bridge.rollback(journal)
        self.assertEqual(events, ['status', 'prepare', 'commit', 'rollback'])
        self.assertEqual(journal[0]['phase'], 'rolled-back')

    def test_removed_domain_does_not_block_other_inventory(self):
        before = fixture(); after = {'owners': {}}
        self.assertEqual(bridge.plan(after, before), [])

    def test_url_switch_same_application_prepares_after_old_policy_clear(self):
        before=fixture();before['cookie_policies']=settings('currency','variant')
        before['owners']['alice']['sites']['one.example']['cookie_integration']['url']='http://one.example'+control.PATH
        after=copy.deepcopy(before)
        after['cookie_policies']=settings('currency','shared')
        after['owners']['alice']['sites']['one.example']['cookie_integration']['url']='https://one.example'+control.PATH
        operations=bridge.plan(after,before)
        original=control.effective_digest('one.example',control.snapshot(before['cookie_policies']))
        current=original;sequence=[];staged={};ids=iter(['a'*32,'b'*32])
        class Client:
            def __init__(self,configuration,host,token,policy,request_id=None,aliases=()):
                self.request_id=request_id or next(ids)
                self.target_digest=control.effective_digest(host,policy)
                self.base_digest=''
            def call(self,operation):
                nonlocal current
                sequence.append(operation)
                if operation=='status':
                    self.base_digest=current
                    return {'capabilities':{'scopedCookiePolicies':True}}
                if operation=='prepare':
                    if self.base_digest!=current:raise control.ControlError('Stale prepare')
                    staged[self.request_id]=(self.base_digest,self.target_digest)
                elif operation=='commit':
                    if self.base_digest!=current:raise control.ControlError('Stale commit')
                    current=self.target_digest
                elif operation=='rollback':
                    base,target=staged[self.request_id]
                    if current!=target:raise control.ControlError('Newer writer')
                    current=base
                    return {'rollbackState':'restored','activeDigest':current}
        saved=[]
        def persist():saved.append(copy.deepcopy(operations))
        with patch.object(control,'Client',Client):
            bridge.inspect(operations)
            bridge.prepare(operations,persist)
            self.assertEqual(operations[1]['phase'],'deferred')
            bridge.commit(operations,persist)
            self.assertEqual(current,control.effective_digest('one.example',control.snapshot(after['cookie_policies'])))
            bridge.rollback(operations,persist)
        self.assertEqual(current,original)
        self.assertEqual(sequence,['status','status','prepare','commit','status','prepare','commit','rollback','rollback'])
