# Plan de recuperación

Decisión actual: comenzar con IA conversacional por API. Las dos alternativas locales se conservan para después en [IA local futura](ia-local-futuro.md).

## 1. Software en la computadora

- Instaladas dependencias de servidor y Whisper en `.venv`; versiones del entorno macOS/Python 3.9 guardadas en `server/requirements-dev-lock.txt`.
- Implementado: configuración externa y etapas separadas de transcripción, conversación y voz.
- Implementado: CLI con `--text`, `--audio` y `--check`, sin ESP32.
- Verificada una consulta mínima real a GPT-5 nano.
- Verificado el recorrido completo sin ESP32 con voz sintetizada: Whisper transcribió correctamente, GPT-5 nano respondió «Lima» y gTTS produjo el WAV final. Tiempos de la primera ejecución: 5.891 s de transcripción, 3.522 s de API y 0.548 s de voz. Uso: 47 tokens de entrada y 11 de salida; coste estimado de la llamada: USD 0.00000675 según la tarifa consultada.
- Siguiente: probar el servidor en ejecución y simular el envío HTTP por bloques y la señal de fin del firmware.
- Integrado y probado Chatterbox Multilingual como alternativa local. gTTS continúa como salida predeterminada por su menor latencia.
- Prueba real de gTTS: generó 2.42 segundos de audio compatible en 1.44 segundos, sin llamada al modelo conversacional.
- Implementado: pregunta sin duplicación, estados HTTP de error y validación WAV/PCM. Nueve pruebas automatizadas con proveedores sustituidos y validación completa por CLI.

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
