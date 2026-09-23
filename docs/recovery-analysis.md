# Analysis of the recovered code

Date: 2026-09-09. Source: a recovered archive, kept unmodified. The four
extracted files are also kept unchanged. Static review: the firmware has not
been compiled and the server has not been run against hardware or external
services.

## Two pairs, two stages

| Stage | Firmware | Server | Implemented behaviour |
|---|---|---|---|
| Transcribe and repeat | `audio_transcriber.ino` | `mic_server.py` | Audio → Whisper base → text → gTTS → audio repeating what was said |
| Conversational assistant | `wristband_v0` firmware | `wristband_v0/server.py` | Audio → Whisper base → GPT-4o-mini over API → gTTS → spoken answer |

By functionality, the conversational pair looks like the evolution of the
transcriber; no version history confirms the chronology. These are not four
independent revisions of one program: they are two complementary
firmware-and-server pairs. The transcription stage is useful for testing the
microphone, transport and speaker without the conversational model call.

## Recovered architecture

1. While the button is held, the ESP32 reads the INMP441 over I2S at 16 kHz and converts samples from 32 to 16 bits.
2. It sends PCM chunks through HTTP POST requests to `/audio` on a server on the local network.
3. When the button is released, it sends another request with `Recording-Status: end`.
4. Python/FastAPI accumulates the audio and runs Whisper `base` on the machine hosting the server.
5. In the conversational pair, the text goes to the OpenAI API under the identifier `gpt-4o-mini`, with a short history kept in memory.
6. gTTS generates Spanish speech; librosa and wave convert it to mono WAV, 16-bit PCM at 16 kHz.
7. The HTTP response carries that WAV; the ESP32 skips the first 44 bytes and plays it through the MAX98357 and the speaker.

The firmware uses Wi-Fi/HTTP, not A2DP or USB, to carry speech. The server
listens on port 8000. Local addresses are hardcoded in the firmware: the code
alone does not identify which computer was running Python. A phone could have
provided the network connection, but that does not mean Python ran on the phone.
The conversational AI does not run inside the ESP32.

## Wiring supported by both firmwares

| Signal | ESP32 GPIO |
|---|---|
| Button, active low with internal pull-up | 4 |
| Microphone WS / SD / SCK | 25 / 32 / 33 |
| Amplifier BCLK / LRC / DIN | 26 / 27 / 22 |

I2S0 is used for the microphone and I2S1 for the speaker. This settles the
discrepancy in the notes: both programs together set the amplifier LRC on
GPIO27. It does not prove the preserved physical wiring matches. The camera from
the old notes still conflicts with the amplifier DIN on GPIO22 if combined
without reassignment.

## What the conversational pair adds

- A conversational model call and in-memory context; the other version only repeats the transcription.
- Instructions for short answers and a second attempt when the answer does not end in punctuation.
- Larger speaker buffers, more diagnostic messages, a 10-second HTTP timeout, a 10-second header wait and a 30-second playback limit.
- Up to three attempts for the final request when it does not receive HTTP 200.
- Explicit length and connection-close headers on the WAV response.

## Issues to fix when restoring it

1. **Retries with no recording identity.** The server empties the buffer before transcribing and synthesising. If the final request times out while processing, resending it does not automatically recover the same answer. Each recording should be identified and its result retained.
2. **JSON responses treated as audio.** The server also returns HTTP 200 with JSON when audio is missing, there is no text, or an error occurs. The firmware treats any final 200 as a WAV. It must check the response type, status and audio format.
3. **Capture interrupted by the network.** Each chunk of up to 1024 samples, around 64 ms of audio, is sent with a blocking POST. The microphone read waits on the network and can lose continuity when the delay exceeds what the buffers absorb. Separating capture from transmission, with a bounded queue, would make this measurable and controllable.
4. **Duplicated question.** `get_openai_response` appends the question to the history and appends it again when building `messages`.
5. **Global state with no recording limit.** Buffer and history are shared across the process, with no device identity and no maximum audio size. Sessions and resources must be bounded before widening use.
6. **Fragile playback.** A fixed 44-byte WAV header is assumed; the body length is not used as an end condition and complete playback is not validated. The 30-second limit ends up returning success even when it truncated the audio. After HTTP 200 the retry loop exits even if playback failed.
7. **Configuration to recover.** There are no library versions, no dependency manifest and no exact board model. The server loads the API key from the environment; the firmwares contain literal Wi-Fi configuration, which is not reproduced in this report and must be separated out when making a shareable version.

These points are deduced from the code; they are not failures observed in a
current physical test.

## Consequences for the redesign

The split between accessory and external processing already existed. The
portability work is deciding where to host the server away from the old PC,
improving the transport, and shrinking the electronics and power.

The Bluetooth Classic restriction mentioned while reviewing the old example does
not block these Wi-Fi firmwares. An ESP32-S3 can be re-evaluated as a candidate,
but it demands adapting pins and drivers and validating audio; it has not been
checked as a drop-in replacement.

Proposed order: restore the conversational pair in a reproducible environment,
use the transcriber for diagnosis if needed, measure latency and power draw, and
only then design the PCB and enclosure. Dimensions, exact battery, exact board
and a battery-life target are all missing before glasses or a wristband can be
sized. None of these four files includes a camera.

## Validation performed

- Read all four files and compared both firmwares and both servers.
- Syntax analysis with `ast.parse` succeeded for both Python files, without importing them or making external calls.
- Pending: installing dependencies, compiling for an identified board, audio and power tests on hardware, and verifying current services.
