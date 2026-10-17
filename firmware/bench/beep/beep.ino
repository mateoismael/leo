// Bench test 1: MAX98357A + speaker only. Same pins and I2S port as wristband.ino.
// Plays a 440 Hz tone for 1 s every 2 s and prints to Serial (115200).
#include <Arduino.h>
#include <driver/i2s.h>
#include <math.h>

#define I2S_SPK_BCLK GPIO_NUM_26
#define I2S_SPK_LRC GPIO_NUM_27
#define I2S_SPK_DIN GPIO_NUM_22
#define I2S_SPK_PORT I2S_NUM_1
const int RATE = 16000;
const float VOLUME = 0.2;  // ponytail: calibration knob; raise if too quiet, lower if it distorts

void setup() {
    Serial.begin(115200);
    i2s_config_t cfg = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = 0,
        .dma_buf_count = 8,
        .dma_buf_len = 256,
        .use_apll = false,
    };
    i2s_pin_config_t pins = {
        .mck_io_num = I2S_PIN_NO_CHANGE,
        .bck_io_num = I2S_SPK_BCLK,
        .ws_io_num = I2S_SPK_LRC,
        .data_out_num = I2S_SPK_DIN,
        .data_in_num = I2S_PIN_NO_CHANGE,
    };
    esp_err_t err = i2s_driver_install(I2S_SPK_PORT, &cfg, 0, NULL);
    if (err == ESP_OK) err = i2s_set_pin(I2S_SPK_PORT, &pins);
    Serial.printf("I2S speaker init: %s\n", esp_err_to_name(err));
}

void loop() {
    static int16_t buf[256];
    static uint32_t n = 0;
    Serial.println("beep");
    for (int i = 0; i < RATE / 256; i++) {  // ~1 s of tone
        for (int j = 0; j < 256; j++, n++)
            buf[j] = (int16_t)(VOLUME * 32767 * sinf(2 * M_PI * 440 * n / RATE));
        size_t written;
        i2s_write(I2S_SPK_PORT, buf, sizeof(buf), &written, portMAX_DELAY);
    }
    i2s_zero_dma_buffer(I2S_SPK_PORT);
    delay(1000);
}
