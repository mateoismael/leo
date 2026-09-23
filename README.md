# Leo

Wrist-worn voice assistant with a button and a speaker, no camera. Built on a recovered ESP32 prototype.

The main path is **Whisper on the computer → conversational model over API → speech with gTTS**. Chatterbox Multilingual remains the local alternative. Future options — on-device commands and local AI on the phone — are covered in [Local AI](docs/future-local-ai.md).

## Status

The server has been refactored with external configuration, a text-only test, a WAV test, Whisper preloading and progressive spoken responses. It keeps the original WAV mode on `/audio` and adds streaming PCM for the updated firmware. 25 Python tests and the C++ transport tests pass, along with two real end-to-end runs against the API. The key is configured locally and Whisper base is already downloaded. The firmware compiles for ESP32 Dev Module with core 3.3.11; it has not been tested on physical hardware yet, and there is no cloud deployment.

## Setup

From the repository root, with Python 3.9 or later:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.in
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`, outside Git. `OPENAI_MODEL` uses `gpt-5-nano` as the initial low-cost candidate (a deprecated model; compare against `gpt-4o-mini` and `gpt-5.6-luna`); `WHISPER_MODEL` stays on `base`. Real conversation tests call the API and cost money.

`TTS_PROVIDER=gtts` produces the spoken reply quickly through a free external service. It needs internet but does not spend the conversational API budget. To try the recovered local alternative, switch to `TTS_PROVIDER=chatterbox`; `CHATTERBOX_PYTHON` must point at the Python of its separate environment. A clean 10–20 second WAV reference can be set in `CHATTERBOX_REFERENCE`; leaving it empty uses the default voice.

To process audio, also install:

```sh
.venv/bin/python -m pip install -r server/requirements-audio.in
```

FFmpeg must be installed and available on PATH. Whisper downloads the model the first time it runs; that needs a connection and local disk space. On start-up, `PRELOAD_WHISPER=true` loads it before accepting audio so the first question does not pay that cost. The text-only test does not load Whisper.

## Testing without an ESP32

Check the environment without external calls (exits 1 if an audio requirement is missing):

```sh
.venv/bin/python server/app.py --check
```

Test the API conversation alone:

```sh
.venv/bin/python server/app.py --text "Hello, tell me what you can do in one sentence."
```

Test the full path with a mono PCM16 WAV recording at 16 kHz, between 0.2 and 60 seconds:

```sh
.venv/bin/python server/app.py --audio recordings/question.wav --output recordings/answer.wav
```

The spoken reply is saved, and the transcription, the text and the timings of each stage are printed. The first transcription includes loading Whisper. `recordings/` is excluded from Git. Chatterbox takes considerably longer and is reserved for local tests that do not need an immediate answer.

To convert a recording to that format:

```sh
ffmpeg -i my-recording.m4a -ar 16000 -ac 1 -c:a pcm_s16le recordings/question.wav
```

Create the `recordings` folder first if it does not exist.

## Server and firmware

```sh
.venv/bin/python server/app.py
```

By default it listens only on `127.0.0.1:8000`; `/health` confirms the process responds, not that providers are reachable. To connect the ESP32 on a controlled development network, use `--host 0.0.0.0`. Copy `firmware/wristband/config.example.h` to `config.h` and fill in the network, password and HTTP address of the server.

The endpoint accepts mono PCM16 chunks at 16 kHz on POST `/audio` plus an empty request carrying `Recording-Status: end`. With no other header it returns the complete WAV compatible with the recovered firmware. With `Response-Mode: stream`, it transcribes first and then delivers mono PCM16 at 16 kHz as each sentence finishes synthesis. That mode is kept for older clients. The updated firmware uses the v2 routes described below, with an explicit end marker and recovery by ID. Invalid audio returns 400, oversized returns 413, a busy pipeline returns 409, and errors detected before the response starts return 502.

This compatibility targets **one device and one process**, with no authentication. Do not run multiple workers or expose it to the internet. The old endpoint keeps its simple state; protocol v2 adds IDs, sequences, a temporary cache and expiry. The old firmware waits only 10 seconds for the answer and may time out; the first test should be done over the CLI.

## Automated tests

```sh
.venv/bin/python -m pip install httpx
.venv/bin/python -m unittest discover -s tests -v
```

The tests stub out external providers: they verify history, sentence segmentation, audio format and both modes of the HTTP protocol at no API cost.

Detailed status, streaming measurements, their limits and the order of work are in [Status and next steps](docs/status-and-next-steps.md).

## Layout and provenance

- `server/app.py`: current working version.
- `firmware/wristband/`: recovered firmware with private configuration kept separate.
- `legacy/wristband_v0/server.py`: original conversational server, kept unchanged.
- `legacy/audio_transcriber/`: earlier pair that transcribes and repeats.
- `docs/`: historical analysis, hardware, plan and future local AI.

Dependency `.in` files describe required packages; the `.txt` files, where they exist, capture versions verified in the development environment and do not guarantee compatibility elsewhere. Future deployment on a personal server is described in the [plan](docs/plan.md); authentication, HTTPS and supervision still need work.

Chat Completions is the current API. See the [model and cost comparison](docs/api-model-comparison.md). To migrate to OpenRouter later, set `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`; it uses a separate key and that provider's official URL. Only the text path is prepared — not native multimodal voice, not Gemini Live.

## Talking from the Mac

```sh
.venv/bin/python server/mac_client.py
```

The default mode uses the Mac microphone. Press SPACE to record, speak, and press SPACE again to stop. Listen to the answer and repeat; `q` quits. That is two presses, not holding the key down. If macOS asks for microphone permission for Terminal, grant it. Whisper loads once before the first recording. Each question uses the API and gTTS. For written mode, add `--chat`. To test an existing WAV with Whisper, use `--audio recordings/simulated-question.wav`. To play audio back with no external calls, use `--replay recordings/streamed-answer.wav`.

Installing microphone support:

```sh
.venv/bin/python -m pip install -r server/requirements-mac.in
```

If there is no audio input, check System Settings > Sound > Input and Privacy & Security > Microphone. `--list-mics` shows devices; `--device 0` selects one by index. Maximum recording: 60 seconds. The microphone stays closed while the answer plays; there is no automatic voice interruption yet.

Mac playback now uses sounddevice/PortAudio with a buffer and 200 ms of priming silence to protect the start of the audio. ffplay was removed from this path.

## Corrected firmware and protocol v2

The ESP32 captures audio in one task and sends it from another through a 16-chunk queue. If loss is detected or the queue fills, it discards the recording. The `/audio/recordings/{id}/…` routes deduplicate chunks and keep results so they can be recovered without repeating the query, as long as they remain cached. An end marker is required to tell a complete answer apart from a dropped connection.

```sh
.venv/bin/python scripts/compile_firmware.py
```

This compiles a copy with example credentials, without touching the board or the private `config.h`. See [protocol, tests, tooling and limits](docs/firmware-and-protocol.md). The server must be updated alongside the firmware; the Mac conversation program keeps working with the same command.
