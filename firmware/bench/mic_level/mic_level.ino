// Bench test 2: INMP441 only. Same pins, port and format as wristband.ino.
// Prints a level bar ~10 times per second to Serial (115200). Speak or clap: it should grow.
#include <Arduino.h>
#include <driver/i2s.h>
#include <math.h>

#define I2S_MIC_WS GPIO_NUM_25
#define I2S_MIC_SD GPIO_NUM_32
#define I2S_MIC_SCK GPIO_NUM_33
#define I2S_MIC_PORT I2S_NUM_0
const int RATE = 16000;

void setup() {
    Serial.begin(115200);
    i2s_config_t cfg = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = 0,
        .dma_buf_count = 8,
        .dma_buf_len = 256,
        .use_apll = false,
    };
    i2s_pin_config_t pins = {
        .mck_io_num = I2S_PIN_NO_CHANGE,
        .bck_io_num = I2S_MIC_SCK,
        .ws_io_num = I2S_MIC_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_MIC_SD,
    };
    esp_err_t err = i2s_driver_install(I2S_MIC_PORT, &cfg, 0, NULL);
    if (err == ESP_OK) err = i2s_set_pin(I2S_MIC_PORT, &pins);
    Serial.printf("I2S mic init: %s\n", esp_err_to_name(err));
}

void loop() {
    static int32_t buf[RATE / 10];  // 100 ms
    size_t got;
    i2s_read(I2S_MIC_PORT, buf, sizeof(buf), &got, portMAX_DELAY);
    int n = got / 4;
    double sum = 0;
    int32_t raw_or = 0;  // all-zero or all-ones words mean no data on SD
    for (int i = 0; i < n; i++) {
        raw_or |= buf[i];
        double s = (buf[i] >> 16) / 32768.0;  // same 16-bit conversion as wristband.ino
        sum += s * s;
    }
    double rms = sqrt(sum / n);
    double db = 20 * log10(rms + 1e-9);
    int bars = constrain((int)((db + 70) / 1.5), 0, 40);  // ponytail: -70..-10 dBFS scale, retune once real levels are seen
    char line[48];
    memset(line, '#', bars); line[bars] = 0;
    Serial.printf("%6.1f dB %s%s\n", db, line, raw_or == 0 ? "  (all zero: check SD/SCK/WS/VDD)" : "");
}
