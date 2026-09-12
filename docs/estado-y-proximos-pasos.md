# Estado y próximos pasos

Actualizado el 9 de septiembre de 2026.

## Objetivo actual

Construir una pulsera de voz sin cámara. El ESP32 captura y reproduce audio; una computadora o servidor ejecuta Whisper local, consulta el modelo conversacional por API y genera la respuesta hablada con gTTS. La primera versión necesita Wi-Fi.

## Lo que funciona

- El servidor recibe PCM16 mono a 16 kHz mediante `POST /audio`.
- Whisper `base` se carga al levantar el servidor. Una pregunta no espera la carga inicial.
- El modo original todavía puede devolver un WAV completo.
- El modo nuevo se activa con `Response-Mode: stream` y devuelve PCM sin cabecera.
- La respuesta del modelo se recibe token por token y se divide en frases.
- Un hilo sigue recibiendo texto mientras gTTS sintetiza las frases disponibles.
- El firmware actualizado solicita el flujo mediante HTTP/1.0 y reproduce los bytes PCM conforme llegan.
- Dieciséis pruebas automatizadas validan servidor y captura simulada sin consumir API.

## Pruebas reales

La prueba de una sola palabra recorrió Whisper, GPT-5 nano y gTTS:

| Medición | Resultado |
|---|---:|
| Carga previa de Whisper | 2.068 s |
| Transcripción caliente | 0.44–0.70 s |
| Primer audio, respuesta «Lima» | 4.430 s |
| Audio completo | 4.430 s |
| Coste estimado de API | USD 0.00000675 |

Una respuesta de tres frases comprobó el solapamiento:

| Medición | Resultado |
|---|---:|
| Primer fragmento de audio | 4.580 s |
| Audio completo generado | 8.089 s |
| Anticipación obtenida | 3.509 s |
| Coste estimado de API | USD 0.00003575 |

El streaming no acorta una respuesta de una sola frase: permite empezar a reproducir respuestas largas antes de que terminen. Las dos llamadas reales de esta implementación costaron aproximadamente USD 0.00004250 en total.

Los WAV de comprobación quedaron en `recordings/`, fuera de Git. FFprobe confirmó PCM16 mono a 16 kHz. También se levantó un servidor local temporal y se comprobó que una petición HTTP/1.0 recibe un cuerpo PCM limpio, delimitado por cierre de conexión y sin bytes de codificación chunked.

## Lo que todavía no está comprobado

- No hay un ESP32 conectado, por lo que todavía no se ha oído el flujo en el INMP441, MAX98357A y altavoz físicos.
- No está instalado `arduino-cli` ni PlatformIO en esta computadora; el firmware se revisó pero no se compiló aquí.
- Hay que confirmar que la versión de la biblioteca `HTTPClient` instalada para la placa respeta `useHTTP10(true)` como en la prueba del servidor.
- gTTS genera cada frase completa antes de entregarla. Es streaming entre frases, no dentro de una palabra o frase.
- Varias llamadas a gTTS pueden introducir pequeñas diferencias de ritmo. Se insertan 80 ms de silencio entre frases.
- Si la API o gTTS falla después de comenzar el cuerpo HTTP, ya no es posible sustituirlo por un error JSON; el firmware verá una conexión interrumpida.
- La captura recuperada todavía hace un POST bloqueante aproximadamente cada 64 ms. La red podría causar huecos en la grabación y debe medirse físicamente.

## Próximos pasos

1. Compilar el firmware para el modelo exacto de ESP32 y corregir cualquier diferencia de la biblioteca instalada.
2. Hacer una prueba de mesa con alimentación USB, micrófono, amplificador y altavoz; medir desde que se suelta el botón hasta la primera muestra reproducida.
3. Comparar el modo WAV y el modo streaming con preguntas de una y varias frases.
4. Separar captura y red en el ESP32 mediante una cola para que una petición HTTP lenta no interrumpa el micrófono.
5. Añadir un identificador de grabación y conservar temporalmente la respuesta para recuperar fallos o reintentos sin repetir una llamada pagada.
6. Ajustar la división de frases y el límite de respuesta usando grabaciones reales en español.
7. Cuando el recorrido sea estable, elegir la placa final, medir consumo y diseñar una PCB compacta sin cámara.
8. Preparar el despliegue en el servidor personal con HTTPS, autenticación del dispositivo y límites de uso.

## Criterio para continuar

La siguiente decisión depende de la prueba física. Si el primer sonido llega cerca de la medición del servidor, se conserva este diseño. Si aparecen cortes, bytes extra o bloqueos, se documentará el resultado aquí y se probará primero el transporte de audio; cambiar Whisper no resolvería esos fallos.

## Pruebas en Mac y conversación interrumpible

Se añadió `server/probar_mac.py`. Desde la raíz del repositorio:

```sh
.venv/bin/python server/probar_mac.py
```

Ahora permite hablar por el micrófono de la Mac: ESPACIO inicia, ESPACIO termina; `q` sale y Ctrl+C interrumpe la prueba. Cada pregunta llama a la API y usa gTTS. Para escribir en lugar de hablar, usar `--chat`. El historial se mantiene mientras siga abierto y el último audio se guarda en `recordings/prueba-mac.wav`.

