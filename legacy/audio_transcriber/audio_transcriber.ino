#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <driver/i2s.h>

#include "config.h"

// Local configuration excluded from Git
const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD;
const char* serverUrl = AUDIO_SERVER_URL;

// Button pin
const int BUTTON_PIN = 4;
bool isRecording = false;

// Audio buffer size
const int SAMPLE_BUFFER_SIZE = 1024;
int16_t sBuffer[SAMPLE_BUFFER_SIZE];

// I2S configuration for the INMP441 (microphone)
#define I2S_MIC_WS GPIO_NUM_25
#define I2S_MIC_SD GPIO_NUM_32
#define I2S_MIC_SCK GPIO_NUM_33
#define I2S_MIC_PORT I2S_NUM_0

// I2S configuration for the MAX98357A (speaker)
#define I2S_SPK_BCLK GPIO_NUM_26
#define I2S_SPK_LRC GPIO_NUM_27
#define I2S_SPK_DIN GPIO_NUM_22
#define I2S_SPK_PORT I2S_NUM_1

// Estados de los dispositivos
bool microphoneEnabled = false;
bool speakerEnabled = false;

void enableMicrophone() {
    if (!microphoneEnabled) {
        ESP_ERROR_CHECK(i2s_start(I2S_MIC_PORT));
        microphoneEnabled = true;
        Serial.println("Microphone enabled");
    }
}

void disableMicrophone() {
    if (microphoneEnabled) {
        ESP_ERROR_CHECK(i2s_stop(I2S_MIC_PORT));
        microphoneEnabled = false;
        Serial.println("Microphone disabled");
    }
}

void enableSpeaker() {
    if (!speakerEnabled) {
        ESP_ERROR_CHECK(i2s_start(I2S_SPK_PORT));
        speakerEnabled = true;
        Serial.println("🔊 Altavoz activado");
    }
}

void disableSpeaker() {
    if (speakerEnabled) {
        ESP_ERROR_CHECK(i2s_stop(I2S_SPK_PORT));
        speakerEnabled = false;
        Serial.println("🔊 Altavoz desactivado");
    }
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println("\n=== Iniciando sistema ===");
    
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    
    // Wi-Fi connection
    Serial.print("📡 Conectando a WiFi");
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\n✅ Conectado al WiFi");

    // Configurar I2S para INMP441
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
        .bck_io_num = I2S_MIC_SCK,
        .ws_io_num = I2S_MIC_WS,
        .data_out_num = -1,
        .data_in_num = I2S_MIC_SD
    };

    // Configurar I2S para MAX98357A
    i2s_config_t i2s_spk_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = 16000,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 3,
        .dma_buf_len = 256,
        .use_apll = false,
        .tx_desc_auto_clear = true
    };

    i2s_pin_config_t spk_pin_config = {
        .bck_io_num = I2S_SPK_BCLK,
        .ws_io_num = I2S_SPK_LRC,
        .data_out_num = I2S_SPK_DIN,
        .data_in_num = -1
    };

    // Instalar drivers I2S
    Serial.println("Configuring I2S for the microphone...");
    ESP_ERROR_CHECK(i2s_driver_install(I2S_MIC_PORT, &i2s_mic_config, 0, NULL));
    ESP_ERROR_CHECK(i2s_set_pin(I2S_MIC_PORT, &mic_pin_config));
    
    Serial.println("🎯 Configurando I2S para altavoz...");
    ESP_ERROR_CHECK(i2s_driver_install(I2S_SPK_PORT, &i2s_spk_config, 0, NULL));
    ESP_ERROR_CHECK(i2s_set_pin(I2S_SPK_PORT, &spk_pin_config));
    
    // Limpiar buffers
    i2s_zero_dma_buffer(I2S_MIC_PORT);
    i2s_zero_dma_buffer(I2S_SPK_PORT);

    Serial.println("✅ Sistema iniciado y listo");
}

void process32to16(uint32_t* samples32, int16_t* samples16, size_t count) {
    for (int i = 0; i < count; i++) {
        samples16[i] = samples32[i] >> 16;
    }
}

