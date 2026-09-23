# Reference hardware

Confirmed goal: a voice wristband, no camera.

| Part | Recovered reference |
|---|---|
| Controller | ESP32; exact board pending |
| Microphone | INMP441 |
| Amplifier | MAX98357; physical variant pending |
| Speaker | Size, impedance and power pending |
| Power | Battery and TP4056 module; regulation, protection and capacity to be identified |
| Input | Button and switch |

## Pins used by both firmwares

- Button: GPIO4, active low with internal pull-up.
- Microphone: WS 25, SD 32, SCK 33; I2S0.
- Amplifier: BCLK 26, LRC 27, DIN 22; I2S1.

This map describes the recovered code, not a check of the physical build. The
power circuit still needs to be reconstructed and must not be inferred from
these signals.

The existing parts will be reused as a reference if they are still available. A
compact camera-less board, possibly an ESP32-S3 with PSRAM, will be evaluated
once the software is recovered. There is no shopping list and no final PCB yet.

## Visual map — 12 September 2026

![Provisional wiring map](images/provisional-wiring.png)

Verified against the firmware GPIOs and the labels in the exported notes. It is
an electrical map by label, not a physical layout: the exact board and modules
still need to be identified from legible photographs before drawing breadboard
positions or rows. The amplifier VIN is pending: the notes say 3V3, but the
current allowed by the board regulator and the speaker impedance and power still
need validating. USB is proposed for the initial test, with no battery and no
TP4056.

SD on the INMP441 is a data signal and goes to GPIO32; SD/MODE on the MAX98357A
is select/enable and is shown at 3V3, as in the original note. Do not confuse
the two. L/R on the microphone tied to GND matches the configured left channel.
GAIN tied to GND preserves the historical configuration. All grounds are common;
there are no two separate grounds, whatever the old note might suggest.

The amplifier output is differential: both speaker wires go to OUT+/OUT−, and
neither goes to GND. The Adafruit reference module asks for a speaker of at
least 4 ohms. [MAX98357A reference pinouts](https://learn.adafruit.com/adafruit-max98357-i2s-class-d-mono-amp/pinouts).
The user's physical variant is still to be confirmed.
