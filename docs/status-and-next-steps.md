# Status and next steps

Updated 9 September 2026.

## Current goal

Build a camera-less voice wristband. The ESP32 captures and plays audio; a
computer or server runs Whisper locally, queries the conversational model over
API and generates the spoken answer with gTTS. The first version needs Wi-Fi.

## What works

- The server receives mono PCM16 at 16 kHz through `POST /audio`.
- Whisper `base` loads at server start-up. A question does not wait for the initial load.
- The original mode can still return a complete WAV.
- The new mode is enabled with `Response-Mode: stream` and returns headerless PCM.
- The model answer arrives token by token and is split into sentences.
- A thread keeps receiving text while gTTS synthesises the sentences already available.
- The updated firmware requests the stream over HTTP/1.0 and plays the PCM bytes as they arrive.
- Sixteen automated tests validate the server and simulated capture without spending API credit.

## Real tests

The single-word test exercised Whisper, GPT-5 nano and gTTS:

| Measurement | Result |
|---|---:|
| Whisper preload | 2.068 s |
| Warm transcription | 0.44–0.70 s |
| First audio, answer "Lima" | 4.430 s |
| Complete audio | 4.430 s |
| Estimated API cost | USD 0.00000675 |

A three-sentence answer verified the overlap:

| Measurement | Result |
|---|---:|
| First audio fragment | 4.580 s |
| Complete audio generated | 8.089 s |
| Head start gained | 3.509 s |
| Estimated API cost | USD 0.00003575 |

Streaming does not shorten a single-sentence answer: it lets long answers start
playing before they finish. The two real calls in this implementation cost
roughly USD 0.00004250 in total.

The verification WAVs stayed in `recordings/`, outside Git. FFprobe confirmed
mono PCM16 at 16 kHz. A temporary local server was also started to confirm that
an HTTP/1.0 request receives a clean PCM body, delimited by connection close and
free of chunked-encoding bytes.

## What is not verified yet

- No ESP32 is connected, so the stream has not been heard on the physical INMP441, MAX98357A and speaker.
- Neither `arduino-cli` nor PlatformIO is installed on this computer; the firmware was reviewed but not compiled here.
- It must be confirmed that the `HTTPClient` library version installed for the board honours `useHTTP10(true)` as it did in the server test.
- gTTS generates each full sentence before delivering it. This is streaming between sentences, not within a word or sentence.
- Several gTTS calls can introduce small differences in pacing. 80 ms of silence is inserted between sentences.
- If the API or gTTS fails after the HTTP body has started, it can no longer be replaced with a JSON error; the firmware will see an interrupted connection.
- The recovered capture still makes a blocking POST roughly every 64 ms. The network could cause gaps in the recording, and this must be measured physically.

## Next steps

1. Compile the firmware for the exact ESP32 model and fix any difference in the installed library.
2. Run a bench test with USB power, microphone, amplifier and speaker; measure from button release to the first sample played.
3. Compare WAV mode and streaming mode with one-sentence and multi-sentence questions.
4. Separate capture from networking on the ESP32 with a queue, so a slow HTTP request does not interrupt the microphone.
5. Add a recording identifier and keep the answer temporarily, to recover from failures or retries without repeating a paid call.
6. Tune sentence splitting and the answer limit using real Spanish recordings.
7. Once the path is stable, choose the final board, measure power draw and design a compact camera-less PCB.
8. Prepare deployment on the personal server with HTTPS, device authentication and usage limits.

## Criterion for continuing

The next decision depends on the physical test. If the first sound arrives close
to the server measurement, this design stays. If dropouts, extra bytes or stalls
appear, the result will be documented here and the audio transport tested first;
swapping Whisper would not fix those failures.

## Mac testing and interruptible conversation

`server/mac_client.py` was added. From the repository root:

```sh
.venv/bin/python server/mac_client.py
```

It now allows speaking through the Mac microphone: SPACE starts, SPACE stops;
`q` quits and Ctrl+C interrupts the test. Each question calls the API and uses
gTTS. To type instead of speak, use `--chat`. History is kept while the session
stays open and the last audio is saved to `recordings/mac-test.wav`.

```sh
# No API and no internet: play back an already saved answer.
.venv/bin/python server/mac_client.py --replay recordings/streamed-answer.wav
# Recorded question: transcribe with Whisper and query the API.
.venv/bin/python server/mac_client.py --audio recordings/simulated-question.wav
```

Additional verification: 13 tests pass, including closing the producer queue on
cancellation and holding the lock during HTTP transmission. The endpoint
previously released that lock when returning the response, allowing
conversations to overlap. That was fixed. An active API read can take until its
timeout before finishing; instant cancellation of a remote request is not
guaranteed.

Local playback of the "Lima" WAV opened ffplay without errors outside the
sandbox. Inside the sandbox, access to the audio device failed. This confirms
the player works; it is not an acoustic measurement with a microphone.

A clarification on the earlier measurements: 4.580 s and 8.089 s come from a
text-only test, with no Whisper and no ESP32 transport. The 3.509 s difference
is between the first and last PCM of the same run, not an A/B comparison against
WAV mode. The speaker adds its own playback latency. The "Lima" test did include
transcription (0.670 s), first PCM at 4.433 s and a 2.006 s preload. There is
still no end-to-end physical voice measurement.

