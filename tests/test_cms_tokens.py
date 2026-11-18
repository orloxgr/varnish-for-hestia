"""Token delivery reads the application's component output, never invents IDs."""
import base64
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
import cms_sessions
import cms_session_server as server

TOKEN='0123456789abcdef0123456789abcdef'


class CoreTokens(unittest.TestCase):
    def test_actual_core_forms_and_json_options_parse_without_executing_html(self):
        for body in ["<form><input value='1' name='"+TOKEN+"' type='hidden'></form>",
                     '<script type="application/json" class="joomla-script-options new">{"csrf.token":"'+TOKEN+'"}</script>']:
            self.assertEqual(cms_sessions.token_from_html(body),TOKEN)
        for body in ['<!-- <form><input value="1" name="'+TOKEN+'" type="hidden"></form> -->',
                     '<script>let sample=\'<form><input type="hidden" name="'+TOKEN+'" value="1"></form>\';</script>',
                     '<form><input name="email"></form>']:
            with self.assertRaises(ValueError):cms_sessions.token_from_html(body)

    def configuration(self):
        return {'sites':{'a'*32:{'names':['example.test','www.example.test'],'installations':[{'cms':'joomla','base':'/','root':'/fixed'}],
                    'origins':{'https':{'type':'tcp','address':'127.0.0.1','port':8080}}}},'query_timeout':30}

    def request(self,**overrides):
        return dict({'schema':1,'op':'token','site':'a'*32,'path':'/el/page?utm_source=actual','cookie':'_ga=own',
                     'host':'www.example.test','scheme':'https','user_agent':'Actual Visitor','client_ip':'192.0.2.45'},**overrides)

    def test_original_headers_context_own_cookies_and_post_request_guest_check(self):
        calls=[];cookie='session=php-created; Expires=Wed, 01 Jan 2030 00:00:00 GMT; Path=/; Secure; HttpOnly'
        def fetch(origin,path,headers,remaining,scheme):
            calls.append((path,headers))
            self.assertGreater(remaining,0)
            return 200,[('Set-Cookie',cookie)],('<form><input type="hidden" value="1" name="'+TOKEN+'"></form>').encode()
        with patch.object(server,'resolve',return_value='guest\tjoomla-guest-session\n') as check:
            answer=server.resolve_token(self.configuration(),self.request(),fetch)
        state,token,fields=answer.rstrip('\n').split('\t')
        self.assertEqual((state,token),('token',TOKEN))
        self.assertEqual(base64.b64decode(fields),('Set-Cookie: '+cookie).encode())
        self.assertIn('lang=el',calls[0][0]);self.assertIn('tmpl=component',calls[0][0])
        self.assertEqual(calls[0][1]['Cookie'],'_ga=own')
        self.assertEqual(calls[0][1]['Host'],'www.example.test')
        self.assertEqual(calls[0][1]['User-Agent'],'Actual Visitor')
        self.assertEqual(calls[0][1]['X-Real-IP'],'192.0.2.45')
        self.assertEqual(calls[0][1]['X-Forwarded-Port'],'443')
        self.assertEqual(check.call_count,2)
        self.assertEqual(check.call_args.args[1]['cookie'],'_ga=own; session=php-created')

    def test_redirects_stay_in_native_hosts_and_detect_loops(self):
        calls=[]
        def fetch(origin,path,headers,remaining,scheme):
            calls.append(headers['Host'])
            if headers['Host']=='www.example.test':return 301,[('Location','https://example.test'+path)],b''
            return 200,[],('<form><input type="hidden" value="1" name="'+TOKEN+'"></form>').encode()
        with patch.object(server,'resolve',return_value='guest\tjoomla-no-session\n'):
            self.assertTrue(server.resolve_token(self.configuration(),self.request(),fetch).startswith('token\t'))
            self.assertEqual(calls,['www.example.test','example.test'])
            for location in ('https://other.test/','https://example.test/index.php?option=com_users&view=login&tmpl=component&lang=el'):
                answer=server.resolve_token(self.configuration(),self.request(host='example.test'),lambda *_:(301,[('Location',location)],b''))
                self.assertEqual(answer,'unresolved\tjoomla-token-unavailable\n')

    def test_auth_transition_unverified_hosts_and_bad_headers_do_not_return_token(self):
        fetch=lambda *_:(200,[],('<form><input type="hidden" value="1" name="'+TOKEN+'"></form>').encode())
        with patch.object(server,'resolve',side_effect=['guest\tjoomla-no-session\n','private\tjoomla-authenticated-session\n']):
            self.assertEqual(server.resolve_token(self.configuration(),self.request(),fetch),'private\tjoomla-authenticated-session\n')
        with patch.object(server,'resolve',return_value='guest\tjoomla-no-session\n'):
            for overrides in ({'host':'other.test'},{'user_agent':'bad\r\nHost: other.test'},{'client_ip':'bad-ip'}):
                with self.subTest(overrides=overrides):
                    self.assertEqual(server.resolve_token(self.configuration(),self.request(**overrides),self.fail),'unresolved\tjoomla-token-unavailable\n')

    def test_unicode_installation_base_uses_same_normalized_route_for_selection_and_redirect(self):
        config=self.configuration()
        config['sites']['a'*32]['installations'][0]['base']='/%CE%B5%CE%BB'
        request=self.request(path='/%ce%b5%ce%bb/page',host='example.test')
        self.assertIsNotNone(server.select_installation(config['sites']['a'*32],request['path']))
        paths=[]
        def fetch(origin,path,headers,remaining,scheme):
            paths.append(path)
            if len(paths)==1:return 301,[('Location','/%ce%b5%ce%bb/index.php?canonical=1')],b''
            return 200,[],('<form><input name="'+TOKEN+'" type="hidden" value="1"></form>').encode()
        with patch.object(server,'resolve',return_value='guest\tjoomla-no-session\n'):
            self.assertTrue(server.resolve_token(config,request,fetch).startswith('token\t'))
        self.assertEqual(len(paths),2)


if __name__=='__main__':unittest.main()
