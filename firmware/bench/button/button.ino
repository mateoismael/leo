// Bench test 3: button on GPIO4 to GND, internal pull-up, same as wristband.ino.
#include <Arduino.h>
const int BUTTON_PIN = 4;

void setup() {
    Serial.begin(115200);
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    Serial.println("Button test ready");
}

void loop() {
    static int last = HIGH;
    int now = digitalRead(BUTTON_PIN);
    if (now != last) {
        Serial.println(now == LOW ? "PRESIONADO" : "SUELTO");
        last = now;
        delay(30);  // ponytail: crude debounce, enough for a bench check
    }
}
