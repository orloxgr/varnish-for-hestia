"""Opt-in disposable-host test of generated Nginx/Varnish with slow real origins.

Uses isolated processes and ephemeral ports. Does not edit hosting services.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import browser_cache
import hosting_timeouts
from registry import desired_state
from vcl import render

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--disposable', action='store_true', required=True)
parser.add_argument('--delay', type=float, default=65)
args = parser.parse_args()
if os.geteuid() != 0 or args.delay <= 0: parser.error('Use root and a positive delay on a disposable Linux host')
counts = Counter()
class Origin(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *args): pass
    def do_GET(self): self.respond()
    def do_POST(self): self.respond()
    def respond(self):
        data = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        counts[(self.command, self.path)] += 1
        if self.path.startswith('/slow'): time.sleep(args.delay)
        body = (self.command + ':' + self.path + ':' + data.decode()).encode()
        self.send_response(200)
        for key, value in [('Content-Type', 'text/plain'), ('Content-Length', str(len(body))), ('Cache-Control', 'public, max-age=300')]: self.send_header(key, value)
        self.end_headers()
        if self.path == '/stream':
            self.wfile.write(body[:1]); self.wfile.flush(); time.sleep(2); self.wfile.write(body[1:])
        else: self.wfile.write(body)
def port():
    with socket.socket() as sock: sock.bind(('127.0.0.1', 0)); return sock.getsockname()[1]
def ready(number, process):
    start = time.monotonic()
    while True:
        if process.poll() is not None: raise RuntimeError('Isolated test process failed')
        try:
            with socket.create_connection(('127.0.0.1', number), timeout=.2): return
        except OSError:
            if time.monotonic() - start > 20: raise RuntimeError('Test listener failed to start')
            time.sleep(.05)
origin = ThreadingHTTPServer(('127.0.0.1', 0), Origin)
threading.Thread(target=origin.serve_forever, daemon=True).start()
processes = []
try:
    with tempfile.TemporaryDirectory(prefix='hvh-timeouts-') as folder:
        root = Path(folder); root.chmod(0o755)
        inventory = {'alice': dict(identity='fixture', package='default', role='user', suspended=False, sites={'example.test': dict(aliases=[], suspended=False)})}
        state = desired_state(None, inventory, 'varnish'); hosting_timeouts.refresh(state)
        site = state['owners']['alice']['sites']['example.test']
        front, cache, admin = port(), port(), port()
        (root / 'active.vcl').write_text(render(state, dict(origin_ip='127.0.0.1', origin_port=origin.server_port)))
        with (root / 'varnish.log').open('w') as log:
            process = subprocess.Popen(['varnishd', '-j', 'none', '-F', '-a', '127.0.0.1:' + str(cache), '-T', '127.0.0.1:' + str(admin), '-f', str(root / 'active.vcl'), '-n', str(root / 'cache'), '-s', 'malloc,32m', '-p', 'first_byte_timeout=1', '-p', 'between_bytes_timeout=1', '-p', 'idle_send_timeout=1', '-p', 'send_timeout=1'], stdout=log, stderr=log, start_new_session=True)
        processes.append(process); ready(cache, process)
        template = (Path(__file__).resolve().parents[1] / 'templates/hvh-varnish.tpl').read_text()
        template = browser_cache.template(hosting_timeouts.template(template, state), site, state, 'tpl')
        replacements = {'%ip%': '127.0.0.1', '%proxy_port%': str(front), '%web_port%': str(origin.server_port), '%home%': str(root), '%user%': 'alice', '%domain_idn%': 'example.test', '%domain%': 'example.test', '%alias_idn%': '', '%web_system%': 'apache2', '%docroot%': str(root), '%proxy_extensions%': 'css'}
        for key, value in replacements.items(): template = template.replace(key, value)
        template = template.replace('/var/log/apache2/domains/', str(root) + '/')
        template = template.replace('127.0.0.1:6081', '127.0.0.1:' + str(cache))
        config = root / 'nginx.conf'
        config.write_text('pid ' + str(root / 'nginx.pid') + ';\nerror_log ' + str(root / 'nginx.log') + ';\nevents {}\nhttp { log_format bytes "$bytes_sent"; access_log off; map $request_method $rfc_early_data { default ""; }\n' + template + '\n}')
        checked = subprocess.run(['nginx', '-t', '-p', str(root), '-c', str(config)], capture_output=True, text=True)
        if checked.returncode: raise RuntimeError(checked.stderr)
        with (root / 'nginx-start.log').open('w') as log:
            process = subprocess.Popen(['nginx', '-p', str(root), '-c', str(config), '-g', 'daemon off;'], stdout=log, stderr=log, start_new_session=True)
        processes.append(process); ready(front, process)
        def request(path, method='GET'):
            start = time.monotonic(); conn = http.client.HTTPConnection('127.0.0.1', front, timeout=args.delay + 60)
            conn.request(method, path, body=b'once' if method == 'POST' else None, headers={'Host': 'example.test'})
            response = conn.getresponse(); body = response.read(); conn.close()
            assert response.status == 200 and body == (method + ':' + path + ':' + ('once' if method == 'POST' else '')).encode()
            return dict(path=path, method=method, seconds=round(time.monotonic() - start, 3), cache=response.getheader('X-Hestia-Varnish'))
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(request, '/slow-get'), pool.submit(request, '/slow-post', 'POST'), pool.submit(request, '/stream')]
            results = [future.result() for future in futures]
        warm = request('/slow-get')
        assert warm['cache'] == 'HIT' and counts[('GET', '/slow-get')] == counts[('POST', '/slow-post')] == 1
        print(json.dumps(dict(results=results, warm=warm, single_post=True, hosting_timeouts=state['hosting_timeouts']), indent=2))
finally:
    for process in reversed(processes):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: os.killpg(process.pid, signal.SIGKILL); process.wait()
    origin.shutdown(); origin.server_close()
