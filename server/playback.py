"""Salida PCM que conserva las muestras durante el arranque y las pausas."""
import queue
import threading


class PCMBuffer:
    def __init__(self, rate=16000):
        self.queue = queue.Queue(maxsize=64)
        self.pending = b''
        self.offset = 0
        self.warmup = int(rate * 0.2) * 2
        self.finished = False
        self.underflows = 0
        self.drained = False

    def render(self, size):
        result = bytearray(size)
        cursor = min(size, self.warmup)
        self.warmup -= cursor
        while cursor < size:
            if self.offset == len(self.pending):
                try:
                    self.pending = self.queue.get_nowait()
                    self.offset = 0
                except queue.Empty:
                    if self.finished:
                        self.drained = True
                    break
            length = min(size - cursor, len(self.pending) - self.offset)
            result[cursor:cursor + length] = self.pending[self.offset:self.offset + length]
            cursor += length
            self.offset += length
        return bytes(result)


class PCMPlayer:
    def __init__(self, rate=16000):
        self.buffer = PCMBuffer(rate)
        self.rate = rate
        self.done = threading.Event()
        self.stream = None

    def __enter__(self):
        import sounddevice as sd

        def callback(outdata, frames, timing, status):
            if status.output_underflow:
                self.buffer.underflows += 1
            outdata[:] = self.buffer.render(frames * 2)
            if self.buffer.drained:
                raise sd.CallbackStop

        self.stream = sd.RawOutputStream(
            samplerate=self.rate, channels=1, dtype='int16',
            blocksize=1024, latency='high', callback=callback,
            finished_callback=self.done.set,
        )
        try:
            self.stream.start()
        except BaseException:
            self.stream.close()
            raise
        return self

    def write(self, chunk):
        if len(chunk) % 2:
            raise ValueError('Fragmento PCM incompleto.')
        if not chunk:
            return
        while True:
            if not self.stream.active:
                raise RuntimeError('La salida de audio se detuvo.')
            try:
                self.buffer.queue.put(chunk, timeout=0.1)
                return
            except queue.Full:
                pass

    def finish(self):
        self.buffer.finished = True
        if not self.done.wait(timeout=90):
            raise RuntimeError('La reproducción agotó el tiempo de espera.')

    def __exit__(self, *args):
        self.stream.abort()
        self.stream.close()
