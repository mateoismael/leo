"""Asistente de voz: Whisper local, respuesta por API y voz con gTTS."""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
RATE = 16000
MAX_SECONDS = 60
MAX_BYTES = RATE * 2 * MAX_SECONDS


class PipelineError(Exception):
    pass


def pcm_to_wav(pcm):
    if len(pcm) % 2 or not RATE * 2 * 0.2 <= len(pcm) <= MAX_BYTES:
        raise ValueError('Se requiere PCM16 mono de 16 kHz, entre 0.2 y 60 segundos.')
    output = BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(pcm)
    return output.getvalue()


def read_wav(path):
    with wave.open(str(path), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, RATE, 'NONE'):
            raise ValueError('El archivo debe ser WAV PCM16 mono a 16000 Hz.')
        if wav.getnframes() > RATE * MAX_SECONDS:
            raise ValueError('La grabación supera 60 segundos.')
        pcm = wav.readframes(wav.getnframes())
    pcm_to_wav(pcm)
    return pcm


class VoiceAssistant:
    def __init__(self, client=None):
        self.client = client
        self.whisper = None
        self.history = []
        self.provider = os.getenv('LLM_PROVIDER', 'openai').strip()
        if self.provider not in ('openai', 'openrouter'):
            raise ValueError('LLM_PROVIDER debe ser openai u openrouter.')
        self.model = os.getenv('OPENAI_MODEL', 'gpt-5-nano') if self.provider == 'openai' else os.getenv('OPENROUTER_MODEL', '')
        self.usage = {}

    def answer(self, text):
        text = text.strip()
        if not text or len(text) > 4000:
            raise ValueError('La pregunta debe contener entre 1 y 4000 caracteres.')
        if self.client is None:
            key_name = 'OPENAI_API_KEY' if self.provider == 'openai' else 'OPENROUTER_API_KEY'
            key = os.getenv(key_name, '').strip()
            if not key:
                raise PipelineError(f'Falta {key_name} en el archivo .env de la raíz.')
            from openai import OpenAI
            base_url = 'https://api.openai.com/v1' if self.provider == 'openai' else 'https://openrouter.ai/api/v1'
            self.client = OpenAI(api_key=key, base_url=base_url, timeout=60.0, max_retries=0)
        if not self.model:
            raise PipelineError('Configura el identificador del modelo del proveedor en .env.')
        messages = [
            {'role': 'system', 'content': 'Responde en español para un asistente de voz. Usa como máximo 50 palabras, frases completas y sin formato Markdown.'},
            *self.history[-10:],
            {'role': 'user', 'content': text},
        ]
        try:
            options = {'model': self.model, 'messages': messages}
            if self.provider == 'openai' and self.model.startswith('gpt-5'):
                effort = 'minimal' if self.model.startswith('gpt-5-nano') else 'none'
                options.update(max_completion_tokens=1024, reasoning_effort=effort)
            else:
                options.update(max_tokens=180, temperature=0.5)
            result = self.client.chat.completions.create(**options)
        except Exception as exc:
            raise PipelineError('La API no respondió correctamente. Comprueba clave, acceso al modelo y conexión.') from exc
        usage = getattr(result, 'usage', None)
        self.usage = usage.model_dump() if usage is not None and hasattr(usage, 'model_dump') else {}
        answer = (result.choices[0].message.content or '').strip()
        if not answer:
            raise PipelineError('La API devolvió una respuesta vacía.')
        self.history = (self.history + [
            {'role': 'user', 'content': text}, {'role': 'assistant', 'content': answer},
        ])[-10:]
        return answer

    def transcribe(self, wav_path):
        if self.whisper is None:
            try:
                import whisper
            except ImportError as exc:
                raise PipelineError('Instala server/requirements-audio.in para usar Whisper.') from exc
            self.whisper = whisper.load_model(os.getenv('WHISPER_MODEL', 'base'))
        text = self.whisper.transcribe(str(wav_path), language='es', fp16=False)['text'].strip()
        if not text:
            raise PipelineError('No se detectó voz reconocible en la grabación.')
        return text

    def speak(self, text):
        if not shutil.which('ffmpeg'):
            raise PipelineError('FFmpeg no está disponible en PATH.')
        provider = os.getenv('TTS_PROVIDER', 'gtts').strip().lower()
        if provider not in ('chatterbox', 'gtts'):
            raise PipelineError('TTS_PROVIDER debe ser chatterbox o gtts.')
        try:
            if provider == 'chatterbox':
                python = os.getenv('CHATTERBOX_PYTHON', '').strip()
                if not python or not Path(python).is_file():
                    raise PipelineError('Configura CHATTERBOX_PYTHON con el Python del entorno Chatterbox.')
                with tempfile.TemporaryDirectory(prefix='pulsera-tts-') as folder:
                    raw_wav = Path(folder) / 'chatterbox.wav'
                    command = [python, str(ROOT / 'server/tts_chatterbox.py'),
                               '--text', text, '--output', str(raw_wav)]
                    reference = os.getenv('CHATTERBOX_REFERENCE', '').strip()
                    if reference:
                        command.extend(['--reference', reference])
                    env = os.environ.copy()
                    cache = ROOT / '.cache/numba'
                    cache.mkdir(parents=True, exist_ok=True)
                    env['NUMBA_CACHE_DIR'] = str(cache)
                    subprocess.run(command, capture_output=True, timeout=300,
                                   check=True, env=env)
                    result = subprocess.run([
                        'ffmpeg', '-v', 'error', '-i', str(raw_wav), '-f', 's16le',
                        '-acodec', 'pcm_s16le', '-ar', str(RATE), '-ac', '1', 'pipe:1',
                    ], capture_output=True, timeout=60, check=True)
            else:
                from gtts import gTTS
                mp3 = BytesIO()
                gTTS(text=text, lang='es', timeout=30).write_to_fp(mp3)
                result = subprocess.run([
                    'ffmpeg', '-v', 'error', '-i', 'pipe:0', '-f', 's16le',
                    '-acodec', 'pcm_s16le', '-ar', str(RATE), '-ac', '1', 'pipe:1',
                ], input=mp3.getvalue(), capture_output=True, timeout=60, check=True)
        except subprocess.TimeoutExpired as exc:
            raise PipelineError(f'La generación de voz con {provider} agotó el tiempo.') from exc
        except subprocess.CalledProcessError as exc:
            raise PipelineError(f'La generación de voz con {provider} falló.') from exc
        return pcm_to_wav(result.stdout)

    def process(self, pcm):
        wav = pcm_to_wav(pcm)
        timings = {}
        with tempfile.TemporaryDirectory(prefix='pulsera-') as folder:
            path = Path(folder) / 'entrada.wav'
            path.write_bytes(wav)
            start = time.perf_counter()
            text = self.transcribe(path)
            timings['transcripcion'] = round(time.perf_counter() - start, 3)
        start = time.perf_counter()
        answer = self.answer(text)
        timings['api'] = round(time.perf_counter() - start, 3)
        start = time.perf_counter()
        audio = self.speak(answer)
        timings['voz'] = round(time.perf_counter() - start, 3)
        return audio, {'transcripcion': text, 'respuesta': answer, 'segundos': timings, 'uso_api': self.usage}


