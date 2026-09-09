# Pulsera de voz

Asistente de voz para llevar en la muñeca, con botón para hablar y respuesta por altavoz. Sin cámara. Basado en el prototipo ESP32 recuperado del proyecto Sunday.

## Estado

Repositorio local inicial. Se conserva el comportamiento del código recuperado, con la configuración Wi-Fi separada de los programas. El servidor todavía no se ha ejecutado en este entorno ni se ha compilado o probado el firmware con hardware. No está listo para exponerse a internet.

## Arquitectura actual

Botón y micrófono INMP441 → ESP32 → Wi-Fi/HTTP → servidor Python/FastAPI → Whisper base → API del modelo conversacional → gTTS → audio WAV → ESP32 y MAX98357/altavoz.

El procesamiento pesado ocurre fuera de la pulsera. Más adelante el servidor Python podrá alojarse en el servidor personal del propietario; subir el repositorio por sí solo no despliega el servicio.

## Carpetas

| Ruta | Contenido |
|---|---|
| `firmware/leov1/` | Firmware principal recuperado y plantilla de configuración |
| `server/` | Servidor conversacional recuperado e inventario de dependencias |
| `legacy/transcriptoraud/` | Pareja anterior de transcripción y repetición, para referencia y diagnóstico |
| `docs/` | Análisis de recuperación, hardware y próximos pasos |

## Configuración

- Copiar `.env.example` a `.env` en la raíz y configurar `OPENAI_API_KEY` antes de ejecutar el servidor. La clave se utiliza para llamadas a la API, que pueden generar consumo.
- Copiar `firmware/leov1/config.example.h` a `firmware/leov1/config.h` y completar red, contraseña y dirección del servidor local.
- La versión anterior tiene su propia plantilla `config.example.h`.
- `.env`, `config.h`, audios y modelos descargados quedan excluidos de Git.

`server/requirements.in` recoge las dependencias encontradas, todavía sin versiones verificadas. El siguiente trabajo es preparar un entorno reproducible, incluyendo FFmpeg para el audio, y una prueba con grabaciones. No se presenta aún una receta de instalación validada.

## Próximo objetivo

Probar el recorrido voz → transcripción → IA → respuesta hablada desde la computadora usando un archivo de audio, sin requerir ESP32. Después corregir el protocolo y medir latencia antes de miniaturizar el hardware. Ver [plan](docs/plan.md).

## GitHub y servidor personal

Este repositorio es independiente del repositorio que contiene la carpeta superior. No tiene remoto ni se ha publicado. Cuando se cree el repositorio de GitHub se añadirá su URL como `origin`.

El despliegue posterior en el servidor personal requerirá configuración externa de secretos, HTTPS y autenticación del dispositivo, límites de uso y almacenamiento, y supervisión del proceso. El endpoint recuperado carece de autenticación; mantenerlo en un entorno de desarrollo controlado hasta implementar estas partes.

## Procedencia

Los archivos originales y los archivos comprimidos se conservan fuera de este repositorio, en la carpeta del proyecto. Aquí se incluyen copias del código: los firmwares tienen únicamente la extracción de configuración privada a `config.h`; los dos servidores Python se conservan sin cambios. El análisis histórico mantiene las rutas originales para facilitar su identificación.
