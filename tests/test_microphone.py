import io
import unittest
from unittest.mock import patch

from server.microphone import MicrophoneError, record_question


class CaptureTests(unittest.TestCase):
    def capture(self, seconds, status=False):
        class FakeStream:
            active = True

            def __init__(self, **options):
                self.callback = options['callback']

            def __enter__(self):
                self.callback(b'\x00\x01' * int(48000 * seconds), 0, None, status)
                return self

            def __exit__(self, *args):
                self.active = False

        with patch('sounddevice.query_devices', return_value={'default_samplerate': 48000}), \
             patch('sounddevice.RawInputStream', FakeStream), \
             patch('server.microphone.select.select', return_value=([True], [], [])):
            return record_question(input_stream=io.StringIO(' '))

    def test_native_audio_is_resampled_to_16k(self):
        pcm = self.capture(0.5)
        self.assertEqual(len(pcm), 16000)

    def test_short_recording_does_not_proceed(self):
        with self.assertRaisesRegex(MicrophoneError, 'too short'):
            self.capture(0.05)

    def test_overflow_does_not_proceed(self):
        with self.assertRaisesRegex(MicrophoneError, 'samples were lost'):
            self.capture(0.5, 'overflow')
