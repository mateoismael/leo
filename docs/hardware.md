# Hardware de referencia

Objetivo confirmado: pulsera de voz, sin cámara.

| Parte | Referencia recuperada |
|---|---|
| Controlador | ESP32; placa exacta pendiente |
| Micrófono | INMP441 |
| Amplificador | MAX98357; variante física pendiente |
| Altavoz | Tamaño, impedancia y potencia pendientes |
| Alimentación | Batería y módulo TP4056; identificar regulación, protección y capacidad |
| Entrada | Botón e interruptor |

## Pines de ambos firmwares

- Botón: GPIO4, activo a GND con pull-up interno.
- Micrófono: WS 25, SD 32, SCK 33; I2S0.
- Amplificador: BCLK 26, LRC 27, DIN 22; I2S1.

Este mapa describe el código recuperado, no una comprobación del montaje físico. El circuito de alimentación sigue pendiente de reconstrucción y no se debe inferir a partir de estas señales.

Se utilizarán las piezas existentes como referencia si siguen disponibles. Una placa compacta sin cámara, posiblemente ESP32-S3 con PSRAM, se evaluará después de recuperar el software. Aún no hay lista de compras ni PCB final.
