# API models — surveyed 9 September 2026

Goal: make use of existing OpenAI credit in a camera-less wristband. OpenRouter
with some Gemini model is a future preference; no claim of better quality or
lower cost is made without comparing concrete models and modalities.

## Comparison

Text rates per million tokens, uncached input and output, without Batch or
tools.

| Model | Input USD | Output USD | Proposed use |
|---|---:|---:|---|
| GPT-5 nano | 0.05 | 0.40 | Initial lowest-rate candidate; measure reasoning, quality and latency |
| GPT-4.1 nano | 0.10 | 0.40 | Deprioritise: retirement announced for 23 October 2026 |
| GPT-4o mini | 0.15 | 0.60 | Reference used by the recovered code |
| GPT-5.6 Luna | 0.20 | 1.20 | Current alternative officially recommended for cost-sensitive loads |

GPT-5 nano is marked deprecated on its model card; it is a temporary choice for
cheap testing, not a guarantee of continuity. The lowest rate does not guarantee
the lowest cost per answer: reasoning tokens add to consumption. The code uses
minimal effort and a 1024-token completion cap for that candidate, reasoning
included. An empty answer caused by insufficient budget must be recorded as a
failure; do not raise the budget blindly.

The text models in this table do not process audio directly. Chosen path:
Whisper base on the computer → model over API → gTTS. Local Whisper bills no
minutes to OpenAI. gTTS uses a free external service, and Chatterbox remains the
fully local alternative for speech output.

Illustrative example: 1000 queries with 500 input tokens and 100 billed output
tokens each cost USD 0.065 with GPT-5 nano, USD 0.135 with GPT-4o mini and
USD 0.22 with Luna. This excludes extra reasoning, history beyond the
assumption, transcription or synthesis billed by other services, taxes and the
server. It is not a guaranteed budget.

## Direct speech

GPT-Realtime-2.1 Mini accepts audio in and out. The published audio rate is
USD 10 per million input tokens and USD 20 output; text tokens are billed
separately at USD 0.60 / 2.40. Audio tokens are not equivalent to text tokens:
do not extrapolate minutes from that table without measuring real usage. It
needs a different transport and implementation and is not part of this first
version.

To replace local transcription, the official table lists gpt-4o-mini-transcribe
at USD 0.003/minute, but its retirement is announced for 26 February 2027. The
replacement, gpt-transcribe, is listed at USD 0.0045/minute. Neither has been
integrated.

## Pending verification

The key is configured in `.env`, excluded from Git and with 600 permissions.
Access to `gpt-5-nano-2025-08-07` was verified with ONE minimal query: 11 input
tokens and 11 output, zero reasoning, answer "listo". Estimated cost at the
published rate: USD 0.00000495; this is not a reading of the balance or the
invoice. The available credit is small, so testing is deliberately limited to
what is necessary. Do not run mass comparisons or repeated calls. Conversation
quality and the full path with speech are not yet verified. The script reports
`api_usage` so future consumption can be measured.

## Official sources

- [GPT-5 nano](https://developers.openai.com/api/docs/models/gpt-5-nano)
- [GPT-4.1 nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano)
- [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini)
- [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
- [Pricing](https://developers.openai.com/api/docs/pricing)
- [Model deprecations](https://developers.openai.com/api/docs/deprecations)
- [Realtime 2.1 Mini](https://developers.openai.com/api/docs/models/gpt-realtime-2.1-mini)
- [OpenRouter with the OpenAI SDK](https://openrouter.ai/docs/cookbook/get-started/migrate-to-openrouter)
