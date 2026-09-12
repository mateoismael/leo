import struct
import threading
import time
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient
from fastapi import HTTPException
from server.leov1ser import create_app
from server.recordings import RecordingStore


def decode(data):
    audio = bytearray()
    while data:
        size = struct.unpack('<I', data[:4])[0]
        data = data[4:]
        if size in (0, 0xffffffff):
            return bytes(audio), size, data
        audio.extend(data[:size])
        data = data[size:]
    raise AssertionError('Falta fin explícito')


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.assistant = Mock(model='test')
        self.pcm = b'\x12\x00' * 4096
        self.assistant.prepare_stream.return_value = ('Hola', iter([self.pcm]))
        self.app = create_app(self.assistant)
        self.client = TestClient(self.app)
        self.base = '/audio/recordings/test-0001'

    def upload(self):
        self.assertEqual(self.client.post(self.base + '/start').status_code, 200)
        for seq in range(4):
            self.assertEqual(self.client.post(self.base + f'/chunks/{seq}', content=self.pcm[seq*2048:(seq+1)*2048]).status_code, 200)

    def test_retry_upload_and_response_never_calls_provider_twice(self):
        self.upload()
        self.assertEqual(self.client.post(self.base + '/start').status_code, 200)
        self.assertEqual(self.client.post(self.base + '/chunks/0', content=self.pcm[:2048]).status_code, 200)
        response = self.client.post(self.base + '/end?blocks=4')
        repeated = self.client.post(self.base + '/end?blocks=4')
        self.assertEqual(response.content, repeated.content)
        self.assertEqual(decode(response.content), (self.pcm, 0, b''))
        self.assistant.prepare_stream.assert_called_once_with(self.pcm)

    def test_missing_or_changed_block_is_rejected(self):
        self.upload()
        self.assertEqual(self.client.post(self.base + '/chunks/0', content=b'\x01\x00').status_code, 409)
        self.assertEqual(self.client.post(self.base + '/chunks/5', content=b'\x01\x00').status_code, 409)
        self.assertEqual(self.client.post(self.base + '/end?blocks=5').status_code, 400)
        self.assistant.prepare_stream.assert_not_called()

    def test_failed_generation_is_cached_and_marked(self):
        self.upload()
        self.assistant.prepare_stream.side_effect = RuntimeError('fake API failure')
        for _ in range(2):
            result = self.client.post(self.base + '/end?blocks=4')
            self.assertEqual(decode(result.content), (b'', 0xffffffff, b''))
        self.assistant.prepare_stream.assert_called_once()

    def test_disconnected_reader_does_not_cancel_generation(self):
        release = threading.Event()
        started = threading.Event()
        def source():
            yield self.pcm[:2048]
            started.set()
            if not release.wait(3):
                raise RuntimeError('test timeout')
            yield self.pcm[2048:]
        self.assistant.prepare_stream.return_value = ('Hola', source())
        self.upload()
        store = self.app.state.recordings
        job = store.end('test-0001', 4)
        reader = store.read(job)
        next(reader)
        reader.close()
        self.assertTrue(started.wait(1))
        self.assertIs(store.end('test-0001', 4), job)
        release.set()
        recovered = b''.join(store.read(job))
        self.assertEqual(decode(recovered), (self.pcm, 0, b''))
        self.assistant.prepare_stream.assert_called_once()

    def test_expiry_and_capacity_bound_memory(self):
        store = RecordingStore(self.assistant, threading.Lock(), ttl=1, capacity=1)
        store.start('test-0001')
        with self.assertRaises(HTTPException) as error:
            store.start('test-0002')
        self.assertEqual(error.exception.status_code, 429)
        store.jobs['test-0001'].updated = time.monotonic() - 2
        with self.assertRaises(HTTPException) as error:
            store.end('test-0001', 0)
        self.assertEqual(error.exception.status_code, 404)
        store.start('test-0002')

    def test_abort_never_uses_api(self):
        self.upload()
        self.assertEqual(self.client.post(self.base + '/abort').status_code, 200)
        self.assertNotEqual(self.client.post(self.base + '/end?blocks=4').status_code, 200)
        self.assistant.prepare_stream.assert_not_called()
