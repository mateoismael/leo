#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <driver/i2s.h>
#include <atomic>
#include "config.h"
#include "transport.h"

const int BUTTON_PIN = 4;
const int SAMPLE_BUFFER_SIZE = 1024;
#define I2S_MIC_WS GPIO_NUM_25
#define I2S_MIC_SD GPIO_NUM_32
#define I2S_MIC_SCK GPIO_NUM_33
#define I2S_MIC_PORT I2S_NUM_0
#define I2S_SPK_BCLK GPIO_NUM_26
#define I2S_SPK_LRC GPIO_NUM_27
#define I2S_SPK_DIN GPIO_NUM_22
#define I2S_SPK_PORT I2S_NUM_1

const uint32_t HTTP_TIMEOUT = 10000;
const int MAX_RETRIES = 3;
QueueHandle_t audioQueue;
std::atomic<bool> networkBusy{false};
std::atomic<bool> recordingFailed{false};
char recordingId[50];
bool isRecording = false;
bool waitForRelease = false;
uint32_t sequence = 0;
uint32_t capturedBytes = 0;
uint32_t recordingStarted = 0;

void networkTask(void*);

void setup() {
    Serial.begin(115200);
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    // setup does not wait indefinitely for the network to appear.
    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) delay(100);
    // Configure I2S for the INMP441
    i2s_config_t i2s_mic_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = 16000,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = SAMPLE_BUFFER_SIZE,
        .use_apll = false,
        .fixed_mclk = 0
    };

    i2s_pin_config_t mic_pin_config = {
        .mck_io_num = I2S_PIN_NO_CHANGE,
        .bck_io_num = I2S_MIC_SCK,
        .ws_io_num = I2S_MIC_WS,
        .data_out_num = -1,
        .data_in_num = I2S_MIC_SD
    };

    // Configure I2S for the MAX98357A with tuned buffers
    i2s_config_t i2s_spk_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = 16000,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,          // Ajustado a 8
        .dma_buf_len = 1024,         // Set to 1024 (maximum allowed)
        .use_apll = false,
        .tx_desc_auto_clear = true
    };

    i2s_pin_config_t spk_pin_config = {
        .mck_io_num = I2S_PIN_NO_CHANGE,
        .bck_io_num = I2S_SPK_BCLK,
        .ws_io_num = I2S_SPK_LRC,
        .data_out_num = I2S_SPK_DIN,
        .data_in_num = -1
    };

    // Install I2S drivers
    Serial.println("Configuring I2S for the microphone...");
    ESP_ERROR_CHECK(i2s_driver_install(I2S_MIC_PORT, &i2s_mic_config, 0, NULL));
    ESP_ERROR_CHECK(i2s_set_pin(I2S_MIC_PORT, &mic_pin_config));
    
    Serial.println("🎯 Configurando I2S para altavoz...");
    ESP_ERROR_CHECK(i2s_driver_install(I2S_SPK_PORT, &i2s_spk_config, 0, NULL));
    ESP_ERROR_CHECK(i2s_set_pin(I2S_SPK_PORT, &spk_pin_config));
    
    // Clear buffers
    i2s_zero_dma_buffer(I2S_MIC_PORT);
    i2s_zero_dma_buffer(I2S_SPK_PORT);

    i2s_stop(I2S_MIC_PORT);
    i2s_stop(I2S_SPK_PORT);
    audioQueue = xQueueCreate(16, sizeof(AudioBlock));
    if (!audioQueue || xTaskCreate(networkTask, "audio-network", 8192, nullptr, 1, nullptr) != pdPASS) {
        Serial.println("No se pudo reservar la cola/tarea de audio.");
        while (true) delay(1000);
    }
    Serial.println("Ready: hold to speak, release to get an answer.");
}

String endpoint(const String& suffix) {
    return String(AUDIO_SERVER_URL) + "/recordings/" + recordingId + suffix;
}

// The same ID and sequence are kept across every retry.
bool sendBlock(const String& suffix, const uint8_t* data, size_t length) {
    for (int attempt = 0; attempt < MAX_RETRIES; ++attempt) {
        HTTPClient http;
        http.setConnectTimeout(3000);
        http.setTimeout(HTTP_TIMEOUT);
        http.begin(endpoint(suffix));
        http.addHeader("Content-Type", "application/octet-stream");
        int code = http.POST(const_cast<uint8_t*>(data), length);
        http.end();
        if (code == 200) return true;
        if (code >= 400 && code < 500 && code != 409 && code != 429) return false;
        delay(200);
    }
    return false;
}

struct PlaybackClock {
    uint32_t now() { return millis(); }
    void pause() { delay(2); }
};

bool readExact(WiFiClient* client, uint8_t* target, size_t length, uint32_t started) {
    PlaybackClock clock;
    return transport::readExact(client, target, length, started, clock);
}

bool writeSpeaker(const uint8_t* pcm, size_t length) {
    size_t offset = 0;
    while (offset < length) {
        size_t written = 0;
        esp_err_t result = i2s_write(I2S_SPK_PORT, pcm + offset, length - offset, &written, pdMS_TO_TICKS(500));
        if (result != ESP_OK || written == 0 || written % 2) return false;
        offset += written;
    }
    return true;
}

