import unittest
from server.playback import PCMBuffer


class PlaybackTests(unittest.TestCase):
    def test_startup_preserves_first_and_last_samples(self):
        buffer = PCMBuffer()
        pcm = b'\x01\x00\x02\x00\x03\x00'
        buffer.queue.put(pcm[:2])
        buffer.queue.put(pcm[2:])
        buffer.finished = True
        self.assertEqual(buffer.render(6400), bytes(6400))
        self.assertEqual(buffer.render(4), pcm[:4])
        self.assertFalse(buffer.drained)
        self.assertEqual(buffer.render(4), pcm[4:] + bytes(2))
        self.assertTrue(buffer.drained)

    def test_gap_inserts_silence_without_losing_following_words(self):
        buffer = PCMBuffer()
        buffer.warmup = 0
        buffer.queue.put(b'\x01\x00')
        self.assertEqual(buffer.render(4), b'\x01\x00\x00\x00')
        self.assertEqual(buffer.render(4), bytes(4))
        self.assertFalse(buffer.drained)
        buffer.queue.put(b'\x02\x00\x03\x00')
        self.assertEqual(buffer.render(4), b'\x02\x00\x03\x00')
