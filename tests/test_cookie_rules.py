"""Cookie rule input, lifecycle, account boundaries and native HTTP behavior."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import addon
import cookie_policy
import maintenance
import service
from registry import desired_state
import test_registry as registry_tests
import test_profile_compatibility as compatibility
import test_cache_policy as policy_tests


def fixture():
    inventory = registry_tests.fixture(2, 2)
    state = desired_state(None, inventory, 'varnish')
    for owner in state['owners'].values():
        for site in owner['sites'].values():
            site['profile'] = 'woocommerce'
    return state, inventory


class CookieRules(unittest.TestCase):
    def test_exact_names_prefixes_blank_lines_duplicates_and_case(self):
        self.assertEqual(cookie_policy.normalize(' membership_*\r\ncurrency\n\nmembership_*\nCurrency '),
                         ['membership_*', 'currency', 'Currency'])
        self.assertEqual(cookie_policy.normalize(''), [])

    def test_invalid_rules_cannot_become_vcl_regex_or_unbounded_input(self):
        for value in [None, True, {}, ['valid', 12], '*', 'member**', 'a*b', 'a?', 'a=value',
                      'a|b', '^cookie$', 'cookie name', 'x"; return(pass); #',
                      'a'*129, '\n'.join('rule'+str(n) for n in range(65)), 'a'*8193]:
            with self.subTest(value=str(value)[:40]), self.assertRaises(ValueError):
                cookie_policy.normalize(value)

    def test_migration_lifecycle_and_profile_change_preserve_rules(self):
        state, inventory = fixture()
        site = state['owners']['user000']['sites']['s0.user000.test']
        site['bypass_cookies'] = ['membership_*']
        del state['owners']['user001']['sites']['s0.user001.test']['bypass_cookies']
        after = desired_state(state, inventory, 'varnish')
        self.assertEqual(after['owners']['user000']['sites']['s0.user000.test'], site)
        self.assertEqual(after['owners']['user001']['sites']['s0.user001.test']['bypass_cookies'], [])
        import administration
        administration.mutate(after, {'scope':'all', 'operation':'set-profile', 'profile':'ultracache'}, 'varnish')
        self.assertEqual(after['owners']['user000']['sites']['s0.user000.test']['bypass_cookies'], ['membership_*'])

    def test_save_is_domain_scoped_and_preserves_other_settings(self):
        state, _ = fixture()
        before = copy.deepcopy(state)
        config = {'origin_ip':'127.0.0.1'}
        def reconcile(hestia, mutate):
            candidate = copy.deepcopy(state)
            mutate(candidate, config)
            service.render(candidate, config)
            state.clear(); state.update(candidate)
            return state, config, {}
        with patch.object(service, 'reconcile', side_effect=reconcile):
            response = service.request(None, 'user000', 'configure-cookies',
                {'domain':'s0.user000.test', 'bypass_cookies':'membership_*\ncurrency'})
            expected = copy.deepcopy(before)
            expected['owners']['user000']['sites']['s0.user000.test']['bypass_cookies'] = ['membership_*', 'currency']
            self.assertEqual(state, expected)
            self.assertEqual(response['sites'][0]['bypass_cookies'], ['membership_*', 'currency'])
            with self.assertRaises(ValueError):
                service.request(None, 'user000', 'configure-cookies',
                    {'domain':'s0.user001.test', 'bypass_cookies':'*'})
            with self.assertRaises(ValueError):
                service.request(None, 'user000', 'configure-cookies',
                    {'domain':'s0.user000.test', 'bypass_cookies':'*'})
            self.assertEqual(state, expected)
            service.request(None, 'user000', 'configure-site',
                {'domain':'s0.user000.test', 'profile':'wordpress', 'custom_recv':'return (pass);'})
            self.assertEqual(state['owners']['user000']['sites']['s0.user000.test']['bypass_cookies'],
                             ['membership_*', 'currency'])
            service.request(None, 'user000', 'configure-cookies',
                {'domain':'s0.user000.test', 'bypass_cookies':''})
            self.assertEqual(state['owners']['user000']['sites']['s0.user000.test']['bypass_cookies'], [])

    def test_native_account_role_protects_cookie_action(self):
        with patch.object(addon, 'hestia', return_value={'user000':{'ROLE':'user','SUSPENDED':'no'}}), \
             patch.object(service, 'request') as request:
            with self.assertRaises(addon.RequestError):
                addon.dispatch({'actor':'user000','owner':'user001','action':'configure-cookies'})
            request.assert_not_called()

    def test_cookie_change_invalidates_only_selected_site(self):
        previous, _ = fixture()
        state = copy.deepcopy(previous)
        site = state['owners']['user000']['sites']['s0.user000.test']
        site['bypass_cookies'] = ['membership_*']
        config = {'origin_ip':'127.0.0.1','origin_port':8080}
        program = service.render(state, config)
        name = 'hvh_gen_'+hashlib.sha256(program.encode()).hexdigest()[:32]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'active.vcl'; path.write_text(program)
            with patch.object(service,'ACTIVE',path), \
                 patch.object(service,'vcls',return_value=[{'name':name,'status':'active'}]), \
                 patch.object(service.routing,'apply',return_value=({},None)), \
                 patch.object(service.routing,'apache_config',return_value=''), \
                 patch.object(service,'purge') as purge, patch.object(service,'prune'):
                result = service.apply(state, previous, {}, config, changes=[])
                self.assertEqual(result['invalidated_sites'], 1)
                purge.assert_called_once_with(config, site)

    def test_backup_validation_preserves_rules_and_rejects_invalid_archived_rules(self):
        state, _ = fixture()
        site = state['owners']['user000']['sites']['s0.user000.test']
        site['bypass_cookies'] = ['membership_*']
        payload = {'settings':{'schema':1,'listen_port':6081,'admin_port':6082,'memory_mb':512,
                               'origin_ip':'127.0.0.1'}, 'desired':state,
                   'admin_secret':base64.b64encode(b'fixture-secret').decode()}
        saved = json.dumps(payload)
        maintenance.validate(payload)
        self.assertEqual(json.dumps(payload), saved)
        site['bypass_cookies'] = ['*']
        with self.assertRaises(ValueError): maintenance.validate(payload)


@unittest.skipUnless(compatibility.shutil.which('varnishtest'), 'native varnishtest is required')
class NativeRules(unittest.TestCase):
    run_policy = policy_tests.CachePolicy.run_policy

    def test_custom_exact_prefix_case_and_literal_names(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                source = compatibility.program(profile, bypass_cookies=['membership_*', 'currency', 'plugin.cookie-name'])
                responses, requests = [], []
                for cookie in ['membership_gold=1', 'currency=EUR', 'plugin.cookie-name=private']:
                    for visitor in ('A','B'):
                        responses.append(compatibility.response('/page',visitor,
                            expect=['expect req.http.Cookie == "'+cookie+'"']))
                        requests.append(compatibility.request('/page',visitor,headers=['Cookie: '+cookie],cache='BYPASS'))
                for number, cookie in enumerate(['prefixcurrency=EUR', 'Currency=EUR', 'membership=1',
                                                 'pluginXcookie-name=1', 'plugin.cookieXname=1']):
                    path = '/public-'+str(number)
                    responses.append(compatibility.response(path,'public',
                        expect=['expect req.http.Cookie == "'+cookie+'"']))
                    requests.extend([compatibility.request(path,'public',headers=['Cookie: '+cookie],cache='MISS'),
                                     compatibility.request(path,'public',headers=['Cookie: '+cookie],cache='HIT')])
                self.run_policy(profile,responses,requests,program=source)

    def test_custom_rule_cannot_be_hidden_in_second_cookie_header(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [compatibility.response('/page',visitor) for visitor in ('A','B')],
                    [compatibility.request('/page',visitor,
                         headers=['Cookie: tracking=1','Cookie: membership_gold=1'],cache='BYPASS')
                     for visitor in ('A','B')],
                    program=compatibility.program(profile,bypass_cookies=['membership_*']))

    def test_private_cookie_cannot_be_hidden_in_second_cookie_header(self):
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                self.run_policy(profile,
                    [compatibility.response('/page',visitor) for visitor in ('A','B')],
                    [compatibility.request('/page',visitor,
                         headers=['Cookie: tracking=1','Cookie: wordpress_logged_in_abcd=private'],cache='BYPASS')
                     for visitor in ('A','B')])

    def test_custom_rule_takes_precedence_over_esi_opt_in(self):
        self.run_policy('ultracache',
            [compatibility.response('/page',visitor) for visitor in ('A','B')],
            [compatibility.request('/page',visitor,headers=[
                'Cookie: ultracache_esi_optin=1; woocommerce_items_in_cart=1; membership_gold=1'],cache='BYPASS')
             for visitor in ('A','B')],
            program=compatibility.program('ultracache',bypass_cookies=['membership_*']))

    def test_unknown_cookies_allow_approved_esi_without_entering_private_carrier(self):
        fragment='/?ultracache_esi=cart&esi_scope=private'
        self.run_policy('ultracache',
            [compatibility.response('/parent', '<html><esi:include src="/?ultracache_esi=cart&amp;esi_scope=private"/></html>',
                headers=['Content-Type: text/html','Surrogate-Control: ESI/1.0','X-UltraCache-ESI-Shared-Parent: 1'],
                expect=['expect req.http.Cookie == "woocommerce_items_in_cart=1; custom_tracking=A"',
                        'expect req.http.X-UltraCache-ESI-Candidate == "1"']),
             *[compatibility.response(fragment,visitor,
                expect=['expect req.http.Cookie == "esi_session='+visitor+'; woocommerce_items_in_cart=1"'])
               for visitor in ('A','B')]],
            [compatibility.request('/parent','<html>'+visitor+'</html>',headers=[
                'Cookie: esi_session='+visitor+'; woocommerce_items_in_cart=1; ultracache_esi_optin=1; custom_tracking='+visitor],
                cache='MISS' if visitor=='A' else 'HIT') for visitor in ('A','B')])

    def test_cookie_rules_are_confined_to_one_site_and_its_aliases(self):
        from vcl import render
        def site(identity, aliases, rules):
            return {'id':identity*32,'profile':'woocommerce','token':'A'*32,'aliases':aliases,
                    'enabled':True,'suspended':False,'custom_recv':'','custom_backend_response':'', 'bypass_cookies':rules}
        state={'owners':{'one':{'enabled':True,'suspended':False,'package':'default','sites':{
            'example.test':site('a',['alias.example.test'],['membership_*'])}},
            'two':{'enabled':True,'suspended':False,'package':'default','sites':{
            'other.test':site('b',[],[])}}}}
        source=render(state,{'origin_ip':'127.0.0.1','origin_port':8080}).replace('"8080"','"${s1_port}"',1)
        responses,requests=[],[]
        for host in ['example.test','alias.example.test','other.test']:
            count=1 if host=='other.test' else 2
            for number in range(count):
                responses.append(compatibility.response('/page',str(number),
                    expect=['expect req.http.host == "'+host+'"']))
            for number in range(2):
                request=compatibility.request('/page',str(number if count==2 else 0),
                    headers=['Cookie: membership_gold=1'],cache='BYPASS' if count==2 else ('MISS' if number==0 else 'HIT'))
                requests.append(request.replace('Host: example.test','Host: '+host))
        self.run_policy('woocommerce',responses,requests,program=source)


if __name__ == '__main__': unittest.main()