bool playAudioFromServer(WiFiClient* client) {
    if (!client) {
        Serial.println("❌ Error: Cliente nulo");
        return false;
    }

    const int bufferSize = 256;
    uint8_t buffer[bufferSize];
    size_t bytesWritten = 0;
    int totalBytesRead = 0;
    int headerSize = 44;  // WAV header size

    // Esperar datos disponibles
    unsigned long timeout = millis() + 5000;
    while (client->available() < headerSize) {
        if (millis() > timeout) {
            Serial.println("❌ Timeout esperando header");
            return false;
        }
        delay(10);
    }

    // Saltar header WAV
    for (int i = 0; i < headerSize; i++) {
        client->read();
    }

    Serial.println("Starting playback...");
    i2s_zero_dma_buffer(I2S_SPK_PORT);
    enableSpeaker();

    while (client->available() || client->connected()) {
        int bytesRead = client->read(buffer, bufferSize);
        
        if (bytesRead > 0) {
            totalBytesRead += bytesRead;
            esp_err_t result = i2s_write(I2S_SPK_PORT, buffer, bytesRead, &bytesWritten, portMAX_DELAY);
            
            if (result != ESP_OK) {
                Serial.printf("❌ Error I2S write: %d\n", result);
                disableSpeaker();
                return false;
            }
        } else if (bytesRead < 0) {
            Serial.println("❌ Error leyendo stream");
            disableSpeaker();
            return false;
        }
        
        yield();
    }

    Serial.printf("✅ Reproducidos %d bytes\n", totalBytesRead);
    delay(100);
    i2s_zero_dma_buffer(I2S_SPK_PORT);
    disableSpeaker();
    return true;
}

void loop() {
    bool buttonIsPressed = (digitalRead(BUTTON_PIN) == LOW);
    static unsigned long lastDebounceTime = 0;
    static const unsigned long debounceDelay = 50;
    
    if (buttonIsPressed) {
        if (!isRecording && (millis() - lastDebounceTime) > debounceDelay) {
            isRecording = true;
            Serial.println("\n=== INICIO GRABACIÓN ===");
            enableMicrophone();
            disableSpeaker();
        }
        
        uint32_t samples32[SAMPLE_BUFFER_SIZE];
        size_t bytesIn = 0;
        
        esp_err_t result = i2s_read(I2S_MIC_PORT, &samples32, sizeof(samples32), &bytesIn, portMAX_DELAY);
        
        if (result == ESP_OK) {
            process32to16(samples32, sBuffer, bytesIn / sizeof(uint32_t));
            size_t samples16_size = bytesIn / 2;
            
            if (WiFi.status() == WL_CONNECTED) {
                HTTPClient http;
                http.begin(serverUrl);
                http.addHeader("Content-Type", "application/octet-stream");
                int httpCode = http.POST((uint8_t*)sBuffer, samples16_size);
                if (httpCode != HTTP_CODE_OK) {
                    Serial.printf("❌ Error HTTP: %d\n", httpCode);
                }
                http.end();
                Serial.print(".");
            }
        }
    } else if (isRecording) {
        lastDebounceTime = millis();
        disableMicrophone();
        
        if (WiFi.status() == WL_CONNECTED) {
            Serial.println("\nSending end of recording...");
            HTTPClient http;
            http.begin(serverUrl);
            http.addHeader("Content-Type", "application/octet-stream");
            http.addHeader("Recording-Status", "end");
            
            int httpCode = http.POST("");
            if (httpCode == HTTP_CODE_OK) {
                Serial.println("✅ Respuesta del servidor recibida");
                WiFiClient* stream = http.getStreamPtr();
                if (stream) {
                    playAudioFromServer(stream);
                }
            } else {
                Serial.printf("❌ Error HTTP final: %d\n", httpCode);
            }
            
            http.end();
        }
        
        isRecording = false;
        Serial.println("=== FIN GRABACIÓN ===\n");
    }
    
    delay(10);
}