def create_app(assistant=None):
    app = FastAPI(title='Pulsera de voz — desarrollo local')
    assistant = assistant or VoiceAssistant()
    buffer = bytearray()
    lock = threading.Lock()

    @app.get('/health')
    def health():
        return {'status': 'ok', 'modo': 'api', 'modelo': assistant.model}

    @app.post('/audio')
    async def audio(request: Request):
        # Compatibilidad de un único dispositivo con el firmware recuperado.
        if not lock.acquire(blocking=False):
            raise HTTPException(409, 'Hay una grabación en procesamiento.')
        try:
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_BYTES:
                    buffer.clear()
                    raise HTTPException(413, 'Audio demasiado grande.')
                body.extend(chunk)
            if request.headers.get('Recording-Status') == 'end':
                if body:
                    raise HTTPException(400, 'La petición final debe tener cuerpo vacío.')
                pcm = bytes(buffer)
                buffer.clear()
                try:
                    pcm_to_wav(pcm)
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
                try:
                    wav, _ = await run_in_threadpool(assistant.process, pcm)
                except PipelineError as exc:
                    raise HTTPException(502, str(exc)) from exc
                except Exception as exc:
                    raise HTTPException(502, 'No se pudo procesar el audio.') from exc
                return Response(wav, media_type='audio/wav', headers={
                    'Connection': 'close', 'Cache-Control': 'no-store',
                })
            if len(body) % 2:
                raise HTTPException(400, 'El bloque PCM debe contener muestras completas de 16 bits.')
            if len(buffer) + len(body) > MAX_BYTES:
                buffer.clear()
                raise HTTPException(413, 'La grabación supera 60 segundos; buffer reiniciado.')
            buffer.extend(body)
            return {'status': 'ok'}
        finally:
            lock.release()

    return app


app = create_app()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Revisar entorno sin llamadas externas')
    mode.add_argument('--text', help='Probar solamente la respuesta por API')
    mode.add_argument('--audio', type=Path, help='Procesar un WAV PCM16 mono a 16 kHz sin ESP32')
    parser.add_argument('--output', type=Path, default=ROOT / 'recordings/respuesta.wav')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if args.check:
        checks = {
            'api_key_configurada': bool(os.getenv('OPENROUTER_API_KEY' if os.getenv('LLM_PROVIDER') == 'openrouter' else 'OPENAI_API_KEY', '').strip()),
            'ffmpeg_disponible': bool(shutil.which('ffmpeg')),
            'whisper_instalado': importlib.util.find_spec('whisper') is not None,
            'modelo_api': VoiceAssistant().model,
            'tts': os.getenv('TTS_PROVIDER', 'gtts'),
            'chatterbox_disponible': Path(os.getenv('CHATTERBOX_PYTHON', '')).is_file(),
        }
        print(json.dumps(checks, ensure_ascii=False, indent=2))
        required = ('api_key_configurada', 'ffmpeg_disponible', 'whisper_instalado')
        if checks['tts'] == 'chatterbox':
            required += ('chatterbox_disponible',)
        return 0 if all(checks[k] for k in required) else 1
    assistant = VoiceAssistant()
    try:
        if args.text is not None:
            print(assistant.answer(args.text))
            print(json.dumps({'uso_api': assistant.usage}, ensure_ascii=False))
        elif args.audio is not None:
            pcm = read_wav(args.audio)
            if not os.getenv('OPENAI_API_KEY' if assistant.provider == 'openai' else 'OPENROUTER_API_KEY', '').strip():
                raise PipelineError('Falta la clave del proveedor elegido en .env.')
            if args.output.resolve() == args.audio.resolve():
                raise ValueError('La salida debe ser diferente del archivo de entrada.')
            wav, report = assistant.process(pcm)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(wav)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            print('Audio guardado en:', args.output.resolve())
        else:
            import uvicorn
            uvicorn.run(app, host=args.host, port=args.port, workers=1)
    except (PipelineError, ValueError, OSError, wave.Error) as exc:
        parser.exit(1, f'Error: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
