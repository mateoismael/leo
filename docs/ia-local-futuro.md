# Alternativas de IA local para el futuro

Decisión del 2026-09-09: comenzar con el servidor Python y el modelo conversacional por API. Mantener Whisper para transcripción y gTTS para salida de voz. No se implementan todavía estas alternativas.

## Opción futura 1: comandos dentro de la pulsera

Reconocer un conjunto limitado de órdenes y ejecutar funciones locales sin teléfono ni conexión. No equivale a una conversación abierta. ESP-SR es una referencia para explorar, pero sus modelos de comandos documentados se orientan a inglés y chino; el español requiere evaluación específica. Habría que elegir las funciones, el modelo y medir memoria, precisión y consumo.

Fuente: https://github.com/espressif/esp-sr

## Opción futura 2: IA local en el celular

La pulsera captura y reproduce audio; el celular ejecuta reconocimiento de voz, modelo conversacional y síntesis sin necesitar internet una vez instalados los modelos. Sigue siendo necesaria una conexión pulsera–celular; el transporte está por decidir. Hay que comprobar memoria, velocidad, batería y calidad en español en el teléfono concreto.

Qwen3-0.6B es una referencia para evaluar, no una elección confirmada ni un modelo que quepa en el ESP32. La transcripción y la síntesis necesitan sus propios componentes locales.

Fuente: https://huggingface.co/Qwen/Qwen3-0.6B

## Servidor personal

Alojar el servidor Python en el servidor personal sigue siendo una vía de despliegue para la opción principal. Si más adelante también se aloja un modelo allí, dejaría de depender de una API de terceros para esa etapa, pero la pulsera necesitaría conexión para acceder. No se considera un modo sin conexión de la pulsera.
