"""Discarded fetches and disconnected clients must not retain cookie fields."""
import shutil
import socket
import threading
import time
import unittest

from test_cookie_delivery import proxy,cookies


def pending(source):
    return source.replace(' call scp_deliver;',
        ' call scp_deliver; set resp.http.X-Test-Pending = cookie_handoff.pending();')


@unittest.skipUnless(shutil.which('varnishd'),'Native Varnish required')
class HandoffLifecycle(unittest.TestCase):
    def test_backend_error_discards_detached_fields(self):
        def origin(path,headers):
            return 'origin',[('Cache-Control','public, max-age=120'),('Set-Cookie','_fbp=discarded; Path=/')]
        def error(source):
            return pending(source).replace('sub vcl_backend_response {','''sub vcl_backend_response {
 if (bereq.url == "/backend-error") {
   call scp_backend_response; return (error(503, "Discarded response"));
 }
''')
        for profile in ('basic','ultracache'):
            with self.subTest(profile=profile),proxy(profile,origin,transform=error) as get:
                status,fields,_=get('/backend-error')
                self.assertEqual(status,503)
                self.assertEqual(cookies(fields),[])

    def test_background_fill_cannot_issue_cookies_to_the_stale_or_next_hit(self):
        for profile in ('basic','ultracache'):
            calls=[]
            def origin(path,headers):
                calls.append(path)
                return str(len(calls)),[('Cache-Control','public, max-age=120'),('Set-Cookie','_fbp=origin-'+str(len(calls))+'; Path=/')]
            def grace(source):
                return pending(source).replace('  return (deliver);\n}\nsub vcl_backend_error',
                    '  set beresp.ttl = 0.3s; set beresp.grace = 60s; return (deliver);\n}\nsub vcl_backend_error')
            with self.subTest(profile=profile),proxy(profile,origin,transform=grace) as get:
                _,fields,body=get('/background')
                self.assertEqual(body,'1');self.assertEqual(len(cookies(fields)),1)
                time.sleep(.4)
                _,fields,_=get('/background')
                self.assertEqual(dict(fields)['X-Cache'],'HIT');self.assertEqual(cookies(fields),[])
                for _ in range(30):
                    time.sleep(.02)
                    _,fields,body=get('/background')
                    self.assertEqual(cookies(fields),[])
                    if body=='2':break
                self.assertEqual(body,'2')
                self.assertEqual(dict(fields)['X-Test-Pending'],'0')

    def test_client_restart_to_a_warmed_hit_discards_the_old_response_cookies(self):
        for profile in ('basic','ultracache'):
            def origin(path,headers):
                return path,[('Cache-Control','public, max-age=120')]+(
                    [('Set-Cookie','_fbp=discarded; Path=/')] if path=='/discard' else [])
            def restart(source):
                return pending(source).replace('sub vcl_deliver {','''sub vcl_deliver {
 if (req.url == "/discard" && req.restarts == 0) {
   set req.url = "/prime";
   return (restart);
 }
''')
            with self.subTest(profile=profile),proxy(profile,origin,transform=restart) as get:
                get('/prime')
                _,fields,body=get('/discard')
                self.assertEqual(body,'/prime');self.assertEqual(dict(fields)['X-Cache'],'HIT')
                self.assertEqual(cookies(fields),[])
                _,fields,_=get('/prime');self.assertEqual(dict(fields)['X-Test-Pending'],'0')

    def test_backend_retry_does_not_deliver_the_discarded_attempts_cookie(self):
        for profile in ('basic','ultracache'):
            calls=[]
            def origin(path,headers):
                calls.append(path)
                return 'final',[('Cache-Control','public, max-age=120')]+(
                    [('Set-Cookie','_fbp=discarded; Path=/')] if len(calls)==1 else [])
            def retry(source):
                return pending(source).replace('sub vcl_backend_response {','''sub vcl_backend_response {
 if (bereq.url == "/retry" && bereq.retries == 0) {
   call scp_backend_response; return (retry);
 }
''')
            with self.subTest(profile=profile),proxy(profile,origin,transform=retry) as get:
                _,fields,body=get('/retry')
                self.assertEqual(body,'final');self.assertEqual(calls,['/retry','/retry'])
                self.assertEqual(cookies(fields),[])
                _,fields,_=get('/retry');self.assertEqual(dict(fields)['X-Cache'],'HIT')
                self.assertEqual(dict(fields)['X-Test-Pending'],'0')

    def test_disconnect_before_origin_response_releases_the_client_owned_entry(self):
        started=threading.Event();finish=threading.Event();completed=threading.Event()
        def origin(path,headers):
            if path=='/abort':
                started.set();finish.wait(5);completed.set()
                return 'aborted',[('Cache-Control','public, max-age=120'),('Set-Cookie','_fbp=aborted-client; Path=/')]
            return 'probe',[('Cache-Control','public, max-age=120')]
        with proxy('basic',origin,transform=pending) as get:
            get('/probe')
            with socket.create_connection(get.endpoint) as connection:
                connection.sendall(b'GET /abort HTTP/1.1\r\nHost: example.test\r\nConnection: close\r\n\r\n')
                self.assertTrue(started.wait(5))
            finish.set();self.assertTrue(completed.wait(5))
            for _ in range(100):
                _,fields,_=get('/probe')
                self.assertEqual(cookies(fields),[])
                if dict(fields)['X-Test-Pending']=='0':break
                time.sleep(.02)
            self.assertEqual(dict(fields)['X-Test-Pending'],'0')


if __name__=='__main__':unittest.main()
