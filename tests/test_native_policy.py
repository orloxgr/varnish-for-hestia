"""Native freshness/retention and origin response policy without addon caps."""
import shutil
import unittest

import test_cache_policy as policy
import test_profile_compatibility as http


@unittest.skipUnless(shutil.which('varnishtest'), 'native varnishtest required')
class NativePolicy(unittest.TestCase):
    run_policy = policy.CachePolicy.run_policy

    def test_native_marker_lifetime_grace_and_keep_are_not_overridden(self):
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                source = http.program(profile).replace('  call scp_backend_response;', '''
  call scp_backend_response;
  set beresp.http.X-Test-TTL = beresp.ttl;
  set beresp.http.X-Test-Grace = beresp.grace;
  set beresp.http.X-Test-Keep = beresp.keep;
''')
                self.run_policy(profile,
                    [http.response('/public', 'public', policy='public, max-age=1800'),
                     http.response('/private', 'A', policy='private, no-store'),
                     http.response('/private', 'B', policy='private, no-store')],
                    [http.request('/public', 'public', cache='MISS'),
                     'expect resp.http.X-Test-TTL == "1800.000"',
                     'expect resp.http.X-Test-Grace == "41.000"',
                     'expect resp.http.X-Test-Keep == "23.000"',
                     http.request('/public', 'public', cache='HIT'),
                     http.request('/private', 'A', cache='PASS'),
                     'expect resp.http.X-Test-TTL == "37.000"',
                     'expect resp.http.X-Test-Grace == "41.000"',
                     'expect resp.http.X-Test-Keep == "23.000"',
                     http.request('/private', 'B', cache='PASS')],
                    program=source,
                    varnish_args='-arg "-p uncacheable_ttl=37 -p default_grace=41 -p default_keep=23"',
                    tail='varnish v1 -expect MAIN.cache_hitmiss == 1')

    def test_origin_can_cache_public_error_responses_and_private_errors_stay_private(self):
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                responses, requests = [], []
                for status in (404, 410):
                    path = '/status-' + str(status)
                    responses.append(http.response(path, 'public', status=status, policy='public, max-age=1800'))
                    requests.extend([http.request(path, 'public', status=status, cache='MISS'),
                                     http.request(path, 'public', status=status, cache='HIT')])
                    for visitor in ('A', 'B'):
                        responses.append(http.response(path + '-private', visitor, status=status, policy='private, no-store'))
                        requests.append(http.request(path + '-private', visitor, status=status, cache='PASS'))
                self.run_policy(profile, responses, requests)

    def test_native_error_freshness_is_kept_and_explicit_site_ttl_is_not_vetoed(self):
        for profile in http.PROFILES:
            for override in (False, True):
                with self.subTest(profile=profile, override=override):
                    responses, requests = [], []
                    for status in (500, 503):
                        path = '/error-' + str(status)
                        # Native Varnish assigns a negative TTL to these statuses.
                        # Only an explicit site rule changes that native decision.
                        visitors = ('public',) if override else ('A', 'B')
                        for visitor in visitors:
                            responses.append(http.response(path, visitor, status=status, policy='public, max-age=1800'))
                            requests.append(http.request(path, visitor, status=status, cache='MISS' if override else 'PASS'))
                        if override:
                            requests.append(http.request(path, 'public', status=status, cache='HIT'))
                        for visitor in ('A', 'B'):
                            responses.append(http.response(path + '-private', visitor, status=status, policy='private, no-store'))
                            requests.append(http.request(path + '-private', visitor, status=status, cache='PASS'))
                    source = http.program(profile, backend_response='set beresp.ttl = 1800s;' if override else '')
                    self.run_policy(profile, responses, requests, program=source)

    def test_unknown_response_cookie_remains_uncached_and_downstream_private(self):
        for profile in http.PROFILES:
            with self.subTest(profile=profile):
                responses, requests = [], []
                for number, control in enumerate(('public, max-age=1800', 'no-cache', None)):
                    path = '/cookie-' + str(number)
                    for visitor in ('A', 'B'):
                        # Unknown fields cannot receive Shared admission.
                        response = http.response(path, visitor, policy=control or '',
                            headers=['Set-Cookie: unknown_provider_cookie=' + visitor + '; Path=/'])
                        if control is None:
                            response = response.replace(' -hdr "Cache-Control: "', '')
                        responses.append(response)
                        requests.extend([http.request(path, visitor, cache='PASS'),
                            'expect resp.http.Set-Cookie == "unknown_provider_cookie=' + visitor + '; Path=/"',
                            'expect resp.http.Cache-Control == "private, no-store"'])
                self.run_policy(profile, responses, requests)


if __name__ == '__main__':
    unittest.main()
