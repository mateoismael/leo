# Recovery plan

Current decision: start with conversational AI over API. Both local
alternatives are kept for later in [Future local AI](future-local-ai.md).

## 1. Software on the computer

- Server dependencies and Whisper installed in `.venv`; the macOS/Python 3.9 environment versions are recorded in `server/requirements-dev-lock.txt`.
- Done: external configuration and separate transcription, conversation and speech stages.
- Done: CLI with `--text`, `--audio` and `--check`, no ESP32 required.
- A minimal real query against GPT-5 nano was verified.
- The full path without an ESP32 was verified with synthesised speech: Whisper transcribed correctly, GPT-5 nano answered "Lima" and gTTS produced the final WAV. First-run timings: 5.891 s transcription, 3.522 s API and 0.548 s speech. Usage: 47 input tokens and 11 output; estimated call cost USD 0.00000675 at the rate consulted.
- Chunked HTTP upload, the end signal and both WAV and progressive PCM response modes were verified.
- Chatterbox Multilingual was integrated and tested as the local alternative. gTTS remains the default output for its lower latency.
- Real gTTS test: produced 2.42 seconds of compatible audio in 1.44 seconds, with no call to the conversational model.
- The server preloads Whisper before accepting audio, and `/health` reports whether it stayed loaded. This moves the slow start to server start-up; measured warm transcription is still around 0.44 s.
- Done: no duplicated question, HTTP error states, WAV/PCM validation and sentence-level streaming. Eleven automated tests with stubbed providers.
- A real three-sentence answer delivered first audio at 4.580 s and finished generating at 8.089 s: playback can start 3.509 s early. Details and limits in [Status and next steps](status-and-next-steps.md).

## 2. Communication and existing hardware

- Identify the board and battery, and confirm the wiring.
- Done in v2: IDs, sequences and an in-memory cache to recover answers for up to five minutes, as long as they are not evicted for capacity.
- A FreeRTOS queue between capture and upload is implemented and compiles; timing and continuity on hardware are still pending.
- Measure audio continuity, latency and power draw on hardware.

## 3. Personal server

A personal server is available and the service is expected to be hosted there
later. Its operating system, resources, domain and access method are not yet
known. No connection or deployment has been made.

- Choose where speech processing runs, based on resources and latency.
- Prepare a reproducible deployment and secret management.
- Add HTTPS, device authentication and request and audio limits.
- Set up supervision, restart and health checking.

## 4. Compact wristband

- Fix target battery life, weight and dimensions.
- Choose a camera-less board, battery and audio output.
- Design the PCB and enclosure, build a prototype and test comfort.

## Scope of simulation

Tests with audio files validate the server without an ESP32. Simulating the
firmware logic and networking must keep audio decoupled: full simulation of the
microphone, amplifier, battery or acoustic behaviour is not assumed.

Update, 12 September: firmware compiles for ESP32 Dev Module, core 3.3.11. It
passes 25 Python tests, and the C++ reader was tested without a board. Details
in [Firmware and protocol](firmware-and-protocol.md).
