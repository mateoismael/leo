"""Protocol v2: idempotent chunks and an in-memory recoverable result."""
import re
import struct
import threading
import time
from dataclasses import dataclass, field

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

MAX_PCM = 16000 * 2 * 60
FRAME_TYPE = 'pcm-s16le-framed-v1'


@dataclass
class Recording:
    pcm: bytearray = field(default_factory=bytearray)
    blocks: list = field(default_factory=list)
    frames: list = field(default_factory=list)
    state: str = 'uploading'
    updated: float = field(default_factory=time.monotonic)
    condition: threading.Condition = field(default_factory=threading.Condition)


class RecordingStore:
    def __init__(self, assistant, pipeline_lock, ttl=300, capacity=4):
        self.assistant = assistant
        self.pipeline_lock = pipeline_lock
        self.ttl = ttl
        self.capacity = capacity
        self.jobs = {}
        self.lock = threading.Lock()

    def prune(self):
        now = time.monotonic()
        for key, job in list(self.jobs.items()):
            if job.state != 'processing' and now - job.updated > self.ttl:
                del self.jobs[key]

    def get(self, key):
        self.prune()
        if key not in self.jobs:
            raise HTTPException(404, 'Recording missing or expired; it is not regenerated.')
        return self.jobs[key]

    def start(self, key):
        if not re.fullmatch(r'[a-zA-Z0-9-]{8,80}', key):
            raise HTTPException(400, 'Invalid identifier.')
        with self.lock:
            self.prune()
            if key in self.jobs:
                return
            if len(self.jobs) >= self.capacity:
                completed = [(job.updated, key) for key, job in self.jobs.items()
                             if job.state in ('done', 'failed', 'aborted')]
                if not completed:
                    raise HTTPException(429, 'Cache full; wait for recordings to expire.')
                del self.jobs[min(completed)[1]]
            self.jobs[key] = Recording()

    def append(self, key, seq, body):
        if not body or len(body) > 2048 or len(body) % 2 or seq < 0:
            raise HTTPException(400, 'Invalid PCM chunk.')
        with self.lock:
            job = self.get(key)
            if job.state != 'uploading':
                raise HTTPException(409, 'The recording is already closed.')
            if seq < len(job.blocks):
                start, length = job.blocks[seq]
                if job.pcm[start:start + length] != body:
                    raise HTTPException(409, 'The repeated chunk changed content.')
            elif seq == len(job.blocks):
                if len(job.pcm) + len(body) > MAX_PCM:
                    raise HTTPException(413, 'Recording too long.')
                job.blocks.append((len(job.pcm), len(body)))
                job.pcm.extend(body)
            else:
                raise HTTPException(409, 'Faltan bloques anteriores.')
            job.updated = time.monotonic()

    def end(self, key, block_count):
        with self.lock:
            job = self.get(key)
            if block_count != len(job.blocks) or len(job.pcm) < 6400:
                raise HTTPException(400, 'Recording incomplete or too short.')
            if job.state == 'uploading':
                if not self.pipeline_lock.acquire(blocking=False):
                    raise HTTPException(409, 'Asistente ocupado; reintenta el mismo ID.')
                job.state = 'processing'
                try:
                    threading.Thread(target=self.produce, args=(job,), daemon=True).start()
                except BaseException:
                    job.state = 'uploading'
                    self.pipeline_lock.release()
                    raise
            elif job.state == 'aborted':
                raise HTTPException(409, 'Recording cancelled.')
            # Repeating end attaches to the same result, even after an error.
            return job

    def abort(self, key):
        with self.lock:
            job = self.get(key)
            if job.state == 'uploading':
                job.state = 'aborted'
                job.pcm.clear()
                job.updated = time.monotonic()

    def produce(self, job):
        source = None
        terminal = 0xffffffff
        try:
            _, source = self.assistant.prepare_stream(bytes(job.pcm))
            total = 0
            for chunk in source:
                if len(chunk) % 2:
                    raise ValueError('PCM incompleto')
                total += len(chunk)
                if total > MAX_PCM:
                    raise ValueError('Respuesta demasiado larga')
                for offset in range(0, len(chunk), 2048):
                    part = chunk[offset:offset + 2048]
                    with job.condition:
                        job.frames.append(struct.pack('<I', len(part)) + part)
                        job.condition.notify_all()
            if total:
                terminal = 0
        except Exception:
            # Never send provider details or credentials to the device.
            pass
        finally:
            try:
                if source is not None and hasattr(source, 'close'):
                    source.close()
            finally:
                with self.lock, job.condition:
                    job.frames.append(struct.pack('<I', terminal))
                    job.state = 'done' if terminal == 0 else 'failed'
                    job.updated = time.monotonic()
                    job.condition.notify_all()
                self.pipeline_lock.release()

    @staticmethod
    def read(job):
        index = 0
        deadline = time.monotonic() + 180
        while True:
            with job.condition:
                while index == len(job.frames) and job.state == 'processing':
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    job.condition.wait(min(remaining, 1))
                if index < len(job.frames):
                    frame = job.frames[index]
                    index += 1
                elif job.state == 'processing':
                    frame = struct.pack('<I', 0xffffffff)
                else:
                    return
            # Never hold the cache lock while sending over the network.
            yield frame
            if frame == struct.pack('<I', 0xffffffff):
                return


def install_recording_routes(app, assistant, pipeline_lock):
    store = RecordingStore(assistant, pipeline_lock)
    app.state.recordings = store

    @app.post('/audio/recordings/{key}/start')
    def start(key: str):
        store.start(key)
        return {'status': 'ok'}

    @app.post('/audio/recordings/{key}/chunks/{seq}')
    async def chunk(key: str, seq: int, request: Request):
        body = bytearray()
        async for part in request.stream():
            body.extend(part)
            if len(body) > 2048:
                raise HTTPException(413, 'Bloque demasiado grande.')
        store.append(key, seq, body)
        return {'status': 'ok', 'sequence': seq}

    @app.post('/audio/recordings/{key}/end')
    def end(key: str, blocks: int):
        job = store.end(key, blocks)
        return StreamingResponse(store.read(job), media_type='application/octet-stream', headers={
            'Connection': 'close', 'Cache-Control': 'no-store', 'X-Audio-Format': FRAME_TYPE,
        })

    @app.post('/audio/recordings/{key}/abort')
    def abort(key: str):
        store.abort(key)
        return {'status': 'aborted'}
