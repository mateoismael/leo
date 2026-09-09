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
- Once pruebas automatizadas validan el servidor sin consumir API.

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
