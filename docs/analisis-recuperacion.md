# Análisis del código recuperado

Fecha: 2026-09-09. Fuente: `proyecto_esp32_recuperado.rar`, conservado sin modificar. Los cuatro archivos extraídos también se conservan sin cambios. Revisión estática: no se ha compilado el firmware ni ejecutado el servidor con hardware o servicios externos.

## Dos parejas, dos etapas

| Etapa | Firmware | Servidor | Comportamiento implementado |
|---|---|---|---|
| Transcripción y repetición | `proyecto_esp32_recuperado/transcriptoraud/transcriptoraud.ino` | `proyecto_esp32_recuperado/transcriptoraud/micampser.py` | Audio → Whisper base → texto → gTTS → audio que repite lo dicho |
| Asistente conversacional | `proyecto_esp32_recuperado/leov1/leov1.ino` | `proyecto_esp32_recuperado/leov1/leov1ser.py` | Audio → Whisper base → GPT-4o-mini por API → gTTS → respuesta hablada |

Por funcionalidad, `leov1` parece la evolución de `transcriptoraud`; no hay historial de versiones que confirme la cronología. No son cuatro revisiones independientes de un mismo programa: son dos parejas complementarias de firmware y servidor. La etapa de transcripción resulta útil para probar micrófono, transporte y altavoz sin la llamada al modelo conversacional.

## Arquitectura recuperada

1. Al mantener pulsado el botón, el ESP32 lee el INMP441 por I2S a 16 kHz y convierte las muestras de 32 a 16 bits.
2. Envía bloques PCM mediante peticiones HTTP POST a `/audio` en un servidor de la red local.
3. Al soltar el botón, envía otra petición con `Recording-Status: end`.
4. Python/FastAPI acumula el audio y ejecuta Whisper `base` en la máquina que aloja el servidor.
5. En `leov1`, el texto se envía a la API de OpenAI con el identificador `gpt-4o-mini` y un historial breve mantenido en memoria.
6. gTTS genera voz en español; librosa y wave la convierten a WAV mono, PCM de 16 bits y 16 kHz.
7. La respuesta HTTP contiene ese WAV; el ESP32 omite los primeros 44 bytes y lo reproduce por MAX98357 y altavoz.

El firmware usa Wi-Fi/HTTP, no A2DP ni USB para transportar voz. El servidor escucha en el puerto 8000. Las direcciones locales están fijadas en el firmware: el código no identifica por sí solo la computadora concreta que ejecutaba Python. La conexión de red podía proporcionarla un teléfono, pero eso no significa que Python corriera en el teléfono. La IA conversacional no se ejecuta dentro del ESP32.

## Cableado respaldado por ambos firmwares

| Señal | GPIO ESP32 |
|---|---|
| Botón, activo a GND con pull-up interno | 4 |
| Micrófono WS / SD / SCK | 25 / 32 / 33 |
| Amplificador BCLK / LRC / DIN | 26 / 27 / 22 |

Se utilizan I2S0 para el micrófono e I2S1 para el altavoz. Esto resuelve la diferencia de las notas: los dos programas conjuntos configuran LRC del amplificador en GPIO27. No prueba que el cableado físico conservado coincida. La cámara de Notion continúa entrando en conflicto con DIN del amplificador en GPIO22 si se combinan sin reasignación.

## Qué aporta leov1

- Consulta al modelo conversacional y contexto en memoria; la otra versión solo repite la transcripción.
- Instrucciones para respuestas breves y un segundo intento si la respuesta no termina en puntuación.
- Buffers del altavoz más grandes, más mensajes de diagnóstico, timeout HTTP de 10 segundos, espera de cabecera de 10 segundos y límite de reproducción de 30 segundos.
- Hasta tres intentos para la petición final cuando no recibe HTTP 200.
- Cabeceras explícitas de longitud y cierre de conexión en la respuesta WAV.

## Aspectos a corregir al recuperar el funcionamiento

1. **Reintentos sin identificación de grabación.** El servidor vacía el buffer antes de transcribir y generar voz. Si la petición final agota el timeout mientras procesa, reenviarla no recupera automáticamente la misma respuesta. Conviene identificar cada grabación y conservar su resultado.
2. **Respuestas JSON tratadas como audio.** El servidor también devuelve HTTP 200 con JSON cuando falta audio, no hay texto o se produce un error. El firmware interpreta cualquier 200 final como WAV. Debe comprobar tipo de respuesta, estado y formato de audio.
3. **Captura interrumpida por red.** Cada bloque de hasta 1024 muestras, unos 64 ms de audio, se envía con un POST bloqueante. La lectura del micrófono espera a la red y puede perder continuidad si el retraso supera lo que absorben los buffers. Separar captura y transmisión, con una cola acotada, permitiría medir y controlar este problema.
4. **Pregunta duplicada.** `get_openai_response` añade la pregunta al historial y vuelve a añadirla al construir `messages`.
5. **Estado global y sin límite de grabación.** Buffer e historial se comparten en el proceso, sin identificación de dispositivo ni tamaño máximo del audio. Antes de ampliar el uso deben delimitarse sesiones y recursos.
6. **Reproducción frágil.** Se asume cabecera WAV fija de 44 bytes; no se usa la longitud del cuerpo como condición de finalización ni se valida una reproducción completa. El límite de 30 segundos termina devolviendo éxito incluso si cortó el audio. Tras HTTP 200 se sale de los reintentos aunque falle la reproducción.
7. **Configuración por recuperar.** No se incluyen versiones de librerías, manifiesto de dependencias ni modelo exacto de placa. El servidor carga la clave de API desde el entorno; los firmwares contienen configuración Wi-Fi literal, que no se reproduce en este informe y deberá separarse al crear una versión compartible.

Estos puntos se deducen del código; no son fallos observados en una prueba física actual.

## Consecuencias para el rediseño

La separación entre accesorio y procesamiento externo ya existía. El trabajo de portabilidad consiste en decidir dónde alojar el servidor fuera de la PC antigua, mejorar el transporte y compactar la electrónica y alimentación.

La restricción de Bluetooth Classic mencionada al revisar el ejemplo de Notion no bloquea estos firmwares Wi-Fi. Un ESP32-S3 puede volver a evaluarse como candidato, pero exige adaptar pines, drivers y validar el audio; no se ha comprobado como sustituto directo.

Orden propuesto: recuperar la pareja `leov1` en un entorno reproducible, utilizar `transcriptoraud` para diagnóstico si hace falta, medir latencia/consumo y después diseñar PCB y carcasa. Faltan dimensiones, batería exacta, placa exacta y objetivo de autonomía para dimensionar gafas o pulsera. No hay cámara integrada en ninguno de estos cuatro archivos.

## Validación realizada

- Lectura de los cuatro archivos y comparación de ambos firmwares y servidores.
- Análisis sintáctico con `ast.parse` satisfactorio para ambos Python, sin importarlos ni ejecutar llamadas externas.
- Pendiente: instalación de dependencias, compilación para placa identificada, pruebas de audio y alimentación en hardware y verificación de servicios actuales.
