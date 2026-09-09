# Voz local con Chatterbox

El motor se recuperó de `../ytauto/voz/tts_chatterbox.py`. Usa Chatterbox
Multilingual 0.1.7, publicado bajo licencia MIT. El modelo está almacenado en la
caché del usuario y ocupa aproximadamente 3 GB; no se copia al repositorio.

Para evitar incompatibilidades, el servidor llama a `server/tts_chatterbox.py`
mediante el entorno Python existente de Chatterbox. En la máquina actual la
importación necesita `NUMBA_CACHE_DIR`; el servidor lo asigna a `.cache/numba`.
La voz se normaliza a WAV PCM16 mono a 16 kHz para el firmware ESP32.

La adaptación conserva las partes útiles para respuestas cortas: división del
texto, `torch.inference_mode`, español y referencia de voz opcional. Mantiene la
marca de agua predeterminada del modelo. No copia audios ni modelos de `ytauto`.

En las mediciones históricas de `ytauto`, CPU tardó cerca de 3.7 segundos de
cómputo por segundo de audio y MPS ocasionó swap. El servidor usa CPU y limita
cada generación a cinco minutos. Actualmente carga el modelo para cada
respuesta; una futura versión persistente reduciría la latencia inicial.

Prueba del 2026-09-09: «Prueba de voz lista.» produjo 1.92 segundos de audio.
La ejecución completa tomó aproximadamente medio minuto, incluida la carga del
modelo. El resultado original fue mono a 24 kHz y se convirtió correctamente a
WAV PCM16 mono a 16 kHz para el ESP32. No se usó la API conversacional ni se
consumieron créditos en esta prueba.

Fuente y licencia: https://github.com/resemble-ai/chatterbox
