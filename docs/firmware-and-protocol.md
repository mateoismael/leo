# Firmware and transport — 12 September 2026

## Scope

Classic ESP32, INMP441 microphone and MAX98357A amplifier on the historical
pins. No board has been connected, recorded from or flashed. The Mac still uses
`mac_client.py` and the server keeps the original `/audio`. The updated firmware
also requires the updated server, because it uses the new routes.

## Capture and networking

The main task reads I2S with a 200 ms maximum wait and enqueues PCM16 chunks of
up to 2048 bytes. A separate FreeRTOS task uploads them. The queue holds 16
chunks (roughly 32 KiB and 1.024 seconds of audio). HTTP is never awaited inside
capture.

If the queue fills, the microphone fails, or upload exhausts its three attempts,
capture stops and the recording is discarded; the model is not queried with that
incomplete audio. This absorbs brief delays — it does not guarantee continuity
on any network. Releasing the button waits for queued uploads to finish. Limit:
60 seconds of speech. While processing or playing, no other recording is
accepted. Button interruption is not part of this change yet.

## v2 routes

`AUDIO_SERVER_URL` is still `http://HOST:8000/audio`. These suffixes are added:

| Method | Suffix | Purpose |
|---|---|---|
| POST | `/recordings/{id}/start` | Create a session; repeating does not erase received audio |
| POST | `/recordings/{id}/chunks/{seq}` | PCM numbered from zero; repeating the same chunk does not duplicate it |
| POST | `/recordings/{id}/end?blocks=N` | Verify every chunk arrived, then produce or recover the answer |
| POST | `/recordings/{id}/abort` | Discard a failed upload before querying the API |

Out-of-order chunks, or duplicates with different content: 409. Recording too
long: 413. Missing or expired ID at the end: 404, with no automatic new query.
The sequence and the ID are preserved across retries.

The answer is generated in a server task that continues if the receiver
disconnects. Repeating `end` recovers the same fragments from the beginning,
with no further provider call. A part that already played may be heard again;
there is no resume from an exact position yet.

Local in-memory cache: four sessions maximum; expiry after five minutes of
inactivity for uploads, or from completion for results. If space is needed, the
oldest finished result is evicted. Sessions still processing are never evicted.
The cache does not survive a server restart and provides no permanent
deduplication. Keep a single process/worker and local network access: no
authentication is added at this stage.

## Audio and detecting cut-offs

HTTP/1.0, header `X-Audio-Format: pcm-s16le-framed-v1`. Each frame carries a
little-endian uint32 length followed by 2 to 2048 bytes of mono PCM16 at 16 kHz.
Zero length means success and a complete end. `0xffffffff` means failure. The
header is never played as audio.

The ESP32 requires an explicit end: a connection closing earlier, an incomplete
frame or an error do not count as success. It reads even bytes split by TCP
without breaking 16-bit samples. Waiting is capped at 20 seconds with no data
and 90 seconds total, including when the socket is connected but empty. Each
I2S write has a 500 ms wait, checks for partial writes and drains the DMA queue
before stopping.

## Reproducible verification

Python tests (25 once this protocol was added), including a real HTTP/1.0
loopback connection with a mid-response disconnect and recovery, plus stubbed
providers:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

C++ tests of the same reader the firmware uses: waiting with no data, fragmented
bytes, partial disconnect, global limit and millis overflow:

```sh
mkdir -p .cache
c++ -std=c++17 -Wall -Wextra -Werror tests/test_transport.cpp -o .cache/test_transport
.cache/test_transport
```

Local compilation, with the example configuration and without uploading
anything to the board:

```sh
.venv/bin/python scripts/compile_firmware.py
```

Tooling installed in `.cache/arduino/`, ignored by Git: Arduino CLI 1.5.1 and
core `esp32:esp32@3.3.11`. Target profile: `esp32:esp32:esp32` (generic ESP32
Dev Module). This does not confirm the exact board model in use.

2.0.17 was tried first; its Intel binaries could not run on this Mac without
Rosetta. The move to 3.3.11 brought an ARM64 compiler. The bundled ctags helper
was also Intel: it was built locally from `arduino/ctags`, tag `5.8-arduino11`,
commit `abc8fca7499f44c725122881cd380a88c37abe0e`. For the current macOS SDK its
`__unused__` macro was renamed to `CTAGS_UNUSED` in the local sources, avoiding
a collision with the system macro. The script passes its path through
`runtime.tools.ctags.path`.

On another Mac, install Arduino CLI, configure the index
`https://espressif.github.io/arduino-esp32/package_esp32_index.json` and install
core 3.3.11. The data, downloads and user paths must point at
`.cache/arduino/{data,downloads,user}` in `arduino-cli.yaml`. A native ctags is
only needed if that machine's package shows the Intel incompatibility described
above.

Tooling sources: [Arduino CLI](https://docs.arduino.cc/arduino-cli/installation/),
[ESP32 migration](https://docs.espressif.com/projects/arduino-esp32/en/latest/migration_guides/2.x_to_3.0.html),
[Arduino ctags](https://github.com/arduino/ctags/tree/5.8-arduino11).

## Physical work pending

Confirm the board and pins, test slow Wi-Fi and queue exhaustion, speech
continuity, complete playback and power draw. Compiling verifies neither
electrical behaviour nor the real timing of I2S/FreeRTOS. No API credit was
spent on these tests.
