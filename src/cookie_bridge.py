"""Hestia transaction adapter for explicitly connected WordPress sites."""
import copy
import cookie_admin
import cookie_control


def _sites(state):
    return {site['id']: dict(site, domain=domain)
            for owner in (state or {}).get('owners', {}).values()
            for domain, site in owner['sites'].items()}


def validate(state):
    cookie_admin.normalize(state.get('cookie_policies'))
    for site in _sites(state).values():
        cookie_admin.normalize(site.get('cookie_policies'))
        cookie_control.integration(site.get('cookie_integration'), site['domain'], site.get('aliases', []))


def reconcile_inventory(state):
    for owner in state['owners'].values():
        for domain,site in owner['sites'].items():
            if 'cookie_integration' not in site:
                continue
            normalized,revoked=cookie_control.reconcile_integration(site['cookie_integration'],domain,site.get('aliases',[]))
            site['cookie_integration']=normalized
            if revoked:
                site['cookie_integration_notice']='The previous WordPress endpoint is no longer assigned to this website. The connection was disabled.'


def plan(state, previous, *, force=False, force_sites=()):
    before = _sites(previous)
    result = []
    for sid, site in sorted(_sites(state).items()):
        old = before.get(sid)
        config = cookie_control.integration(site.get('cookie_integration'), site['domain'], site.get('aliases', []))
        old_config = cookie_control.integration(old.get('cookie_integration'), old['domain'], old.get('aliases', [])) if old else None
        if old_config and old_config['enabled']:
            _,revoked=cookie_control.reconcile_integration(old_config,site['domain'],site.get('aliases',[]))
            if revoked:old_config=None
        switched = bool(old_config and old_config['enabled'] and (not config['enabled'] or old_config['url'] != config['url']))
        def operation(target, configuration, policy, kind):
            result.append({'site_id': sid, 'configuration': copy.deepcopy(configuration),
                           'host': target['domain'], 'aliases': target.get('aliases', []),
                           'token': target['token'], 'policy': policy, 'kind': kind,
                           'phase': 'planned'})
        if switched:
            operation(old, old_config, cookie_control.snapshot(), 'disconnect')
        changed = (not old or cookie_admin.executable((previous or {}).get('cookie_policies'), old.get('cookie_policies')) !=
                   cookie_admin.executable(state.get('cookie_policies'), site.get('cookie_policies')))
        if config['enabled'] and (force or sid in force_sites or switched or not old_config or not old_config['enabled'] or changed):
            operation(site, config, cookie_control.snapshot(state.get('cookie_policies'), site.get('cookie_policies')), 'apply')
    # A deleted native domain has no managed route left to synchronize. We never
    # block unrelated inventory by trying to contact an already removed website.
    return result


def _client(operation):
    client = cookie_control.Client(operation['configuration'], operation['host'], operation['token'],
        operation['policy'], request_id=operation.get('request_id'), aliases=operation['aliases'])
    client.base_digest = operation.get('base_digest', '')
    return client


def inspect(operations):
    """Read-only preflight. No application state is changed before journaling."""
    for operation in operations:
        client = _client(operation)
        status = client.call('status')
        if not isinstance(status.get('capabilities'), dict) or status['capabilities'].get('scopedCookiePolicies') is not True:
            raise cookie_control.ControlError('WordPress does not support scoped cookie policies')
        operation.update(request_id=client.request_id, base_digest=client.base_digest, target_digest=client.target_digest)


def prepare(operations, persist):
    disconnected = set()
    for operation in operations:
        if operation['kind'] == 'apply' and operation['site_id'] in disconnected:
            # Both URLs can reach the same WordPress installation. Preparing
            # against its pre-disconnect digest would make commit stale after
            # the preceding clear. No mutation has happened for this op yet.
            operation['phase'] = 'deferred'; persist()
            continue
        operation['phase'] = 'preparing'; persist()
        _client(operation).call('prepare')
        operation['phase'] = 'prepared'; persist()
        if operation['kind'] == 'disconnect':
            disconnected.add(operation['site_id'])


def commit(operations, persist):
    for operation in operations:
        if operation['phase'] == 'deferred':
            inspect([operation])
            operation['phase'] = 'preparing'; persist()
            _client(operation).call('prepare')
            operation['phase'] = 'prepared'; persist()
        operation['phase'] = 'committing'; persist()
        _client(operation).call('commit')
        operation['phase'] = 'committed'; persist()


def rollback(operations, persist=lambda: None):
    for operation in reversed(operations):
        if operation['phase'] in ('planned', 'deferred', 'rolled-back'):
            continue
        # Also covers a lost commit reply: the remote request identity/base/target
        # decide what happened, not whether our local worker saw the response.
        result = _client(operation).call('rollback')
        operation['rollback_state'] = result['rollbackState']
        operation['rollback_active_digest'] = result['activeDigest']
        operation['phase'] = 'rolled-back'; persist()


def preserved_newer(operations):
    return [{'site_id':row['site_id'],'state':row['rollback_state'],'active_digest':row['rollback_active_digest']}
            for row in operations if row.get('rollback_state') in ('not-applied','superseded') and
            row.get('rollback_active_digest') != row.get('base_digest')]
