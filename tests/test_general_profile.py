"""General caches public HTTP content without relying on application detection."""
import shutil
import unittest

import test_cache_policy as policy_tests
import test_profile_compatibility as compatibility


@unittest.skipUnless(shutil.which('varnishtest'), 'native varnishtest is required')
class GeneralProfile(unittest.TestCase):
    run_policy = policy_tests.CachePolicy.run_policy

    def test_public_html_css_and_generic_paths_ignore_unrelated_cookie_values(self):
        responses, requests = [], []
        for path, mime, body in [('/index.html', 'text/html', '<html>public</html>'),
                                 ('/assets/site.css', 'text/css', 'body {color: green}'),
                                 ('/cart/', 'text/html', '<html>generic directory</html>')]:
            cookie='sbjs_migrations=one; cmplz_banner-status=dismissed; unknown_vendor=one'
            responses.append(compatibility.response(path, body,
                headers=['Content-Type: '+mime], expect=['expect req.http.Cookie == "'+cookie+'"']))
            requests.extend([compatibility.request(path, body, headers=['Cookie: '+cookie], cache='MISS'),
                             compatibility.request(path, body, headers=['Cookie: unknown_vendor=another'], cache='HIT')])
        self.run_policy('general', responses, requests)

    def test_session_does_not_reuse_warm_public_html_or_css(self):
        responses, requests = [], []
        for path in ['/index.html', '/assets/site.css']:
            responses.append(compatibility.response(path, 'public'))
            requests.append(compatibility.request(path, 'public', cache='MISS'))
            for visitor in ('A', 'B'):
                cookie='unknown_vendor=tracking; PHPSESSID='+visitor
                responses.append(compatibility.response(path, visitor,
                    expect=['expect req.http.Cookie == "'+cookie+'"']))
                requests.append(compatibility.request(path, visitor, headers=['Cookie: '+cookie], cache='BYPASS'))
            requests.append(compatibility.request(path, 'public', headers=['Cookie: unknown_vendor=tracking'], cache='HIT'))
        self.run_policy('general', responses, requests)

    def test_response_cookie_is_delivered_once_and_never_replayed_from_cache(self):
        self.run_policy('general',
            [compatibility.response('/page', 'first', headers=['Set-Cookie: _fbp=fixture; Path=/']),
             compatibility.response('/page', 'public', expect=['expect req.http.Cookie == "_fbp=fixture"'])],
            [compatibility.request('/page', 'first', cache='BYPASS'),
             'expect resp.http.Set-Cookie == "_fbp=fixture; Path=/"',
             compatibility.request('/page', 'public', headers=['Cookie: _fbp=fixture'], cache='MISS'),
             'expect resp.http.Set-Cookie == <undef>',
             compatibility.request('/page', 'public', headers=['Cookie: _fbp=other'], cache='HIT'),
             'expect resp.http.Set-Cookie == <undef>'])

    def test_upgrade_refreshes_general_but_retains_other_profiles_cache(self):
        marker='  if (req.http.X-HVH-Profile == "general") { hash_data("hvh-general-cookie-v1"); }\n'
        for profile in compatibility.PROFILES:
            with self.subTest(profile=profile):
                source=compatibility.program(profile)
                self.assertIn(marker, source)
                previous=source.replace(marker, '')
                responses=[compatibility.response('/page', 'old')]
                if profile == 'general': responses.append(compatibility.response('/page', 'new'))
                body='new' if profile=='general' else 'old'
                cache='MISS' if profile=='general' else 'HIT'
                tail='varnish v1 -vcl {\n'+source+'\n}\nclient c2 {\n'+\
                    compatibility.request('/page',body,headers=['Cookie: unknown_vendor=tracking'],cache=cache)+'\n'+\
                    compatibility.request('/page',body,headers=['Cookie: unknown_vendor=another'],cache='HIT')+'\n} -run'
                self.run_policy(profile,responses,[compatibility.request('/page','old',cache='MISS')],
                                program=previous,tail=tail)


if __name__ == '__main__': unittest.main()
