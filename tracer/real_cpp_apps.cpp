// Real multi-phase C++ workloads compiled with `clang++ -O2 -fsanitize=thread`
// and linked against `tsan_trace_rt.c` so every compiler-emitted heap/stack
// memory load and store is captured at 4 KiB virtual-page granularity.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <list>
#include <map>
#include <numeric>
#include <queue>
#include <string>
#include <unordered_map>
#include <vector>

extern "C" void tsan_trace_set_active(int active);

struct Rng {
    uint64_t s;
    explicit Rng(uint64_t seed) : s(seed ? seed : 1) {}
    uint64_t next() {
        s ^= s << 13;
        s ^= s >> 7;
        s ^= s << 17;
        return s;
    }
    double u() { return (next() >> 11) * (1.0 / 9007199254740992.0); }
    uint32_t bound(uint32_t k) { return (uint32_t)(next() % k); }
};

// 1. Burrows-Wheeler + Move-To-Front + Histogram compression/decompression
static int run_bwt_compress(uint64_t seed) {
    tsan_trace_set_active(0);
    Rng rng(seed);
    const size_t N = 262144;
    std::vector<uint8_t> raw(N);
    for (size_t i = 0; i < N; i++) {
        // Structured text-like + binary blocks
        if (i < N / 2) raw[i] = (uint8_t)('a' + (rng.bound(100) < 75 ? rng.bound(6) : rng.bound(26)));
        else raw[i] = (uint8_t)((i * 17 + rng.bound(32)) & 0xff);
    }
    tsan_trace_set_active(1);
    const size_t BLK = 8192;
    uint64_t checksum = 0;
    std::vector<uint32_t> sa(BLK);
    std::vector<uint8_t> bwt(BLK), mtf(BLK);
    for (size_t off = 0; off < N; off += BLK) {
        std::iota(sa.begin(), sa.end(), 0);
        const uint8_t *blk = raw.data() + off;
        std::sort(sa.begin(), sa.end(), [&](uint32_t a, uint32_t b) {
            for (size_t k = 0; k < 16; k++) {
                uint8_t ca = blk[(a + k) % BLK];
                uint8_t cb = blk[(b + k) % BLK];
                if (ca != cb) return ca < cb;
            }
            return a < b;
        });
        uint8_t dict[256];
        std::iota(dict, dict + 256, 0);
        for (size_t i = 0; i < BLK; i++) {
            uint8_t ch = blk[(sa[i] + BLK - 1) % BLK];
            bwt[i] = ch;
            uint8_t idx = 0;
            while (dict[idx] != ch) idx++;
            mtf[i] = idx;
            if (idx > 0) {
                std::memmove(dict + 1, dict, idx);
                dict[0] = ch;
            }
        }
        uint32_t freq[256] = {0};
        for (uint8_t x : mtf) freq[x]++;
        for (int c = 0; c < 256; c++) checksum += (uint64_t)(c + 1) * freq[c];
    }
    return (int)(checksum & 1);
}

// 2. Multi-phase KV engine: B-tree ordered map + Zipf reads -> range scans -> hash updates
static int run_kv_engine(uint64_t seed) {
    tsan_trace_set_active(0);
    Rng rng(seed);
    const int KEYS = 120000;
    std::map<uint32_t, uint64_t> btree;
    std::unordered_map<uint32_t, uint64_t> hidx;
    hidx.reserve(KEYS);
    std::vector<uint32_t> hot(2000);
    for (int i = 0; i < 2000; i++) hot[i] = rng.bound(KEYS);
    for (int i = 0; i < KEYS; i++) {
        uint64_t v = rng.next();
        btree.emplace((uint32_t)i, v);
        hidx.emplace((uint32_t)i, v);
    }
    tsan_trace_set_active(1);
    uint64_t acc = 0;
    // Phase 1: Skewed point reads via unordered_map
    for (int i = 0; i < 45000; i++) {
        uint32_t k = (rng.u() < 0.80) ? hot[rng.bound(2000)] : rng.bound(KEYS);
        auto it = hidx.find(k);
        if (it != hidx.end()) acc ^= it->second;
    }
    // Phase 2: Ordered range scans via std::map (RB-tree)
    for (int i = 0; i < 600; i++) {
        uint32_t lo = rng.bound(KEYS - 120);
        auto it = btree.lower_bound(lo);
        for (int c = 0; c < 80 && it != btree.end(); c++, ++it) acc += it->second;
    }
    // Phase 3: Uniform updates across both structures
    for (int i = 0; i < 15000; i++) {
        uint32_t k = rng.bound(KEYS);
        uint64_t nv = rng.next();
        btree[k] = nv;
        hidx[k] = nv;
    }
    return (int)(acc & 1);
}

