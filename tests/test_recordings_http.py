"""Recovery over real TCP; providers stubbed, no external calls."""
import http.client
import socket
import struct
import threading
import time
import unittest
from unittest.mock import Mock

import uvicorn
from server.app import create_app


class RealHTTPTests(unittest.TestCase):
    def test_http10_disconnect_then_recover_same_generation(self):
        release = threading.Event()
        def chunks():
            yield b'\x01\x00' * 1024
            if not release.wait(5):
                raise RuntimeError('timeout de prueba')
            yield b'\x02\x00' * 1024
        assistant = Mock(model='fake')
        assistant.prepare_stream.return_value = ('Hola', chunks())
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(create_app(assistant), log_level='critical'))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        thread.start()
        connections = []
        def post(path, body=b''):
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            connection._http_vsn = 10
            connection._http_vsn_str = 'HTTP/1.0'
            connections.append(connection)
            connection.request('POST', path, body)
            return connection, connection.getresponse()
        try:
            deadline = time.monotonic() + 5
            while not server.started:
                if time.monotonic() > deadline:
                    self.fail('Local server did not start')
                time.sleep(0.01)
            base = '/audio/recordings/http-0001'
            _, r = post(base + '/start')
            self.assertEqual(r.status, 200)
            r.read()
            for i in range(4):
                _, r = post(base + f'/chunks/{i}', b'\0\0' * 1024)
                self.assertEqual(r.status, 200)
                r.read()
            first, r = post(base + '/end?blocks=4')
            self.assertIsNone(r.getheader('Transfer-Encoding'))
            self.assertEqual(r.getheader('X-Audio-Format'), 'pcm-s16le-framed-v1')
            self.assertEqual(r.read(4), struct.pack('<I', 2048))
            self.assertEqual(r.read(2048), b'\x01\x00' * 1024)
            r.close()
            first.close()
            _, busy = post('/audio', b'\0\0')
            self.assertEqual(busy.status, 409)
            busy.read()
            release.set()
            _, retry = post(base + '/end?blocks=4')
            expected = struct.pack('<I', 2048) + b'\x01\x00' * 1024
            expected += struct.pack('<I', 2048) + b'\x02\x00' * 1024 + bytes(4)
            self.assertEqual(retry.read(), expected)
            assistant.prepare_stream.assert_called_once()
        finally:
            release.set()
            for connection in connections:
                connection.close()
            server.should_exit = True
            thread.join(5)
            sock.close()
