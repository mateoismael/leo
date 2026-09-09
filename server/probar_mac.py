"""Prueba interactiva con altavoces del Mac; no requiere ESP32."""
import argparse
import json
import time
import wave
from pathlib import Path

from leov1ser import ROOT, RATE, VoiceAssistant, read_wav
from playback import PCMPlayer
from microphone import MicrophoneError, wait_and_record


def play_stream(chunks, output, started):
    """Guarda el PCM y lo entrega al reproductor según llega."""
    output.parent.mkdir(parents=True, exist_ok=True)
    first = None
    count = 0
    try:
        # El dispositivo recibe silencio mientras se esperan los primeros datos.
        with PCMPlayer(RATE) as player, wave.open(str(output), 'wb') as wav:
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
                player.write(chunk)
                count += len(chunk)
            delivered = time.perf_counter() - started
            if not count:
                raise RuntimeError('La respuesta no produjo audio.')
            player.finish()
            if player.buffer.underflows:
                print(f'Aviso: {player.buffer.underflows} interrupciones de salida de audio detectadas.')
        print(json.dumps({'primer_pcm_s': first, 'entrega_completa_s': round(delivered, 3),
                          'duracion_audio_s': count / (RATE * 2)}, ensure_ascii=False))
        print('WAV guardado:', output.resolve())
    finally:
        if hasattr(chunks, 'close'):
            chunks.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--text', help='Una pregunta escrita: API y respuesta hablada')
    mode.add_argument('--audio', type=Path, help='Pregunta WAV PCM16 mono 16 kHz: Whisper, API y voz')
    mode.add_argument('--replay', type=Path, help='Reproducir WAV existente; sin internet ni consumo')
    mode.add_argument('--mic', action='store_true', help='Conversar por el micrófono (modo predeterminado)')
    mode.add_argument('--chat', action='store_true', help='Conversar escribiendo')
    mode.add_argument('--list-mics', action='store_true', help='Mostrar dispositivos de audio')
    parser.add_argument('--device', type=int, help='Índice del micrófono; por defecto el del sistema')
    parser.add_argument('--output', type=Path, default=ROOT / 'recordings/prueba-mac.wav')
    args = parser.parse_args()
    if args.list_mics:
        import sounddevice as sd
        print(sd.query_devices())
        return
    source = args.audio or args.replay
    if source and source.resolve() == args.output.resolve():
        parser.error('La salida no puede sobrescribir el audio de entrada.')
    assistant = VoiceAssistant()
    try:
        if args.mic or not (args.text is not None or args.audio or args.replay or args.chat):
            import sounddevice as sd
            try:
                info = sd.query_devices(args.device, 'input')
            except sd.PortAudioError as exc:
                raise MicrophoneError('No hay un micrófono disponible. Revisa la entrada de sonido de macOS.') from exc
            print('Micrófono:', info['name'])
            print('Cargando Whisper una sola vez…', flush=True)
            assistant.load_transcriber()
            print('Listo. Cada pregunta usa la API. q termina.', flush=True)
            while True:
                try:
                    pcm = wait_and_record(args.device)
                except MicrophoneError as exc:
                    print(str(exc), flush=True)
                    continue
                started = time.perf_counter()
                text, chunks = assistant.prepare_stream(pcm)
                print('Entendido:', text, flush=True)
                play_stream(chunks, args.output, started)
                print('Respuesta:', assistant.history[-1]['content'])
                print('Uso API:', json.dumps(assistant.usage))
        elif args.replay:
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
    except MicrophoneError as exc:
        parser.exit(1, str(exc) + '\n')
    except ImportError:
        parser.exit(1, 'Instala las dependencias: .venv/bin/python -m pip install -r server/requirements-mac.in\n')
    except Exception as exc:
        # Los SDK pueden incluir datos de peticiones en excepciones: no imprimirlos.
        parser.exit(1, f'No se pudo completar la prueba ({type(exc).__name__}). Revisa conexión y salida de audio.\n')


if __name__ == '__main__':
    main()
