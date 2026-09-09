# Pulsera de voz

Asistente de voz con botón y altavoz para llevar en la muñeca, sin cámara. Basado en el proyecto ESP32 Sunday recuperado.

La opción principal es **Whisper en la computadora → modelo conversacional por API → voz con gTTS**. Chatterbox Multilingual queda como alternativa local. Las alternativas futuras de comandos dentro de la pulsera e IA local en el celular están en [IA local](docs/ia-local-futuro.md).

## Estado

Servidor refactorizado con configuración externa, prueba por texto, prueba con WAV y medición por etapa. Mantiene `/audio` para el firmware recuperado. Se verificaron nueve pruebas automatizadas y un recorrido completo simulado: Whisper transcribió la pregunta, GPT-5 nano respondió «Lima» y gTTS generó un WAV válido. La clave está configurada localmente y Whisper base ya está descargado. Falta probar el transporte del firmware ESP32 y el hardware físico; no hay despliegue en nube.

## Preparación

El entorno local ya está preparado. Para otra instalación, desde la raíz del repositorio, con Python 3.9 o posterior:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.in
cp .env.example .env
```

Configurar `OPENAI_API_KEY` en `.env`, fuera de Git. `OPENAI_MODEL` usa `gpt-5-nano` como candidato económico inicial (modelo deprecado; comparar con `gpt-4o-mini` y `gpt-5.6-luna`); `WHISPER_MODEL` conserva `base`. Las pruebas reales de conversación llaman a la API y generan consumo.

`TTS_PROVIDER=gtts` genera rápidamente la respuesta hablada mediante un servicio externo gratuito. Requiere internet, pero no utiliza el saldo de la API conversacional. Para probar la alternativa local recuperada de `ytauto`, cambiar a `TTS_PROVIDER=chatterbox`; `CHATTERBOX_PYTHON` debe apuntar al Python de su entorno independiente. Una referencia WAV limpia de 10–20 segundos puede configurarse en `CHATTERBOX_REFERENCE`; vacío usa la voz predeterminada.

Para procesar audio, instalar además:

```sh
.venv/bin/python -m pip install -r server/requirements-audio.in
```

FFmpeg debe estar instalado y disponible en PATH. Whisper descarga el modelo la primera vez que se usa; esto necesita conexión y espacio local. Al levantar el servidor, `PRELOAD_WHISPER=true` lo carga antes de aceptar audio y evita que la primera pregunta pague ese tiempo de arranque. La prueba por texto no carga Whisper.

## Probar sin ESP32

Revisar el entorno sin llamadas externas (devuelve código 1 si falta algún requisito de audio):

```sh
.venv/bin/python server/leov1ser.py --check
```

Probar solo la conversación por API:

```sh
.venv/bin/python server/leov1ser.py --text "Hola, dime qué puedes hacer en una frase."
```

Probar todo el recorrido con una grabación WAV PCM16 mono a 16 kHz, de 0.2 a 60 segundos:

```sh
.venv/bin/python server/leov1ser.py --audio recordings/pregunta.wav --output recordings/respuesta.wav
```

Se guardará la respuesta hablada y se mostrarán la transcripción, el texto y los tiempos de cada etapa. La primera transcripción incluye la carga de Whisper. `recordings/` se excluye de Git. Chatterbox tarda bastante más y se reserva para pruebas locales que no necesiten una respuesta inmediata.

Para convertir una grabación a ese formato:

```sh
ffmpeg -i mi-grabacion.m4a -ar 16000 -ac 1 -c:a pcm_s16le recordings/pregunta.wav
```

Crear antes la carpeta `recordings` si no existe.

## Servidor y firmware

```sh
.venv/bin/python server/leov1ser.py
```

Escucha por defecto solo en `127.0.0.1:8000`; `/health` comprueba que el proceso responde, no la disponibilidad de proveedores. Para conectar el ESP32 en una red de desarrollo controlada, usar `--host 0.0.0.0`. Copiar `firmware/leov1/config.example.h` a `config.h` y completar red, contraseña y dirección HTTP del servidor.

El endpoint admite bloques PCM16 mono de 16 kHz en POST `/audio` y una petición vacía con `Recording-Status: end`. Devuelve un WAV compatible con la cabecera de 44 bytes esperada por el firmware. Audio inválido devuelve 400, demasiado grande 413, procesamiento ocupado 409 y errores de proveedores 502.

Esta compatibilidad es para **un dispositivo y un proceso**, sin autenticación. No usar múltiples workers ni exponer a internet. Los identificadores de grabación, recuperación de respuestas tras timeout y limpieza de grabaciones abandonadas siguen pendientes. El firmware antiguo espera solo 10 segundos para la respuesta y podría agotar su timeout; la primera prueba debe hacerse por CLI.

## Pruebas automatizadas

```sh
.venv/bin/python -m pip install httpx
.venv/bin/python -m unittest discover -s tests -v
```

Las pruebas sustituyen proveedores externos: verifican historial, formato de audio y protocolo HTTP sin coste de API.

## Organización y procedencia

- `server/leov1ser.py`: versión de trabajo actual.
- `firmware/leov1/`: firmware recuperado con configuración privada separada.
- `legacy/leov1/leov1ser.py`: servidor conversacional original, conservado sin cambios.
- `legacy/transcriptoraud/`: pareja anterior que transcribe y repite.
- `docs/`: análisis histórico, hardware, plan e IA local futura.

El repo local no tiene remoto ni publicación en GitHub. El despliegue futuro en el servidor personal está descrito en el [plan](docs/plan.md); falta preparar autenticación, HTTPS y supervisión. Las dependencias `.in` describen paquetes requeridos; los archivos `.txt`, cuando existan, capturan las versiones verificadas en el entorno de desarrollo, no garantizan compatibilidad con otro sistema.

Se mantiene Chat Completions. Ver [comparación de modelos y costes](docs/modelos-api-2026-09-09.md). Para migrar en el futuro a OpenRouter, configurar `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY` y `OPENROUTER_MODEL`; se utiliza una clave independiente y la URL oficial de ese proveedor. Solo está preparada la ruta de texto, no voz multimodal nativa ni Gemini Live.
