#include <cassert>
#include <cstring>
#include <vector>
#include "../firmware/wristband/transport.h"
struct Clock {
    uint32_t t;
    uint32_t now() { return t; }
    void pause() { t += 2; }
};
struct Client {
    std::vector<uint8_t> data;
    size_t pos = 0;
    bool alive = true;
    int available() { return pos < data.size() ? 1 : 0; }
    bool connected() { return alive; }
    int read(uint8_t* out, size_t length) {
        if (!length || pos == data.size()) return 0;
        *out = data[pos++];
        return 1;
    }
};
int main() {
    uint8_t out[4];
    Client stalled;
    Clock c{0};
    assert(!transport::readExact(&stalled, out, 4, 0, c));
    assert(c.t == transport::IDLE_TIMEOUT);
    Client split{{1,2,3,4}};
    c.t=0;
    assert(transport::readExact(&split, out, 4, 0, c));
    assert(std::memcmp(out,"\1\2\3\4",4)==0);
    Client closed{{1,2}};
    closed.alive=false;
    assert(!transport::readExact(&closed, out, 4, 0, c));
    c.t=0xfffffff0;
    auto start=c.t;
    assert(!transport::readExact(&stalled, out, 4, start, c));
    assert(uint32_t(c.t-start)==transport::IDLE_TIMEOUT);
    Client ready{{1,2,3,4}};
    c.t=transport::TOTAL_TIMEOUT;
    assert(!transport::readExact(&ready, out, 4, 0, c));
}
