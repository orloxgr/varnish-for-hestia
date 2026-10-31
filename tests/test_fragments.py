import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from fragments import FragmentError, validate
from vcl import render


def state():
    return {'owners': {'alice': {'enabled': True, 'suspended': False, 'package': 'default', 'sites': {
        'example.test': {'id': 'a' * 32, 'aliases': ['www.example.test', '*.example.test'],
                         'profile': 'ultracache', 'token': 'a' * 32, 'enabled': True,
                         'suspended': False, 'custom_recv': '', 'custom_backend_response': ''}}}}}


class FragmentTests(unittest.TestCase):
    def test_useful_site_local_vcl(self):
        source = '''# own request condition
        if (req.url ~ "^/special/") { return (pass); }
        else if (req.http.User-Agent ~ "robot") { set req.http.X-User-Client = "bot"; }
        else { unset req.http.X-User-Client; }'''
        self.assertIn('return ( pass ) ;', validate(source, 'recv'))
        self.assertIn('beresp.ttl', validate('if (beresp.status == 200) { set beresp.ttl = 30m; }', 'backend_response'))

    def test_tenant_cannot_escape_or_bypass_immutable_policy(self):
        forbidden = ['} sub vcl_recv { return (hash);', 'include "/etc/shadow";',
                     'import std;', 'C{ system("id"); }C', 'call vcl_recv;',
                     'set req.backend_hint = foreign;', 'set req.http.host = "foreign.test";',
                     'set req.http.Cookie = "wordpress_logged_in=1";',
                     'unset req.http.Authorization;', 'return (hash);', 'return (pipe);',
                     'set req.http.X-HVH-Site = "foreign";', 'ban("obj.status > 0");',
                     'set req.http.X-User-Probe = std.fileread("/etc/shadow");',
                     'if (req.http.X-HVH-Site == "foreign") { return (pass); }',
                     'if (req.http.x-hvh-site == "foreign") { return (pass); }']
        for source in forbidden:
            with self.subTest(source=source), self.assertRaises(FragmentError):
                validate(source, 'recv')
        for source in ['set beresp.uncacheable = false;', 'unset beresp.http.Set-Cookie;',
                       'set beresp.http.Cache-Control = "public";', 'return (deliver);',
                       'set bereq.http.host = "foreign.test";']:
            with self.subTest(source=source), self.assertRaises(FragmentError):
                validate(source, 'backend_response')

    def test_strings_and_comments_cannot_inject_code(self):
        self.assertEqual('set req.http.X-User-Note = "include \\"file\\";" ;',
                         validate('set req.http.X-User-Note = "include \\"file\\";"; # return(hash)', 'recv'))
        with self.assertRaises(FragmentError):
            validate('set req.http.X-User-Note = "ok"; include "evil.vcl";', 'recv')

    def test_complexity_is_bounded(self):
        with self.assertRaises(FragmentError):
            validate('#' + 'x' * 16384, 'recv')
        with self.assertRaises(FragmentError):
            validate('if (' + '!' * 2000 + 'req.url) { return(pass); }', 'recv')
        with self.assertRaises(FragmentError):
            validate('if(req.url){' * 30 + 'return(pass);' + '}' * 30, 'recv')

    def test_all_profiles_selectable_with_no_application_inventory(self):
        for profile in ('general', 'wordpress', 'woocommerce', 'ultracache'):
            fixture = state(); fixture['owners']['alice']['sites']['example.test']['profile'] = profile
            result = render(fixture, {'origin_ip': '127.0.0.1'})
            self.assertIn('set req.http.X-HVH-Profile = "' + profile + '";', result)

    def test_duplicate_alias_or_scope_refused(self):
        fixture = state()
        site = copy.deepcopy(fixture['owners']['alice']['sites']['example.test'])
        site['id'] = 'b' * 32
        fixture['owners']['alice']['sites']['second.test'] = site
        with self.assertRaises(ValueError):
            render(fixture, {'origin_ip': '127.0.0.1'})

    def test_hostname_and_origin_cannot_inject_vcl(self):
        fixture = state(); site = fixture['owners']['alice']['sites'].pop('example.test')
        fixture['owners']['alice']['sites']['evil";}.test'] = site
        with self.assertRaises(ValueError):
            render(fixture, {'origin_ip': '127.0.0.1'})
        with self.assertRaises(ValueError):
            render(state(), {'origin_ip': '127.0.0.1";})'})

    def test_more_specific_wildcard_routes_first(self):
        fixture = state()
        site = copy.deepcopy(fixture['owners']['alice']['sites']['example.test'])
        site.update(id='b' * 32, aliases=['*.sub.example.test'])
        fixture['owners']['alice']['sites']['other.test'] = site
        result = render(fixture, {'origin_ip': '127.0.0.1'})
        self.assertLess(result.index('sub[.]example[.]test'), result.index('+example[.]test'))

    def test_each_native_origin_ip_gets_its_own_backend_assignment(self):
        fixture = state()
        site = copy.deepcopy(fixture['owners']['alice']['sites']['example.test'])
        site.update(id='b' * 32, aliases=[], origin_ip='127.0.0.2')
        fixture['owners']['alice']['sites']['other.test'] = site
        result = render(fixture, {'origin_ip': '127.0.0.1'})
        self.assertIn('backend hvh_origin_1 { .host = "127.0.0.2";', result)
        import re
        self.assertRegex(result, r'req.http.host == "other[.]test"\) \{[^}]*set req.backend_hint = hvh_origin_1;')
        fixture['owners']['alice']['sites']['other.test']['origin_ip'] = '127.0.0.1"; }'
        with self.assertRaises(ValueError):
            render(fixture, {'origin_ip': '127.0.0.1'})


if __name__ == '__main__':
    unittest.main()