bool playFrames(WiFiClient* client) {
    uint32_t started = millis();
    uint8_t pcm[2048];
    bool heardAudio = false;
    while (true) {
        uint8_t header[4];
        if (!readExact(client, header, 4, started)) return false;
        uint32_t length = uint32_t(header[0]) | (uint32_t(header[1]) << 8) |
                          (uint32_t(header[2]) << 16) | (uint32_t(header[3]) << 24);
        if (length == 0) {
            if (!heardAudio) return false;
            // Add enough silence to drain the 8 DMA buffers before stopping.
            memset(pcm, 0, sizeof(pcm));
            for (int i = 0; i < 10; ++i) if (!writeSpeaker(pcm, sizeof(pcm))) return false;
            return true;
        }
        if (length > sizeof(pcm) || length % 2) return false; // Incluye marcador de error 0xffffffff.
        if (!readExact(client, pcm, length, started) || !writeSpeaker(pcm, length)) return false;
        heardAudio = true;
    }
}

bool fetchResponse(uint32_t count) {
    for (int attempt = 0; attempt < MAX_RETRIES; ++attempt) {
        HTTPClient http;
        http.useHTTP10(true);
        http.setConnectTimeout(3000);
        http.setTimeout(HTTP_TIMEOUT);
        http.begin(endpoint("/end?blocks=" + String(count)));
        const char* keys[] = {"X-Audio-Format", "Transfer-Encoding"};
        http.collectHeaders(keys, 2);
        int code = http.POST("");
        bool ok = false;
        if (code == 200 && http.header("X-Audio-Format") == "pcm-s16le-framed-v1" &&
            http.header("Transfer-Encoding").length() == 0) {
            i2s_zero_dma_buffer(I2S_SPK_PORT);
            if (i2s_start(I2S_SPK_PORT) == ESP_OK) ok = playFrames(http.getStreamPtr());
            i2s_stop(I2S_SPK_PORT);
            i2s_zero_dma_buffer(I2S_SPK_PORT);
        }
        http.end();
        if (ok) return true;
        Serial.printf("Respuesta incompleta/error HTTP %d; intento %d\n", code, attempt + 1);
        if (code == 404 || code == 400) break;
        delay(300);
    }
    return false;
}

void networkTask(void*) {
    AudioBlock block;
    for (;;) {
        if (xQueueReceive(audioQueue, &block, portMAX_DELAY) != pdTRUE) continue;
        if (block.kind == BlockKind::Start) {
            if (!sendBlock("/start", nullptr, 0)) recordingFailed.store(true);
        } else if (block.kind == BlockKind::Data) {
            if (!recordingFailed.load() && !sendBlock("/chunks/" + String(block.sequence), block.pcm, block.length))
                recordingFailed.store(true);
        } else {
            if (recordingFailed.load()) {
                sendBlock("/abort", nullptr, 0);
                Serial.println("Recording discarded after audio/network loss. Try again.");
            } else if (!fetchResponse(block.sequence)) {
                Serial.println("Could not complete the answer. No automatic retry is issued.");
            }
            networkBusy.store(false);
        }
    }
}

void endRecording() {
    i2s_stop(I2S_MIC_PORT);
    isRecording = false;
    waitForRelease = true;
    AudioBlock end{};
    end.kind = BlockKind::End;
    end.sequence = sequence;
    // Microphone already stopped: waiting for the consumer here loses no samples.
    if (xQueueSend(audioQueue, &end, pdMS_TO_TICKS(50000)) != pdTRUE) {
        Serial.println("La tarea de red no responde; reiniciando para recuperar estado.");
        ESP.restart();
    }
}

void loop() {
    bool pressed = digitalRead(BUTTON_PIN) == LOW;
    if (waitForRelease) {
        if (!pressed) waitForRelease = false;
        delay(10);
        return;
    }
    if (!isRecording) {
        if (!pressed || networkBusy.load()) { delay(10); return; }
        delay(30);
        if (digitalRead(BUTTON_PIN) != LOW) return;
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("No Wi-Fi; recording will not start.");
            waitForRelease = true;
            return;
        }
        networkBusy.store(true);
        recordingFailed.store(false);
        snprintf(recordingId, sizeof(recordingId), "%012llx-%08lx-%08lx", ESP.getEfuseMac(),
                 (unsigned long)esp_random(), (unsigned long)esp_random());
        sequence = 0;
        capturedBytes = 0;
        AudioBlock start{};
        start.kind = BlockKind::Start;
        xQueueSend(audioQueue, &start, 0);
        i2s_zero_dma_buffer(I2S_MIC_PORT);
        if (i2s_start(I2S_MIC_PORT) != ESP_OK) {
            recordingFailed.store(true);
            endRecording();
            return;
        }
        isRecording = true;
        recordingStarted = millis();
    }
    if (!pressed || recordingFailed.load() || millis() - recordingStarted >= 60000 || capturedBytes >= 1920000) {
        endRecording();
        return;
    }
    static uint32_t samples[SAMPLE_BUFFER_SIZE];
    size_t bytes = 0;
    esp_err_t result = i2s_read(I2S_MIC_PORT, samples, sizeof(samples), &bytes, pdMS_TO_TICKS(200));
    if (result != ESP_OK || !bytes || bytes % 4) {
        recordingFailed.store(true);
        endRecording();
        return;
    }
    static AudioBlock block{};
    block.kind = BlockKind::Data;
    block.sequence = sequence;
    block.length = min(static_cast<uint32_t>(bytes / 2), 1920000 - capturedBytes);
    for (size_t i = 0; i < block.length / 2; ++i) {
        int16_t sample = samples[i] >> 16;
        memcpy(block.pcm + i * 2, &sample, 2);
    }
    if (xQueueSend(audioQueue, &block, 0) != pdTRUE) {
        recordingFailed.store(true);
        endRecording();
    } else {
        ++sequence;
        capturedBytes += block.length;
    }
}