```sh
# Sin API ni internet: reproduce una respuesta ya guardada.
.venv/bin/python server/probar_mac.py --replay recordings/respuesta-streaming.wav
# Pregunta grabada: transcribe con Whisper y consulta la API.
.venv/bin/python server/probar_mac.py --audio recordings/pregunta-simulada.wav
```

Verificación adicional: 13 pruebas pasan, incluyendo cierre de la cola productora al cancelar y conservación del bloqueo durante la transmisión HTTP. Antes el endpoint soltaba ese bloqueo al devolver la respuesta, permitiendo superponer conversaciones. Se corrigió. Una lectura activa de la API puede tardar hasta su timeout antes de terminar; no se garantiza cancelación instantánea de una solicitud remota.

La reproducción local del WAV «Lima» abrió ffplay sin errores fuera del sandbox. Dentro del sandbox falló el acceso al dispositivo de audio. Esta comprobación confirma el funcionamiento del reproductor, no una medición acústica con micrófono.

Precisión sobre las mediciones anteriores: 4.580 s y 8.089 s corresponden a una prueba desde texto, sin Whisper ni transporte ESP32. La diferencia de 3.509 s es entre primer PCM y último PCM de la misma ejecución, no una comparación A/B contra el modo WAV. El altavoz añade latencia de reproducción. La prueba de «Lima» sí incluyó transcripción (0.670 s), primer PCM a 4.433 s y carga previa de 2.006 s. No hay todavía una medición de voz física de extremo a extremo.

Interrupción automática de voz (barge-in), propuesta para después de validar el recorrido básico:

1. Primero permitir pulsar el botón mientras habla para detener reproducción, descartar audio pendiente e iniciar una nueva grabación. El firmware actual aún no implementa esa interrupción.
2. Después mantener escucha durante la reproducción, detectar voz (VAD) y cancelar el turno cuando el usuario tome la palabra.
3. Añadir cancelación de eco para no confundir el altavoz con la voz del usuario y ajustar detección de final de turno para tolerar pausas.
4. Conservar en el historial qué parte de la respuesta se escuchó y añadir la corrección del usuario antes de generar la siguiente respuesta. Actualmente se guarda el texto generado completo, no el audio efectivamente escuchado.

Esto mejora la naturalidad y permite correcciones, pero no acelera por sí solo la API. No se incorpora escucha permanente en esta fase. Referencia consultada: https://elevenlabs.io/docs/eleven-agents/customization/conversation-flow

## Captura del micrófono implementada

Se instaló sounddevice 0.5.6 en el entorno local. macOS reconoce el micrófono integrado (índice 0) y las bocinas (índice 1). La captura usa la frecuencia nativa del dispositivo, mono PCM16, y FFmpeg convierte a 16 kHz. Whisper permanece cargado durante la conversación. La captura se cierra antes de transcribir y reproducir la respuesta. El límite es 60 segundos; errores de captura o grabaciones demasiado cortas no se envían a la API.

Se verificaron 16 pruebas: incluyen conversión real de PCM simulado de 48 a 16 kHz, rechazo de grabaciones cortas y rechazo de pérdida de muestras. La enumeración de dispositivos se probó fuera del sandbox. Falta que el usuario permita el micrófono para Terminal y pruebe su voz; no se grabó el entorno durante estas verificaciones ni se hicieron nuevas llamadas pagadas. No se ha medido aún la latencia acústica completa.


## Corte de las primeras palabras reportado por el usuario

Síntoma: el texto está completo, pero al empezar a sonar parece faltar parte de la primera palabra. El WAV guardado comienza con una frase reconocible al retranscribir localmente sus primeros siete segundos. Esto apunta a la reproducción, pero no demuestra que la síntesis esté libre de cortes; falta confirmación acústica del usuario.

Se sustituyó ffplay en `probar_mac.py` por sounddevice/PortAudio. El dispositivo se abre antes de consumir el generador, emite 200 ms de silencio de preparación y permanece activo durante las pausas. La cola conserva los bytes PCM pendientes: si no llega la siguiente frase, sale silencio y luego continúa desde su primera muestra. El WAV guardado conserva el PCM original, sin ese silencio de preparación. Se esperan los últimos datos antes de cerrar y se informa de underflows detectados por PortAudio.

Verificaciones: 18 pruebas pasan. Las nuevas pruebas comparan bytes del inicio y final y comprueban continuidad después de una pausa. Se reprodujo «Lima» fuera del sandbox sin errores ni underflows reportados y sin nuevas llamadas API. El sandbox no permite abrir la salida de audio. No se afirma que el problema acústico esté resuelto hasta que el usuario lo compruebe. El control del micrófono sigue siendo ESPACIO para iniciar/terminar y q para salir.

Prueba gratuita con la respuesta guardada, sin sobrescribirla:

```sh
.venv/bin/python server/probar_mac.py --replay recordings/prueba-mac.wav --output recordings/revision-audio.wav
```

Pendiente independiente: el modelo ofreció buscar información, pero el programa no tiene herramienta de búsqueda web. Las respuestas históricas sobre el libro de Coelho no se han verificado y no deben tratarse como resultados de una búsqueda.


## Confirmación de uso — 12 de septiembre de 2026

El usuario indica que cree que desapareció el corte al inicio del audio después del cambio a sounddevice/PortAudio. Se registra como mejora percibida en uso real, con confirmación provisional; falta observar si reaparece en próximas conversaciones. No es una medición acústica controlada ni valida todavía la reproducción en ESP32.
