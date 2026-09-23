# Local speech with Chatterbox

The engine was recovered from an earlier local project. It uses Chatterbox
Multilingual 0.1.7, published under the MIT licence. The model lives in the
user cache and takes roughly 3 GB; it is not copied into the repository.

To avoid incompatibilities, the server calls `server/tts_chatterbox.py` through
the existing Chatterbox Python environment. On the current machine the import
needs `NUMBA_CACHE_DIR`; the server points it at `.cache/numba`. Speech is
normalised to mono WAV PCM16 at 16 kHz for the ESP32 firmware.

The adaptation keeps the parts that matter for short replies: text splitting,
`torch.inference_mode`, Spanish, and an optional voice reference. It keeps the
model's default watermark. It copies no audio and no models from the source
project.

In historical measurements, CPU took close to 3.7 seconds of compute per second
of audio, and MPS caused swapping. The server uses CPU and caps each generation
at five minutes. It currently loads the model for every reply; a future
persistent version would cut the initial latency.

Test on 2026-09-09: "Prueba de voz lista." produced 1.92 seconds of audio. The
full run took about half a minute, including loading the model. The original
output was mono at 24 kHz and was correctly converted to mono WAV PCM16 at
16 kHz for the ESP32. This test used no conversational API and spent no credit.

Source and licence: https://github.com/resemble-ai/chatterbox