// 3. Multi-phase graph analytics: CSR BFS + PageRank + Triangle sampling
static int run_graph_analytics(uint64_t seed) {
    tsan_trace_set_active(0);
    Rng rng(seed);
    const int N = 150000;
    std::vector<std::vector<uint32_t>> adj(N);
    for (int u = 0; u < N; u++) {
        int deg = 3 + rng.bound(6);
        for (int k = 0; k < deg; k++) {
            uint32_t v = (rng.u() < 0.65) ? rng.bound(15000) : rng.bound(N);
            adj[u].push_back(v);
        }
    }
    std::vector<uint32_t> off(N + 1, 0), edges;
    for (int u = 0; u < N; u++) {
        off[u + 1] = off[u] + (uint32_t)adj[u].size();
        edges.insert(edges.end(), adj[u].begin(), adj[u].end());
    }
    adj.clear();
    std::vector<double> pr(N, 1.0 / N), nxt(N, 0.0);
    std::vector<uint8_t> vis(N, 0);
    tsan_trace_set_active(1);
    // Phase 1: BFS from multiple roots
    std::queue<uint32_t> q;
    uint64_t visited = 0;
    for (int root = 0; root < 5; root++) {
        uint32_t s = rng.bound(N);
        if (!vis[s]) { vis[s] = 1; q.push(s); }
        int steps = 0;
        while (!q.empty() && steps < 25000) {
            uint32_t u = q.front(); q.pop(); visited++; steps++;
            for (uint32_t e = off[u]; e < off[u + 1]; e++) {
                uint32_t v = edges[e];
                if (!vis[v]) { vis[v] = 1; q.push(v); }
            }
        }
    }
    // Phase 2: PageRank sweeps
    for (int it = 0; it < 2; it++) {
        std::fill(nxt.begin(), nxt.end(), 0.15 / N);
        for (int u = 0; u < N; u++) {
            uint32_t d = off[u + 1] - off[u];
            if (!d) continue;
            double share = 0.85 * pr[u] / d;
            for (uint32_t e = off[u]; e < off[u + 1]; e++) nxt[edges[e]] += share;
        }
        pr.swap(nxt);
    }
    return (int)((visited + (uint64_t)(pr[0] * 1e6)) & 1);
}

// 4. In-memory hash/LRU cache simulator workload (pointer-chasing + hashing)
static int run_cache_replay(uint64_t seed) {
    tsan_trace_set_active(0);
    Rng rng(seed);
    const uint32_t KEYSPACE = 80000;
    const size_t CAP = 8000;
    std::vector<uint32_t> stream(90000);
    for (size_t i = 0; i < stream.size(); i++) {
        if (i < 30000) stream[i] = (uint32_t)(std::pow(rng.u(), 2.5) * KEYSPACE);
        else if (i < 60000) stream[i] = (uint32_t)((i * 7) % 30000);
        else stream[i] = rng.bound(KEYSPACE);
    }
    tsan_trace_set_active(1);
    std::list<uint32_t> lru;
    std::unordered_map<uint32_t, std::list<uint32_t>::iterator> pos;
    pos.reserve(CAP * 2);
    size_t hits = 0;
    for (uint32_t k : stream) {
        auto it = pos.find(k);
        if (it != pos.end()) {
            hits++;
            lru.splice(lru.begin(), lru, it->second);
        } else {
            if (lru.size() >= CAP) {
                uint32_t v = lru.back();
                lru.pop_back();
                pos.erase(v);
            }
            lru.push_front(k);
            pos[k] = lru.begin();
        }
    }
    return (int)(hits & 1);
}

int main(int argc, char **argv) {
    if (argc < 3) return 2;
    std::string app = argv[1];
    uint64_t seed = std::strtoull(argv[2], nullptr, 10);
    if (app == "bwt") return run_bwt_compress(seed);
    if (app == "kv") return run_kv_engine(seed);
    if (app == "graph") return run_graph_analytics(seed);
    if (app == "cache") return run_cache_replay(seed);
    return 2;
}