Automatic voice interruption (barge-in), proposed for after the basic path is
validated:

1. First, allow pressing the button while it speaks to stop playback, discard pending audio and start a new recording. The current firmware does not implement that interruption yet.
2. Then keep listening during playback, detect speech (VAD) and cancel the turn when the user starts talking.
3. Add echo cancellation so the speaker is not mistaken for the user's voice, and tune end-of-turn detection to tolerate pauses.
4. Keep in the history which part of the answer was actually heard, and add the user's correction before generating the next answer. At present the full generated text is stored, not the audio actually heard.

This improves naturalness and allows corrections, but it does not by itself make
the API faster. Always-on listening is not part of this phase. Reference
consulted: https://elevenlabs.io/docs/eleven-agents/customization/conversation-flow

## Microphone capture implemented

sounddevice 0.5.6 was installed in the local environment. macOS recognises the
built-in microphone (index 0) and the speakers (index 1). Capture uses the
device's native rate, mono PCM16, and FFmpeg converts to 16 kHz. Whisper stays
loaded during the conversation. Capture closes before transcribing and playing
the answer. The limit is 60 seconds; capture errors and recordings that are too
short are never sent to the API.

16 tests were verified: they include a real conversion of simulated PCM from 48
to 16 kHz, rejection of short recordings and rejection of sample loss. Device
enumeration was tested outside the sandbox. Microphone permission for Terminal
and a real voice test are still pending; nothing was recorded during these
checks and no new paid calls were made. Full acoustic latency has not been
measured yet.

## Reported clipping of the first words

Symptom: the text is complete, but the start of the first word seems to be
missing when playback begins. Re-transcribing the first seven seconds of the
saved WAV locally yields a recognisable sentence. This points at playback, but
does not prove synthesis is free of clipping; acoustic confirmation is still
needed.

ffplay in the Mac client was replaced with sounddevice/PortAudio. The device
opens before the generator is consumed, emits 200 ms of priming silence and
stays active through pauses. The queue keeps pending PCM bytes: if the next
sentence does not arrive, silence goes out and playback then continues from its
first sample. The saved WAV keeps the original PCM, without that priming
silence. The last data is awaited before closing, and underflows detected by
PortAudio are reported.

Verification: 18 tests pass. The new tests compare start and end bytes and check
continuity after a pause. "Lima" played outside the sandbox with no errors, no
reported underflows and no new API calls. The sandbox does not allow opening the
audio output. The acoustic problem is not claimed to be solved until confirmed
in real use. Microphone control is still SPACE to start/stop and q to quit.

Free test with the saved answer, without overwriting it:

```sh
.venv/bin/python server/mac_client.py --replay recordings/mac-test.wav --output recordings/audio-review.wav
```

Separate item pending: the model offered to look information up, but the program
has no web search tool. Past answers about a book have not been verified and
must not be treated as search results.

## Usage confirmation — 12 September 2026

The clipping at the start of the audio appears to have gone after the move to
sounddevice/PortAudio. This is recorded as a perceived improvement in real use,
provisionally confirmed; whether it reappears in later conversations is still to
be observed. It is neither a controlled acoustic measurement nor a validation of
ESP32 playback.

## Firmware fix and recovery — 12 September 2026

This section updates the historical open items on compilation, blocking capture
and recording identity.

- The no-data wait was fixed: 20 s of inactivity and 90 s total; a cut-off is not read as success.
- The reader preserves chunks split by TCP, validates the format and waits for the explicit end. I2S uses writes with a timeout and a final drain.
- Capture and networking are separated by a 16-chunk FreeRTOS queue. A full queue or a detected failure discards the recording, so that incomplete question never reaches the API.
- The new v2 routes use IDs and sequences. Upload retries do not duplicate PCM, and response retries attach to the existing result. Production continues even if the receiver disconnects.
- In-memory cache: up to four sessions, results for up to five minutes and subject to eviction for capacity. It does not survive restarts. Recovery starts from the beginning, not from the word where it was cut.
- 25 Python tests pass, including a real HTTP/1.0 TCP disconnect and recovery on localhost, with the provider executed only once. C++ tests of the reader also pass: fragmented bytes, empty socket, disconnect and clock rollover.
- Cross-compilation completed for ESP32 Dev Module with core 3.3.11 and Arduino CLI 1.5.1 on Apple Silicon. Result: 1,042,664 bytes of program (79%) and 54,872 bytes of global variables (16%). The queue, tasks and dynamic buffers consume additional RAM at runtime.
- The first attempt with core 2.0.17 failed on Intel executables. 3.3.11 was installed with a native compiler and the ctags helper was built for ARM64. The adaptation is documented so it can be reproduced.

No firmware was uploaded to a board, no API credit was spent and the physical
microphone and amplifier were not verified. The ESP32 model still needs
confirming, the pins reviewing and a bench test running on both normal and slow
networks. Mac mode keeps SPACE for the microphone and sounddevice playback.

Details and commands: [Firmware and protocol](firmware-and-protocol.md).
