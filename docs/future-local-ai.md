# Future local AI options

Decision of 2026-09-09: start with the Python server and the conversational
model over API. Keep Whisper for transcription and gTTS for speech output. None
of the alternatives below are implemented yet.

## Future option 1: commands inside the wristband

Recognise a limited set of orders and run local functions with no phone and no
connection. This is not the same as open conversation. ESP-SR is a reference
worth exploring, but its documented command models target English and Chinese;
Spanish would need its own evaluation. The functions and the model would have to
be chosen, then memory, accuracy and power draw measured.

Source: https://github.com/espressif/esp-sr

## Future option 2: local AI on the phone

The wristband captures and plays audio; the phone runs speech recognition, the
conversational model and synthesis, needing no internet once the models are
installed. A wristband-to-phone link is still required, and the transport is
undecided. Memory, speed, battery and Spanish quality would have to be checked
on the specific handset.

Qwen3-0.6B is a reference to evaluate, not a confirmed choice, and not a model
that fits on the ESP32. Transcription and synthesis need their own local
components.

Source: https://huggingface.co/Qwen/Qwen3-0.6B

## Personal server

Hosting the Python server on a personal machine remains a deployment path for
the main option. If a model were later hosted there too, that stage would stop
depending on a third-party API, but the wristband would still need a connection
to reach it. This is not considered an offline mode for the wristband.
