"""Captura acotada; el micrófono se cierra antes de consultar la API."""
import select
import subprocess
import sys
import time
import os
import termios
import tty
from contextlib import contextmanager


class MicrophoneError(Exception):
    pass


@contextmanager
def immediate_keys(stream):
    if not stream.isatty():
        raise MicrophoneError('Abre el programa en Terminal para usar la barra espaciadora.')
    fd = stream.fileno()
    previous = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        # Descarta teclas pulsadas durante la respuesta anterior.
        termios.tcflush(fd, termios.TCIFLUSH)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def read_key(stream):
    key = os.read(stream.fileno(), 1).decode(errors='ignore') if stream.isatty() else stream.read(1)
    if key == '' or key in ('q', 'Q'):
        raise EOFError
    return key


def wait_and_record(device=None):
    with immediate_keys(sys.stdin):
        print('\nPulsa ESPACIO para grabar; q para salir.', flush=True)
        while read_key(sys.stdin) != ' ':
            pass
        return record_question(device)


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
            print('Grabando. Habla y pulsa ESPACIO para terminar (máximo 60 s).', flush=True)
            deadline = time.monotonic() + max_seconds
            while stream.active and time.monotonic() < deadline:
                ready, _, _ = select.select([input_stream], [], [], 0.1)
                if ready:
                    if read_key(input_stream) == ' ':
                        break
    except sd.PortAudioError as exc:
        raise MicrophoneError(
            'No se pudo abrir el micrófono. Permite el acceso a Terminal en '
            'Ajustes del Sistema > Privacidad y seguridad > Micrófono, y revisa la entrada de sonido.'
        ) from exc
    if problems:
        raise MicrophoneError('Se perdieron muestras del micrófono. Repite la grabación.')
    if len(blocks) < rate * 2 * 0.2:
        raise MicrophoneError('La grabación fue demasiado corta. Habla antes de pulsar ESPACIO.')
    result = subprocess.run([
        'ffmpeg', '-v', 'error', '-f', 's16le', '-ar', str(rate), '-ac', '1',
        '-i', 'pipe:0', '-f', 's16le', '-ar', '16000', '-ac', '1', 'pipe:1',
    ], input=bytes(blocks), capture_output=True, check=True, timeout=30)
    return result.stdout
