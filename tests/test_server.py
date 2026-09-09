import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch
import wave

from fastapi.testclient import TestClient
from server.leov1ser import VoiceAssistant, PipelineError, pcm_to_wav, create_app, MAX_BYTES


class ServerTests(unittest.TestCase):
    def test_question_once_and_history_only_after_success(self):
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='Hola.'))])
        assistant = VoiceAssistant(client)
        self.assertEqual(assistant.answer('Pregunta'), 'Hola.')
        messages = client.chat.completions.create.call_args.kwargs['messages']
        self.assertEqual(sum(m['content'] == 'Pregunta' for m in messages), 1)
        before = assistant.history.copy()
        client.chat.completions.create.side_effect = RuntimeError('fallo externo')
        with self.assertRaises(PipelineError):
            assistant.answer('Segunda pregunta')
        self.assertEqual(assistant.history, before)

    def test_nano_omits_unsupported_temperature(self):
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='Bien.'))])
        with patch.dict('os.environ', {'LLM_PROVIDER': 'openai', 'OPENAI_MODEL': 'gpt-5-nano'}):
            VoiceAssistant(client).answer('Hola')
        options = client.chat.completions.create.call_args.kwargs
        self.assertNotIn('temperature', options)
        self.assertNotIn('max_tokens', options)
        self.assertEqual(options['reasoning_effort'], 'minimal')

    def test_openrouter_requires_its_own_key(self):
        with patch.dict('os.environ', {'LLM_PROVIDER': 'openrouter', 'OPENROUTER_MODEL': 'test/model',
                                      'OPENAI_API_KEY': 'test-only', 'OPENROUTER_API_KEY': ''}):
            with self.assertRaisesRegex(PipelineError, 'OPENROUTER_API_KEY'):
                VoiceAssistant().answer('Hola')

    def test_pcm_is_canonical_wav(self):
        pcm = b'\x00\x00' * 16000
        data = pcm_to_wav(pcm)
        self.assertEqual(data[36:40], b'data')
        self.assertEqual(data[44:], pcm)
        with wave.open(BytesIO(data), 'rb') as wav:
            self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate()), (1, 2, 16000))

    def test_old_firmware_protocol_returns_audio(self):
        fake = Mock(model='test')
        pcm = b'\x01\x00' * 16000
        wav = pcm_to_wav(pcm)
        fake.process.return_value = (wav, {})
        with TestClient(create_app(fake)) as client:
            for offset in range(0, len(pcm), 2048):
                self.assertEqual(client.post('/audio', content=pcm[offset:offset+2048]).status_code, 200)
            result = client.post('/audio', headers={'Recording-Status': 'end'})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.headers['content-type'], 'audio/wav')
            self.assertEqual(result.content, wav)
            fake.process.assert_called_once_with(pcm)
            self.assertEqual(client.post('/audio', headers={'Recording-Status': 'end'}).status_code, 400)

    def test_processing_failure_is_not_200_audio(self):
        fake = Mock(model='test')
        fake.process.side_effect = PipelineError('Error de prueba')
        with TestClient(create_app(fake)) as client:
            client.post('/audio', content=b'\x00\x00' * 16000)
            result = client.post('/audio', headers={'Recording-Status': 'end'})
            self.assertEqual(result.status_code, 502)
            self.assertEqual(result.headers['content-type'], 'application/json')

    def test_bad_or_oversized_audio_rejected(self):
        fake = Mock(model='test')
        with TestClient(create_app(fake)) as client:
            self.assertEqual(client.post('/audio', content=b'x').status_code, 400)
            self.assertEqual(client.post('/audio', content=b'x' * (MAX_BYTES + 1)).status_code, 413)
            self.assertEqual(client.post('/audio', headers={'Recording-Status': 'end'}).status_code, 400)
            fake.process.assert_not_called()

    def test_health_does_not_call_models(self):
        fake = Mock(model='test')
        with TestClient(create_app(fake)) as client:
            self.assertEqual(client.get('/health').json()['status'], 'ok')
            fake.process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
