# Firmware y transporte — 12 de septiembre de 2026

## Alcance

ESP32 clásico, micrófono INMP441 y amplificador MAX98357A con los pines históricos. No se ha conectado, grabado ni flasheado una placa. La Mac sigue usando `probar_mac.py` y el servidor conserva `/audio` original. El firmware actualizado necesita también el servidor actualizado porque usa rutas nuevas.

## Captura y red

La tarea principal lee I2S con espera máxima de 200 ms y encola bloques PCM16 de hasta 2048 bytes. Una tarea FreeRTOS independiente envía los bloques. La cola contiene 16 bloques (aproximadamente 32 KiB y 1.024 segundos de audio). No se espera al HTTP dentro de la captura.

Si la cola se llena, el micrófono falla o el envío agota sus tres intentos, se detiene y descarta la grabación; no se consulta al modelo con ese audio incompleto. Esto permite absorber retrasos breves, no garantizar continuidad con cualquier red. Al soltar el botón se espera a que terminen los envíos encolados. Límite: 60 segundos de voz. Mientras se procesa o reproduce no se acepta otra grabación. La interrupción por botón todavía no forma parte de este cambio.

## Rutas v2

El valor `AUDIO_SERVER_URL` sigue siendo `http://HOST:8000/audio`. Se añaden estos sufijos:

| Método | Sufijo | Función |
|---|---|---|
| POST | `/recordings/{id}/start` | Crear una sesión; repetir no borra el audio recibido |
| POST | `/recordings/{id}/chunks/{seq}` | PCM numerado desde cero; repetir el mismo bloque no lo duplica |
| POST | `/recordings/{id}/end?blocks=N` | Verificar que llegaron todos los bloques y producir o recuperar respuesta |
| POST | `/recordings/{id}/abort` | Descartar una carga fallida antes de consultar la API |

Bloques fuera de orden o duplicados con contenido distinto: 409. Grabación demasiado larga: 413. ID inexistente/caducado al finalizar: 404; no se genera otra consulta automáticamente. La secuencia y el ID se conservan durante los reintentos.

La respuesta se genera en una tarea del servidor que continúa si el receptor se desconecta. Repetir `end` recupera los mismos fragmentos desde el principio, sin otra llamada al proveedor. Puede volver a escucharse una parte que ya sonó; todavía no hay reanudación desde una posición exacta.

Caché local en memoria: máximo cuatro sesiones; caducidad de cinco minutos sin actividad para cargas o desde terminación para resultados. Si hace falta espacio, se expulsa el resultado terminado más antiguo. Las sesiones en procesamiento no se expulsan. La caché no sobrevive al reinicio del servidor y no proporciona deduplicación permanente. Mantener un solo proceso/worker y acceso por red local: no se añade autenticación en esta fase.

## Audio y detección de cortes

HTTP/1.0, cabecera `X-Audio-Format: pcm-s16le-framed-v1`. Cada trama tiene longitud uint32 little-endian y luego entre 2 y 2048 bytes PCM16 mono 16 kHz. Longitud cero significa éxito y fin completo. `0xffffffff` significa fallo. No se reproduce la cabecera como audio.

El ESP32 exige fin explícito: una conexión que se cierre antes, una trama incompleta o un error no cuentan como éxito. Lee incluso bytes partidos por TCP sin romper muestras de 16 bits. La espera se limita a 20 segundos sin datos y 90 segundos totales, incluyendo cuando el socket está conectado pero vacío. Cada escritura I2S tiene espera de 500 ms, comprueba escrituras parciales y drena la cola DMA antes de parar.

## Verificación reproducible

Pruebas Python (25 al añadir este protocolo), incluidas una conexión HTTP/1.0 real por loopback con desconexión a mitad de respuesta y recuperación, y proveedores simulados:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Pruebas C++ del mismo lector que usa el firmware: espera sin datos, bytes fragmentados, desconexión parcial, límite global y desbordamiento de millis:

```sh
mkdir -p .cache
c++ -std=c++17 -Wall -Wextra -Werror tests/test_transport.cpp -o .cache/test_transport
.cache/test_transport
```

Compilación local, con configuración de ejemplo y sin subir nada a la placa:

```sh
.venv/bin/python scripts/compile_firmware.py
```

Herramientas instaladas en `.cache/arduino/`, ignoradas por Git: Arduino CLI 1.5.1 y núcleo `esp32:esp32@3.3.11`. Perfil objetivo: `esp32:esp32:esp32` (ESP32 Dev Module genérico). No confirma el modelo exacto de placa del usuario.

Se intentó primero 2.0.17; sus binarios Intel no podían ejecutarse en esta Mac sin Rosetta. Se pasó a 3.3.11 con compilador ARM64. El auxiliar ctags distribuido también era Intel: se compiló localmente desde `arduino/ctags`, etiqueta `5.8-arduino11`, commit `abc8fca7499f44c725122881cd380a88c37abe0e`. Para el SDK de macOS actual se renombró su macro `__unused__` a `CTAGS_UNUSED` en los fuentes locales, evitando colisión con la macro del sistema. El script pasa su ruta con `runtime.tools.ctags.path`.

En otra Mac, instalar Arduino CLI, configurar el índice `https://espressif.github.io/arduino-esp32/package_esp32_index.json` e instalar el núcleo 3.3.11. Las rutas de datos, descargas y usuario deben apuntar a `.cache/arduino/{data,downloads,user}` en `arduino-cli.yaml`. El ctags nativo solo es necesario si el paquete de esa máquina presenta la incompatibilidad Intel descrita.

Fuentes de herramientas: [Arduino CLI](https://docs.arduino.cc/arduino-cli/installation/), [migración ESP32](https://docs.espressif.com/projects/arduino-esp32/en/latest/migration_guides/2.x_to_3.0.html), [ctags de Arduino](https://github.com/arduino/ctags/tree/5.8-arduino11).

## Pendiente físico

Confirmar placa y pines, probar Wi-Fi lento y agotamiento de cola, continuidad de voz, reproducción completa y consumo. La compilación no verifica el comportamiento eléctrico ni la temporización real de I2S/FreeRTOS. No se gastó saldo de API en estas pruebas.
