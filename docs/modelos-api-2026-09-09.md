# Modelos por API — consulta del 9 de septiembre de 2026

Objetivo: aprovechar créditos existentes de OpenAI en una pulsera sin cámara. OpenRouter con algún modelo Gemini es una preferencia futura del usuario; no se afirma superioridad ni menor coste sin comparar modelos y modalidades concretos.

## Comparación

Tarifas de texto por millón de tokens, entrada no almacenada en caché y salida, sin Batch ni herramientas.

| Modelo | Entrada USD | Salida USD | Uso propuesto |
|---|---:|---:|---|
| GPT-5 nano | 0.05 | 0.40 | Candidato inicial de menor tarifa; medir razonamiento, calidad y latencia |
| GPT-4.1 nano | 0.10 | 0.40 | No priorizar: retirada anunciada para el 23 de octubre de 2026 |
| GPT-4o mini | 0.15 | 0.60 | Referencia del código recuperado |
| GPT-5.6 Luna | 0.20 | 1.20 | Alternativa actual recomendada oficialmente para cargas sensibles a coste |

GPT-5 nano aparece deprecado en su ficha; es una elección temporal para pruebas económicas, no una garantía de continuidad. La menor tarifa no garantiza el menor coste por respuesta: los tokens de razonamiento se suman al consumo. El código utiliza esfuerzo mínimo y un tope de 1024 tokens de completado para ese candidato, que incluye razonamiento. Una respuesta vacía por presupuesto insuficiente debe registrarse como fallo; no aumentar el presupuesto a ciegas.

Los modelos de texto de esta tabla no procesan audio directamente. Ruta elegida: Whisper base en la computadora → modelo por API → gTTS. Whisper local no factura minutos a OpenAI, aunque consume recursos de la máquina. gTTS usa un servicio externo; no hace a la solución offline.

Ejemplo ilustrativo: 1000 consultas con 500 tokens de entrada y 100 tokens facturados de salida cada una cuestan USD 0.065 con GPT-5 nano, USD 0.135 con GPT-4o mini y USD 0.22 con Luna. No incluye razonamiento adicional, historial superior al supuesto, transcripción o síntesis cobradas por otros servicios, impuestos ni servidor. No es un presupuesto garantizado.

## Voz directa

GPT-Realtime-2.1 Mini admite audio de entrada y salida. La tarifa de audio publicada es USD 10 por millón de tokens de entrada y USD 20 de salida; los tokens de texto se cobran aparte a USD 0.60 / 2.40. Los tokens de audio no son equivalentes a los de texto: no extrapolar minutos desde esa tabla sin medir el uso. Requiere otro transporte e implementación y no se incorpora en esta primera versión.

Para sustituir la transcripción local, la tabla oficial muestra gpt-4o-mini-transcribe a USD 0.003/minuto, pero su retirada está anunciada para el 26 de febrero de 2027. El reemplazo gpt-transcribe figura a USD 0.0045/minuto. No se han integrado.

## Verificación pendiente

La clave se configuró en `.env`, excluido de Git y con permisos 600. Se verificó acceso a `gpt-5-nano-2025-08-07` con UNA consulta mínima: 11 tokens de entrada y 11 de salida, cero razonamiento, respuesta «listo». Coste estimado por tarifa publicada: USD 0.00000495; no es una lectura del saldo o factura. El usuario dispone de aproximadamente USD 3 y pidió limitarse a pruebas necesarias. No hacer comparativas masivas ni llamadas repetidas. La calidad de conversación y el recorrido completo con voz todavía no están verificados. El script muestra `uso_api` para medir consumos futuros.

## Fuentes oficiales

- [GPT-5 nano](https://developers.openai.com/api/docs/models/gpt-5-nano)
- [GPT-4.1 nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano)
- [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini)
- [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
- [Precios](https://developers.openai.com/api/docs/pricing)
- [Retiradas de modelos](https://developers.openai.com/api/docs/deprecations)
- [Realtime 2.1 Mini](https://developers.openai.com/api/docs/models/gpt-realtime-2.1-mini)
- [OpenRouter con SDK OpenAI](https://openrouter.ai/docs/cookbook/get-started/migrate-to-openrouter)
