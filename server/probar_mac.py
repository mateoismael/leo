"""Prueba interactiva con altavoces del Mac; no requiere ESP32."""
import argparse
import json
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path

from leov1ser import ROOT, RATE, VoiceAssistant, read_wav


def play_stream(chunks, output, started):
    """Guarda el PCM y lo entrega al reproductor según llega."""
    if not shutil.which('ffplay'):
        raise RuntimeError('Falta ffplay (incluido en la instalación completa de FFmpeg).')
    output.parent.mkdir(parents=True, exist_ok=True)
    errors = tempfile.TemporaryFile()
    player = subprocess.Popen([
        'ffplay', '-nodisp', '-autoexit', '-loglevel', 'error',
        '-probesize', '32', '-analyzeduration', '0',
        '-f', 's16le', '-ar', str(RATE), '-ch_layout', 'mono', '-i', 'pipe:0',
    ], stdin=subprocess.PIPE, stderr=errors)
    first = None
    count = 0
    try:
        with wave.open(str(output), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(RATE)
            for chunk in chunks:
                if len(chunk) % 2:
                    raise ValueError('Fragmento PCM incompleto.')
                if not chunk:
                    continue
                if first is None:
                    first = time.perf_counter() - started
                    print(f'Primer audio disponible: {first:.2f} s (el reproductor añade su búfer).', flush=True)
                wav.writeframesraw(chunk)
                player.stdin.write(chunk)
                player.stdin.flush()
                count += len(chunk)
        delivered = time.perf_counter() - started
        player.stdin.close()
        code = player.wait(timeout=90)
        errors.seek(0)
        diagnostic = errors.read().decode('utf-8', errors='replace').lower()
        if code != 0 or 'failed' in diagnostic or 'error' in diagnostic:
            raise RuntimeError('El reproductor no pudo abrir o completar la salida de audio.')
        if not count:
            raise RuntimeError('La respuesta no produjo audio.')
        print(json.dumps({'primer_pcm_s': first, 'entrega_completa_s': round(delivered, 3),
                          'duracion_audio_s': count / (RATE * 2)}, ensure_ascii=False))
        print('WAV guardado:', output.resolve())
    finally:
        if hasattr(chunks, 'close'):
            chunks.close()
        if player.poll() is None:
            player.terminate()
            try:
                player.wait(timeout=5)
            except subprocess.TimeoutExpired:
                player.kill()
                player.wait()
        errors.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--text', help='Una pregunta escrita: API y respuesta hablada')
    mode.add_argument('--audio', type=Path, help='Pregunta WAV PCM16 mono 16 kHz: Whisper, API y voz')
    mode.add_argument('--replay', type=Path, help='Reproducir WAV existente; sin internet ni consumo')
    parser.add_argument('--output', type=Path, default=ROOT / 'recordings/prueba-mac.wav')
    args = parser.parse_args()
    source = args.audio or args.replay
    if source and source.resolve() == args.output.resolve():
        parser.error('La salida no puede sobrescribir el audio de entrada.')
    if not shutil.which('ffplay'):
        parser.error('Falta ffplay para reproducir audio.')
    assistant = VoiceAssistant()
    try:
        if args.replay:
            pcm = read_wav(args.replay)
            chunks = (pcm[i:i + 2048] for i in range(0, len(pcm), 2048))
            play_stream(chunks, args.output, time.perf_counter())
        elif args.audio:
            pcm = read_wav(args.audio)
            print('Cargando Whisper antes de medir…', flush=True)
            assistant.load_transcriber()
            started = time.perf_counter()
            text, chunks = assistant.prepare_stream(pcm)
            print('Entendido:', text, flush=True)
            play_stream(chunks, args.output, started)
            print('Respuesta:', assistant.history[-1]['content'])
            print('Uso API:', json.dumps(assistant.usage))
        else:
            print('Escribe tu pregunta y pulsa Enter. Cada pregunta usa la API; /salir termina.', flush=True)
            while True:
                text = args.text if args.text is not None else input('\nTú: ').strip()
                if text == '/salir':
                    break
                if not text:
                    if args.text is not None:
                        parser.error('La pregunta está vacía.')
                    continue
                play_stream(assistant.stream_speech(text), args.output, time.perf_counter())
                print('Respuesta:', assistant.history[-1]['content'])
                print('Uso API:', json.dumps(assistant.usage))
                if args.text is not None:
                    break
    except (KeyboardInterrupt, EOFError):
        print('\nPrueba terminada.')
    except Exception as exc:
        # Los SDK pueden incluir datos de peticiones en excepciones: no imprimirlos.
        parser.exit(1, f'No se pudo completar la prueba ({type(exc).__name__}). Revisa conexión y salida de audio.\n')


if __name__ == '__main__':
    main()
