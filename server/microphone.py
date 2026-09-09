"""Captura acotada; el micrófono se cierra antes de consultar la API."""
import select
import subprocess
import sys
import time


class MicrophoneError(Exception):
    pass


def record_question(device=None, max_seconds=60, input_stream=None):
    import sounddevice as sd

    input_stream = input_stream or sys.stdin
    info = sd.query_devices(device, 'input')
    rate = int(info['default_samplerate'])
    capacity = rate * 2 * max_seconds
    blocks = bytearray()
    problems = []

    def receive(data, frames, timing, status):
        if status:
            problems.append(str(status))
        remaining = capacity - len(blocks)
        blocks.extend(bytes(data)[:remaining])
        if len(blocks) >= capacity:
            raise sd.CallbackStop

    try:
        # Captura a la frecuencia nativa; no todos los micros aceptan 16 kHz.
        with sd.RawInputStream(device=device, samplerate=rate, channels=1,
                               dtype='int16', callback=receive) as stream:
            print('Grabando. Habla y pulsa Enter para terminar (máximo 60 s).', flush=True)
            deadline = time.monotonic() + max_seconds
            while stream.active and time.monotonic() < deadline:
                ready, _, _ = select.select([input_stream], [], [], 0.1)
                if ready:
                    if input_stream.readline() == '':
                        raise EOFError
                    break
    except sd.PortAudioError as exc:
        raise MicrophoneError(
            'No se pudo abrir el micrófono. Permite el acceso a Terminal en '
            'Ajustes del Sistema > Privacidad y seguridad > Micrófono, y revisa la entrada de sonido.'
        ) from exc
    if problems:
        raise MicrophoneError('Se perdieron muestras del micrófono. Repite la grabación.')
    if len(blocks) < rate * 2 * 0.2:
        raise MicrophoneError('La grabación fue demasiado corta. Habla antes de pulsar Enter.')
    result = subprocess.run([
        'ffmpeg', '-v', 'error', '-f', 's16le', '-ar', str(rate), '-ac', '1',
        '-i', 'pipe:0', '-f', 's16le', '-ar', '16000', '-ac', '1', 'pipe:1',
    ], input=bytes(blocks), capture_output=True, check=True, timeout=30)
    return result.stdout
