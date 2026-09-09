# Plan de recuperación

## 1. Software en la computadora

- Resolver y fijar dependencias en un entorno virtual.
- Separar configuración, transcripción, conversación y generación de voz.
- Crear una prueba con archivo de audio que sustituya al ESP32.
- Comprobar el recorrido completo y medir tiempo por etapa.
- Corregir pregunta duplicada, respuestas de error y validación de WAV.

## 2. Comunicación y hardware existente

- Identificar placa y batería y confirmar cableado.
- Identificar grabaciones y conservar resultados para reintentos.
- Separar captura de audio y envío de red.
- Medir continuidad del audio, latencia y consumo con hardware.

## 3. Servidor personal

El usuario dispone de un servidor personal y prevé alojar allí el servicio más adelante. Todavía no se conocen sistema operativo, recursos, dominio ni forma de acceso. No se ha realizado ninguna conexión o despliegue.

- Elegir ubicación del procesamiento de voz según recursos y latencia.
- Preparar despliegue reproducible y gestión de secretos.
- Incorporar HTTPS, autenticación del dispositivo y límites de peticiones y audio.
- Configurar supervisión, reinicio y comprobación de salud.

## 4. Pulsera compacta

- Fijar autonomía, peso y dimensiones objetivo.
- Elegir placa sin cámara, batería y salida de audio.
- Diseñar PCB y carcasa, fabricar prototipo y probar comodidad.

## Alcance de simulación

Las pruebas con archivos de audio permiten validar el servidor sin ESP32. La simulación de lógica y red del firmware debe mantener el audio desacoplado: no se asume simulación completa del micrófono, amplificador, batería ni comportamiento acústico.
