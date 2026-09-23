#pragma once
#include <stdint.h>
#include <stddef.h>

// 16 chunks amount to roughly 1.024 s of speech (32 KiB).
enum class BlockKind : uint8_t { Start, Data, End };
struct AudioBlock {
    BlockKind kind;
    uint16_t length;
    uint32_t sequence;
    uint8_t pcm[2048];
};

namespace transport {
constexpr uint32_t IDLE_TIMEOUT = 20000;
constexpr uint32_t TOTAL_TIMEOUT = 90000;

// Clock allows testing timeouts and millis overflow without a board.
template <typename Client, typename Clock>
bool readExact(Client* client, uint8_t* target, size_t length, uint32_t started, Clock& clock) {
    size_t offset = 0;
    uint32_t lastData = clock.now();
    while (offset < length) {
        if (uint32_t(clock.now() - started) >= TOTAL_TIMEOUT ||
            uint32_t(clock.now() - lastData) >= IDLE_TIMEOUT) return false;
        int available = client->available();
        if (available <= 0) {
            if (!client->connected()) return false;
            clock.pause();
            continue;
        }
        size_t wanted = length - offset;
        if (wanted > static_cast<size_t>(available)) wanted = available;
        int count = client->read(target + offset, wanted);
        if (count < 0) return false;
        if (count > 0) {
            offset += count;
            lastData = clock.now();
        } else {
            clock.pause();
        }
    }
    return true;
}
}
