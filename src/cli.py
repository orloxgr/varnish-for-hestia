"""Authenticated native Varnish CLI, without a client-side work deadline."""
import hashlib
import json
import socket
import subprocess


class AuthenticationError(ConnectionError):
    pass


def response(stream):
    header = stream.readline()
    parts = header.split()
    if len(parts) != 2 or not all(value.isdigit() for value in parts):
        raise ConnectionError('Invalid native CLI response')
    status, size = map(int, parts)
    body = stream.read(size)
    if len(body) != size or stream.read(1) != b'\n':
        raise ConnectionError('Incomplete native CLI response')
    return status, body


def command(port, secret_path, args):
    with socket.create_connection(('127.0.0.1', port)) as connection:
        with connection.makefile('rb') as stream:
            status, body = response(stream)
            if status != 107:
                raise AuthenticationError('Native CLI authentication is required')
            challenge = body.split(b'\n', 1)[0]
            if len(challenge) != 32:
                raise ConnectionError('Invalid native CLI challenge')
            secret = secret_path.read_bytes()
            digest = hashlib.sha256(challenge + b'\n' + secret + challenge + b'\n').hexdigest()
            connection.sendall(('auth ' + digest + '\n').encode())
            status, body = response(stream)
            if status != 200:
                raise AuthenticationError('Native CLI authentication failed')
            # Quote each operand; never interpret a caller-supplied CLI command line.
            connection.sendall((' '.join(json.dumps(str(arg), ensure_ascii=True) for arg in args) + '\n').encode())
            status, body = response(stream)
            return subprocess.CompletedProcess(list(args), 0 if status == 200 else 1, stdout=body, stderr=b'')
