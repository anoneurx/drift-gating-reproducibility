// pathA_sim.cpp -- Unified, consistent simulator for the Path A measurement study.
// Implements:
//  1. 21 static/adaptive/learned policies (including S3-FIFO, SIEVE, ARC, LIRS,
//     W-TinyLFU, LeCaR, CACHEUS, MGLRU-style, and online-learned LRB-style).
//  2. Exact Dynamic Programming (Viterbi) per-window hindsight oracle paying
//     explicit switch cost C (primary) and 0 (upper bound).
//  3. Switching controller comparing all 6 triggers (CUSUM, Page-Hinkley,
//     ADWIN, Periodic, Random, Oracle-window) + ContShadow across 3 evaluation
//     budgets, with rankable shadow caches (Cs <= 0.5 * Dw) and consistent
//     CLOCK_PROCESS_CPUTIME_ID timing.
//
// Build: g++ -O2 -std=c++17 -Wall -Wextra -o pathA_sim pathA_sim.cpp

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <list>
#include <memory>
#include <numeric>
#include <random>
#include <set>
#include <string>
#include <time.h>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using namespace std;
using u32 = uint32_t;
using u64 = uint64_t;

static int NP = 1 << 20;
static const u32 NONE = 0xFFFFFFFFu;

static inline u64 cpu_ns() {
    struct timespec ts;
    clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &ts);
    return (u64)ts.tv_sec * 1000000000ULL + (u64)ts.tv_nsec;
}

struct RNG {
    mt19937_64 g;
    explicit RNG(u64 s) : g(s) {}
    double u() { return (g() >> 11) * (1.0 / 9007199254740992.0); }
    u32 n(u32 k) { return (u32)(g() % k); }
};

struct LS {
    vector<list<u32>> L;
    vector<list<u32>::iterator> it;
    vector<int8_t> loc;
    explicit LS(int k) : L(k), it(NP), loc(NP, -1) {}
    void pf(int l, u32 x) {
        L[l].push_front(x);
        it[x] = L[l].begin();
        loc[x] = (int8_t)l;
    }
    void rm(u32 x) {
        L[loc[x]].erase(it[x]);
        loc[x] = -1;
    }
    u32 back(int l) const { return L[l].back(); }
    size_t sz(int l) const { return L[l].size(); }
};

struct Policy {
    int C;
    explicit Policy(int c) : C(max(1, c)) {}
    virtual ~Policy() {}
    virtual bool access(u32 p) = 0;
    virtual vector<u32> resident() { return {}; }
    virtual void load(const vector<u32>&, const vector<uint16_t>&) {}
};

// 1. LRU / MRU
struct LRU : Policy {
    LS s;
    bool mru;
    LRU(int c, bool m = false) : Policy(c), s(1), mru(m) {}
    bool access(u32 p) override {
        if (s.loc[p] >= 0) { s.rm(p); s.pf(0, p); return true; }
        if ((int)s.sz(0) >= C) { u32 v = mru ? s.L[0].front() : s.back(0); s.rm(v); }
        s.pf(0, p);
        return false;
    }
    vector<u32> resident() override { return vector<u32>(s.L[0].rbegin(), s.L[0].rend()); }
    void load(const vector<u32>& pg, const vector<uint16_t>&) override {
        size_t st = pg.size() > (size_t)C ? pg.size() - C : 0;
        for (size_t i = st; i < pg.size(); i++) s.pf(0, pg[i]);
    }
};

// 2. FIFO
struct FIFO : Policy {
    LS s;
    explicit FIFO(int c) : Policy(c), s(1) {}
    bool access(u32 p) override {
        if (s.loc[p] >= 0) return true;
        if ((int)s.sz(0) >= C) s.rm(s.back(0));
        s.pf(0, p);
        return false;
    }
};

// 3. CLOCK
struct CLOCK : Policy {
    vector<u32> fr;
    vector<char> rb;
    vector<int> slot;
    int hand = 0, used = 0;
    explicit CLOCK(int c) : Policy(c), fr(C, NONE), rb(C, 0), slot(NP, -1) {}
    bool access(u32 p) override {
        if (slot[p] >= 0) { rb[slot[p]] = 1; return true; }
        if (used < C) { fr[used] = p; slot[p] = used; rb[used] = 0; used++; return false; }
        while (rb[hand]) { rb[hand] = 0; hand = (hand + 1) % C; }
        slot[fr[hand]] = -1;
        fr[hand] = p;
        slot[p] = hand;
        rb[hand] = 0;
        hand = (hand + 1) % C;
        return false;
    }
};

// 4. LFU-A (aged LFU)
struct LFUA : Policy {
    set<tuple<u32, u64, u32>> S;
    vector<u32> cnt;
    vector<u64> last;
    vector<char> in;
    u64 t = 0, age;
    int n = 0;
    LFUA(int c, u64 ageRefs) : Policy(c), cnt(NP, 0), last(NP, 0), in(NP, 0), age(ageRefs) {}
    bool access(u32 p) override {
        t++;
        if (age && t % age == 0) {
            vector<u32> pg;
            pg.reserve(S.size());
            for (const auto& e : S) pg.push_back(get<2>(e));
            S.clear();
            for (u32 q : pg) { cnt[q] = max<u32>(1, cnt[q] / 2); S.insert({cnt[q], last[q], q}); }
        }
        if (in[p]) {
            S.erase({cnt[p], last[p], p});
            cnt[p]++;
            last[p] = t;
            S.insert({cnt[p], last[p], p});
            return true;
        }
        if (n >= C) {
            auto v = *S.begin();
            S.erase(S.begin());
            in[get<2>(v)] = 0;
            n--;
        }
        cnt[p] = 1;
        last[p] = t;
        in[p] = 1;
        n++;
        S.insert({1, t, p});
        return false;
    }
    vector<u32> resident() override {
        vector<pair<u64, u32>> v;
        v.reserve(S.size());
        for (const auto& e : S) v.push_back({get<1>(e), get<2>(e)});
        sort(v.begin(), v.end());
        vector<u32> r;
        r.reserve(v.size());
        for (const auto& x : v) r.push_back(x.second);
        return r;
    }
    void load(const vector<u32>& pg, const vector<uint16_t>& c) override {
        size_t st = pg.size() > (size_t)C ? pg.size() - C : 0;
        for (size_t i = st; i < pg.size(); i++) {
            u32 q = pg[i];
            cnt[q] = max<u32>(1, c[i]);
            last[q] = ++t;
            in[q] = 1;
            n++;
            S.insert({cnt[q], last[q], q});
        }
    }
};

// 5. 2Q
struct TwoQ : Policy {
    LS s;
    int kin, kout;
    explicit TwoQ(int c) : Policy(c), s(3), kin(max(1, C / 4)), kout(max(1, C / 2)) {}
    void reclaim() {
        if ((int)(s.sz(0) + s.sz(1)) < C) return;
        if ((int)s.sz(0) > kin || s.sz(1) == 0) {
            u32 v = s.back(0);
            s.rm(v);
            s.pf(2, v);
            if ((int)s.sz(2) > kout) s.rm(s.back(2));
        } else {
            s.rm(s.back(1));
        }
    }
    bool access(u32 p) override {
        int l = s.loc[p];
        if (l == 1) { s.rm(p); s.pf(1, p); return true; }
        if (l == 0) return true;
        if (l == 2) { s.rm(p); reclaim(); s.pf(1, p); return false; }
        reclaim();
        s.pf(0, p);
        return false;
    }
    vector<u32> resident() override {
        vector<u32> r(s.L[0].rbegin(), s.L[0].rend());
        r.insert(r.end(), s.L[1].rbegin(), s.L[1].rend());
        return r;
    }
    void load(const vector<u32>& pg, const vector<uint16_t>& c) override {
        size_t st = pg.size() > (size_t)C ? pg.size() - C : 0;
        for (size_t i = st; i < pg.size(); i++) s.pf(c[i] >= 2 ? 1 : 0, pg[i]);
    }
};

// 6. ARC
struct ARC : Policy {
    LS s;
    double p = 0;
    explicit ARC(int c) : Policy(c), s(4) {}
    void replace(u32 x) {
        bool inB2 = s.loc[x] == 3;
        if (s.sz(0) > 0 && ((double)s.sz(0) > p || (inB2 && (double)s.sz(0) == p))) {
            u32 v = s.back(0); s.rm(v); s.pf(2, v);
        } else if (s.sz(1) > 0) {
            u32 v = s.back(1); s.rm(v); s.pf(3, v);
        }
    }
    bool access(u32 x) override {
        int l = s.loc[x];
        if (l == 0 || l == 1) { s.rm(x); s.pf(1, x); return true; }
        if (l == 2) {
            p = min<double>(C, p + max<double>(1, (double)s.sz(3) / max<size_t>(1, s.sz(2))));
            replace(x); s.rm(x); s.pf(1, x); return false;
        }
        if (l == 3) {
            p = max<double>(0, p - max<double>(1, (double)s.sz(2) / max<size_t>(1, s.sz(3))));
            replace(x); s.rm(x); s.pf(1, x); return false;
        }
        size_t L1 = s.sz(0) + s.sz(2);
        if ((int)L1 >= C) {
            if ((int)s.sz(0) < C) { s.rm(s.back(2)); replace(x); }
            else s.rm(s.back(0));
        } else {
            size_t tot = L1 + s.sz(1) + s.sz(3);
            if ((int)tot >= C) {
                if ((int)tot >= 2 * C && s.sz(3)) s.rm(s.back(3));
                replace(x);
            }
        }
        s.pf(0, x);
        return false;
    }
    vector<u32> resident() override {
        vector<u32> r(s.L[0].rbegin(), s.L[0].rend());
        r.insert(r.end(), s.L[1].rbegin(), s.L[1].rend());
        return r;
    }
    void load(const vector<u32>& pg, const vector<uint16_t>& c) override {
        size_t st = pg.size() > (size_t)C ? pg.size() - C : 0;
        for (size_t i = st; i < pg.size(); i++) s.pf(c[i] >= 2 ? 1 : 0, pg[i]);
    }
};

// 7. S3-FIFO (Yang et al., SOSP 2023): 10% Small, 90% Main, ghost = M, freq > 0 promotes
struct S3FIFO : Policy {
    LS s;
    int S, M;
    vector<uint8_t> f;
    explicit S3FIFO(int c) : Policy(c), s(3), f(NP, 0) {
        S = max(1, (int)lround(0.10 * C));
        M = C - S;
        if (M < 1) { M = max(1, C - 1); S = C - M; }
    }
    void evictMain() {
        while (s.sz(1) > 0) {
            u32 t = s.back(1);
            s.rm(t);
            if (f[t] > 0) { f[t]--; s.pf(1, t); }
            else return;
        }
    }
    void evict() {
        if ((int)(s.sz(0) + s.sz(1)) < C) return;
        if ((int)s.sz(0) >= S || s.sz(1) == 0) {
            if (s.sz(0) == 0) { evictMain(); return; }
            u32 t = s.back(0);
            s.rm(t);
            if (f[t] > 0 && M > 0) {
                f[t] = 0;
                if ((int)s.sz(1) >= M) evictMain();
                s.pf(1, t);
            } else {
                s.pf(2, t);
                if ((int)s.sz(2) > max(1, M)) s.rm(s.back(2));
            }
        } else {
            evictMain();
        }
    }
    bool access(u32 x) override {
        int l = s.loc[x];
        if (l == 0 || l == 1) { f[x] = min<uint8_t>(3, f[x] + 1); return true; }
        bool g = (l == 2);
        if (g) s.rm(x);
        evict();
        f[x] = 0;
        s.pf(g ? 1 : 0, x);
        return false;
    }
    vector<u32> resident() override {
        vector<u32> r(s.L[0].rbegin(), s.L[0].rend());
        r.insert(r.end(), s.L[1].rbegin(), s.L[1].rend());
        return r;
    }
    void load(const vector<u32>& pg, const vector<uint16_t>& c) override {
        size_t st = pg.size() > (size_t)C ? pg.size() - C : 0;
        for (size_t i = st; i < pg.size(); i++) {
            u32 q = pg[i];
            if (c[i] >= 2 && (int)s.sz(1) < M) s.pf(1, q);
            else if ((int)s.sz(0) < S) s.pf(0, q);
            else s.pf(1, q);
            f[q] = (uint8_t)min<uint16_t>(3, c[i] > 0 ? c[i] - 1 : 0);
        }
    }
};

// 8. LeCaR (Vietri et al., HotStorage 2018)
struct LeCaR : Policy {
    LS s;
    set<tuple<u32, u64, u32>> F;
    vector<u32> cnt;
    vector<u64> last, hl, hf;
    vector<char> hin;
    deque<u32> HL, HF;
    double wl = 0.5, lr = 0.45, d;
    u64 t = 0;
    RNG r;
    explicit LeCaR(int c)
        : Policy(c), s(1), cnt(NP, 0), last(NP, 0), hl(NP, 0), hf(NP, 0),
          hin(NP, 0), d(pow(0.005, 1.0 / max(1, C))), r(7) {}
    void hist(deque<u32>& H, u32 v, char tag, vector<u64>& tm) {
        H.push_back(v);
        tm[v] = t;
        hin[v] = tag;
        while ((int)H.size() > max(1, C / 2)) {
            u32 o = H.front();
            H.pop_front();
            if (hin[o] == tag) hin[o] = 0;
        }
    }
    bool access(u32 p) override {
        t++;
        if (s.loc[p] >= 0) {
            F.erase({cnt[p], last[p], p});
            cnt[p]++;
            last[p] = t;
            F.insert({cnt[p], last[p], p});
            s.rm(p);
            s.pf(0, p);
            return true;
        }
        if (hin[p]) {
            double rew = pow(d, (double)(t - (hin[p] == 1 ? hl[p] : hf[p])));
            if (hin[p] == 1) wl *= exp(-lr * rew);
            else wl /= exp(-lr * rew);
            wl = min(0.99, max(0.01, wl / (wl + (1.0 - wl))));
            hin[p] = 0;
        }
        if ((int)s.sz(0) >= C) {
            bool useLRU = r.u() < wl;
            u32 v = useLRU ? s.back(0) : get<2>(*F.begin());
            if (useLRU) hist(HL, v, 1, hl);
            else hist(HF, v, 2, hf);
            F.erase({cnt[v], last[v], v});
            s.rm(v);
        }
        cnt[p] = 1;
        last[p] = t;
        F.insert({1, t, p});
        s.pf(0, p);
        return false;
    }
};

// 9. LPR-style
struct LPR : Policy {
    LS s;
    bool mru = false;
    int epochRefs = 0, ghostHits = 0, W = 2000;
    explicit LPR(int c) : Policy(c), s(2) {}
    bool access(u32 p) override {
        if (++epochRefs == W) {
            if ((double)ghostHits / W > 0.05) mru = !mru;
            ghostHits = 0;
            epochRefs = 0;
            while (s.sz(1)) s.rm(s.back(1));
        }
        if (s.loc[p] == 0) { s.rm(p); s.pf(0, p); return true; }
        if (s.loc[p] == 1) { ghostHits++; s.rm(p); }
        if ((int)s.sz(0) >= C) {
            u32 v = mru ? s.L[0].front() : s.back(0);
            s.rm(v);
            s.pf(1, v);
            if ((int)s.sz(1) > 2 * C) s.rm(s.back(1));
        }
        s.pf(0, p);
        return false;
    }
};

// 10. SIEVE (Zhang et al., NSDI 2024)
struct SIEVE : Policy {
    list<u32> q;
    vector<list<u32>::iterator> it;
    vector<char> in, visited;
    list<u32>::iterator hand;
    bool handInit = false;
    explicit SIEVE(int c) : Policy(c), it(NP), in(NP, 0), visited(NP, 0) {}
    bool access(u32 p) override {
        if (in[p]) { visited[p] = 1; return true; }
        if ((int)q.size() >= C) {
            if (!handInit) { hand = prev(q.end()); handInit = true; }
            while (visited[*hand]) {
                visited[*hand] = 0;
                hand = (hand == q.begin()) ? prev(q.end()) : prev(hand);
            }
            u32 v = *hand;
            auto nxt = (hand == q.begin()) ? prev(q.end()) : prev(hand);
            q.erase(hand);
            in[v] = 0;
            visited[v] = 0;
            hand = nxt;
            if (q.empty()) handInit = false;
        }
        q.push_front(p);
        it[p] = q.begin();
        in[p] = 1;
        visited[p] = 0;
        return false;
    }
};

// 11. W-TinyLFU (Einziger et al., FAST 2017)
struct WTinyLFU : Policy {
    int Wsz, Psz, ProtSz;
    list<u32> win, prob, prot;
    vector<list<u32>::iterator> itW, itP, itProt;
    vector<char> inW, inP, inProt;
    static const int CMS_D = 4;
    int cmsW;
    vector<uint16_t> cms;
    u64 accesses = 0;
    explicit WTinyLFU(int c)
        : Policy(c), itW(NP), itP(NP), itProt(NP), inW(NP, 0), inP(NP, 0), inProt(NP, 0) {
        Wsz = max(1, C / 100);
        if (Wsz >= C && C > 1) Wsz = C - 1;
        int mainC = max(1, C - Wsz);
        ProtSz = max(1, (int)(mainC * 0.8));
        Psz = mainC - ProtSz;
        if (Psz < 1) { Psz = 1; ProtSz = max(0, mainC - 1); }
        cmsW = max(1024, C * 4);
        cms.assign(CMS_D * cmsW, 0);
    }
    uint32_t h1(uint32_t x, int i) const {
        uint64_t z = x + 0x9e3779b97f4a7c15ULL * (i + 1);
        z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
        return (uint32_t)((z ^ (z >> 27)) % cmsW);
    }
    void cmsInc(u32 x) {
        for (int i = 0; i < CMS_D; i++) {
            uint32_t idx = (uint32_t)i * cmsW + h1(x, i);
            if (cms[idx] < 65535) cms[idx]++;
        }
    }
    uint32_t cmsEst(u32 x) const {
        uint32_t m = 65535;
        for (int i = 0; i < CMS_D; i++) {
            uint32_t v = cms[(uint32_t)i * cmsW + h1(x, i)];
            if (v < m) m = v;
        }
        return m;
    }
    void cmsDecay() { for (auto& v : cms) v >>= 1; }
    void rmWin(u32 x) { win.erase(itW[x]); inW[x] = 0; }
    void rmProb(u32 x) { prob.erase(itP[x]); inP[x] = 0; }
    void rmProt(u32 x) { prot.erase(itProt[x]); inProt[x] = 0; }
    void addProt(u32 x) {
        if (ProtSz == 0) { prob.push_front(x); itP[x] = prob.begin(); inP[x] = 1; return; }
        prot.push_front(x);
        itProt[x] = prot.begin();
        inProt[x] = 1;
        if ((int)prot.size() > ProtSz) {
            u32 v = prot.back();
            rmProt(v);
            prob.push_front(v);
            itP[v] = prob.begin();
            inP[v] = 1;
        }
    }
    bool access(u32 p) override {
        if (++accesses % (u64)max(1, C) == 0) cmsDecay();
        cmsInc(p);
        if (inW[p]) { win.erase(itW[p]); win.push_front(p); itW[p] = win.begin(); return true; }
        if (inProt[p]) { prot.erase(itProt[p]); prot.push_front(p); itProt[p] = prot.begin(); return true; }
        if (inP[p]) { rmProb(p); addProt(p); return true; }
        win.push_front(p);
        itW[p] = win.begin();
        inW[p] = 1;
        if ((int)win.size() > Wsz) {
            u32 cand = win.back();
            rmWin(cand);
            if ((int)(prob.size() + prot.size()) < Psz + ProtSz) {
                prob.push_front(cand);
                itP[cand] = prob.begin();
                inP[cand] = 1;
            } else if (!prob.empty()) {
                u32 victim = prob.back();
                if (cmsEst(cand) > cmsEst(victim)) {
                    rmProb(victim);
                    prob.push_front(cand);
                    itP[cand] = prob.begin();
                    inP[cand] = 1;
                }
            }
        }
        return false;
    }
};

// 12. LHD-style hit-density heuristic
struct LHD : Policy {
    vector<u64> born;
    vector<uint32_t> hits;
    vector<char> in;
    vector<double> key;
    u64 now = 0;
    int residentN = 0;
    using Key = pair<double, u32>;
    set<Key> order;
    explicit LHD(int c) : Policy(c), born(NP, 0), hits(NP, 0), in(NP, 0), key(NP, 0) {}
    double score(u32 p) const { return (double)(hits[p] + 1u) / (double)(now - born[p] + 1ull); }
    void add(u32 p) { double s = score(p); order.insert(Key(s, p)); key[p] = s; }
    void remove(u32 p) { order.erase(Key(key[p], p)); }
    bool access(u32 p) override {
        ++now;
        if (in[p]) { remove(p); ++hits[p]; add(p); return true; }
        if (residentN >= C && !order.empty()) {
            auto it = order.begin();
            u32 v = it->second;
            order.erase(it);
            in[v] = 0;
            --residentN;
        }
        born[p] = now;
        hits[p] = 0;
        in[p] = 1;
        ++residentN;
        add(p);
        return false;
    }
};

// 13. CAR
struct CAR : Policy {
    LS s;
    vector<char> rb;
    double p = 0;
    explicit CAR(int c) : Policy(c), s(4), rb(NP, 0) {}
    u32 ev(int l) {
        while (true) {
            u32 v = s.back(l);
            if (rb[v]) { rb[v] = 0; s.rm(v); s.pf(l, v); }
            else { s.rm(v); return v; }
        }
    }
    void repl() {
        if (s.sz(0) && ((double)s.sz(0) > p || (s.sz(0) == p && s.sz(3) > 0))) { u32 v = ev(0); s.pf(2, v); }
        else if (s.sz(1)) { u32 v = ev(1); s.pf(3, v); }
        else if (s.sz(0)) { u32 v = ev(0); s.pf(2, v); }
    }
    void trim() {
        while (s.sz(2) + s.sz(3) > (size_t)C) {
            if (s.sz(2)) s.rm(s.back(2));
            else if (s.sz(3)) s.rm(s.back(3));
            else break;
        }
    }
    bool access(u32 x) override {
        int l = s.loc[x];
        if (l == 0 || l == 1) { rb[x] = 1; return true; }
        if (l == 2) {
            p = min<double>(C, p + max<double>(1, (double)s.sz(3) / max<size_t>(1, s.sz(2))));
            if (s.sz(0) + s.sz(1) >= (size_t)C) repl();
            s.rm(x); s.pf(1, x); rb[x] = 1; trim(); return false;
        }
        if (l == 3) {
            p = max<double>(0.0, p - max<double>(1, (double)s.sz(2) / max<size_t>(1, s.sz(3))));
            if (s.sz(0) + s.sz(1) >= (size_t)C) repl();
            s.rm(x); s.pf(1, x); rb[x] = 1; trim(); return false;
        }
        if (s.sz(0) + s.sz(1) >= (size_t)C) repl();
        s.pf(0, x); rb[x] = 0; trim(); return false;
    }
};

// 14. LIRS (O(1) stack-bounded LIRS: Jiang & Zhang SIGMETRICS 2002)
struct LIRS : Policy {
    struct Entry { u32 p; bool lir; bool res; };
    list<Entry> S;
    list<u32> Q;
    vector<list<Entry>::iterator> itS;
    vector<list<u32>::iterator> itQ;
    vector<char> inS, inQ, isLir, isRes;
    int lirCap, hirCap, nLir = 0, nRes = 0;
    explicit LIRS(int c)
        : Policy(c), itS(NP), itQ(NP), inS(NP, 0), inQ(NP, 0), isLir(NP, 0), isRes(NP, 0) {
        hirCap = max(1, (int)lround(0.10 * C));
        lirCap = max(0, C - hirCap);
    }
    void pruneS() {
        while (!S.empty() && !S.back().lir) {
            u32 q = S.back().p;
            S.pop_back();
            inS[q] = 0;
        }
        while ((int)S.size() > max(4, 2 * C)) {
            u32 q = S.back().p;
            if (S.back().lir) { isLir[q] = 0; nLir--; }
            S.pop_back();
            inS[q] = 0;
            if (isRes[q] && !inQ[q]) { Q.push_back(q); itQ[q] = prev(Q.end()); inQ[q] = 1; }
        }
    }
    void moveTopS(u32 p, bool lir, bool res) {
        if (inS[p]) S.erase(itS[p]);
        S.push_front({p, lir, res});
        itS[p] = S.begin();
        inS[p] = 1;
    }
    void demoteBottomLir() {
        if (S.empty()) return;
        for (auto it = prev(S.end()); ; --it) {
            if (it->lir) {
                u32 q = it->p;
                it->lir = false;
                isLir[q] = 0;
                nLir--;
                if (!inQ[q] && isRes[q]) { Q.push_back(q); itQ[q] = prev(Q.end()); inQ[q] = 1; }
                break;
            }
            if (it == S.begin()) break;
        }
        pruneS();
    }
    void evictOne() {
        if (nRes < C) return;
        if (!Q.empty()) {
            u32 v = Q.front();
            Q.pop_front();
            inQ[v] = 0;
            isRes[v] = 0;
            nRes--;
            if (inS[v]) itS[v]->res = false;
            return;
        }
        // fallback if Q empty
        for (auto it = prev(S.end()); ; --it) {
            if (it->res) {
                u32 v = it->p;
                it->res = false;
                isRes[v] = 0;
                nRes--;
                if (it->lir) { it->lir = false; isLir[v] = 0; nLir--; }
                break;
            }
            if (it == S.begin()) break;
        }
    }
    bool access(u32 p) override {
        if (isRes[p]) {
            if (isLir[p]) {
                moveTopS(p, true, true);
                pruneS();
            } else {
                bool wasInS = inS[p];
                if (inQ[p]) { Q.erase(itQ[p]); inQ[p] = 0; }
                if (wasInS && lirCap > 0) {
                    moveTopS(p, true, true);
                    isLir[p] = 1;
                    nLir++;
                    if (nLir > lirCap) demoteBottomLir();
                } else {
                    moveTopS(p, false, true);
                    Q.push_back(p);
                    itQ[p] = prev(Q.end());
                    inQ[p] = 1;
                }
            }
            return true;
        }
        evictOne();
        isRes[p] = 1;
        nRes++;
        if (nLir < lirCap) {
            isLir[p] = 1;
            nLir++;
            moveTopS(p, true, true);
        } else {
            bool wasInS = inS[p];
            if (wasInS && lirCap > 0) {
                moveTopS(p, true, true);
                isLir[p] = 1;
                nLir++;
                if (nLir > lirCap) demoteBottomLir();
            } else {
                moveTopS(p, false, true);
                Q.push_back(p);
                itQ[p] = prev(Q.end());
                inQ[p] = 1;
            }
        }
        return false;
    }
};

// 15. CLOCK-Pro
struct CLOCKPro : Policy {
    LS s;
    vector<char> rb, seen;
    double p = 0;
    explicit CLOCKPro(int c) : Policy(c), s(4), rb(NP, 0), seen(NP, 0) {}
    u32 ev(int l) {
        while (true) {
            u32 v = s.back(l);
            if (rb[v]) { rb[v] = 0; s.rm(v); s.pf(l, v); }
            else { s.rm(v); return v; }
        }
    }
    void repl() {
        if (s.sz(0) && ((double)s.sz(0) > p || (s.sz(0) == p && s.sz(3) > 0))) { u32 v = ev(0); s.pf(2, v); }
        else if (s.sz(1)) { u32 v = ev(1); s.pf(3, v); }
        else if (s.sz(0)) { u32 v = ev(0); s.pf(2, v); }
    }
    void trim() {
        while (s.sz(2) + s.sz(3) > (size_t)C) {
            if (s.sz(2)) s.rm(s.back(2));
            else if (s.sz(3)) s.rm(s.back(3));
            else break;
        }
    }
    bool access(u32 x) override {
        int l = s.loc[x];
        if (l == 0 || l == 1) {
            if (seen[x]) {
                rb[x] = 1;
                if (l == 0) { s.rm(x); s.pf(1, x); }
                return true;
            }
            seen[x] = 1;
            rb[x] = 1;
            return true;
        }
        if (l == 2) {
            p = min<double>(C, p + 1);
            if (s.sz(0) + s.sz(1) >= (size_t)C) repl();
            s.rm(x); s.pf(1, x); rb[x] = 1; seen[x] = 1; trim(); return false;
        }
        if (l == 3) {
            p = max<double>(0.0, p - 1);
            if (s.sz(0) + s.sz(1) >= (size_t)C) repl();
            s.rm(x); s.pf(1, x); rb[x] = 1; seen[x] = 1; trim(); return false;
        }
        if (s.sz(0) + s.sz(1) >= (size_t)C) repl();
        s.pf(0, x); rb[x] = 0; seen[x] = 1; trim(); return false;
    }
};

// 16. CACHEUS
struct CACHEUS : Policy {
    LS rec;
    set<tuple<u32, u64, u32>> F;
    vector<u64> last, cnt;
    vector<char> in;
    double w[3] = {1, 1, 1};
    u64 t = 0, age;
    int n = 0;
    explicit CACHEUS(int c)
        : Policy(c), rec(1), last(NP, 0), cnt(NP, 0), in(NP, 0), age(4ull * max(1, C)) {}
    bool access(u32 p) override {
        t++;
        if (t % age == 0) {
            vector<u32> pg;
            pg.reserve(F.size());
            for (const auto& e : F) pg.push_back(get<2>(e));
            F.clear();
            for (u32 q : pg) { cnt[q] = max<u64>(1, cnt[q] / 2); F.insert({(u32)cnt[q], last[q], q}); }
        }
        bool hit = in[p];
        if (hit) {
            F.erase({(u32)cnt[p], last[p], p});
            cnt[p]++;
            last[p] = t;
            F.insert({(u32)cnt[p], last[p], p});
            rec.rm(p);
            rec.pf(0, p);
        }
        for (int i = 0; i < 3; i++) w[i] = 0.99 * w[i] + (hit ? 0.01 : 0.0);
        if (!hit) {
            if (n >= C) {
                int k = (w[0] <= w[1] && w[0] <= w[2]) ? 0 : (w[1] <= w[2] ? 1 : 2);
                u32 v;
                if (k == 0) v = rec.back(0);
                else if (k == 1) v = get<2>(*F.begin());
                else {
                    v = rec.back(0);
                    for (const auto& e : F) if (get<0>(e) == 1) { v = get<2>(e); break; }
                }
                F.erase({(u32)cnt[v], last[v], v});
                rec.rm(v);
                in[v] = 0;
                n--;
            }
            cnt[p] = 1;
            last[p] = t;
            in[p] = 1;
            n++;
            F.insert({1, t, p});
            rec.pf(0, p);
        }
        return hit;
    }
};

// 17. 3L-style heuristic
struct ThreeL : Policy {
    LS s;
    vector<char> ghost;
    int n = 0;
    explicit ThreeL(int c) : Policy(c), s(2), ghost(NP, 0) {}
    u32 victim() const {
        if (s.sz(0) > (size_t)(C / 4)) return s.back(0);
        if (s.sz(1) > (size_t)(C / 2)) return s.back(1);
        return s.sz(0) ? s.back(0) : s.back(1);
    }
    bool access(u32 p) override {
        int l = s.loc[p];
        if (l >= 0) { s.rm(p); s.pf(1, p); return true; }
        bool wasGhost = ghost[p] != 0;
        if (wasGhost) ghost[p] = 0;
        if (n >= C) { u32 v = victim(); s.rm(v); ghost[v] = 1; n--; }
        s.pf(wasGhost ? 1 : 0, p);
        n++;
        return false;
    }
};

// 18. MGLRU-style
struct MGLRU : Policy {
    static const int NG = 4;
    array<list<u32>, NG> L;
    vector<list<u32>::iterator> it;
    vector<int8_t> gen, seen;
    vector<char> in;
    int nres = 0;
    u64 t = 0;
    int A;
    explicit MGLRU(int c)
        : Policy(c), it(NP), gen(NP, -1), seen(NP, 0), in(NP, 0), A(max(1, C)) {}
    void place(u32 p, int g) { L[g].push_front(p); it[p] = L[g].begin(); gen[p] = (int8_t)g; }
    void age() {
        vector<u32> g0(L[0].begin(), L[0].end());
        for (u32 p : g0) { L[0].erase(it[p]); place(p, 1); }
        for (int g = NG - 1; g >= 1; g--) {
            vector<u32> cur(L[g].begin(), L[g].end());
            for (u32 p : cur) {
                if (seen[p]) { seen[p] = 0; continue; }
                L[g].erase(it[p]);
                int ng = min(NG - 1, g + 1);
                L[ng].push_back(p);
                it[p] = prev(L[ng].end());
                gen[p] = (int8_t)ng;
            }
        }
    }
    bool access(u32 p) override {
        t++;
        if (t % (u64)A == 0) age();
        bool hit = in[p];
        if (hit) { seen[p] = 1; L[gen[p]].erase(it[p]); place(p, 0); return true; }
        if (nres >= C) {
            int g = NG - 1;
            while (g > 0 && L[g].empty()) g--;
            if (g == 0 && L[0].empty()) g = -1;
            if (g >= 0) {
                u32 v = L[g].back();
                L[g].pop_back();
                in[v] = 0;
                gen[v] = -1;
                seen[v] = 0;
                nres--;
            }
        }
        place(p, 0);
        in[p] = 1;
        seen[p] = 1;
        nres++;
        return false;
    }
};

// 19. DIP-set-duel
struct SetDuel : Policy {
    static const int NS = 16;
    LS mainCache, sa, sb;
    int cs, ca;
    bool bypass = false;
    u64 t = 0;
    int W;
    long long ma = 0, mb = 0;
    explicit SetDuel(int c)
        : Policy(c), mainCache(1), sa(1), sb(1), cs(C), ca(max(4, C / 16)), W(max(1000, C)) {}
    static void insBypass(LS& s, u32 p) {
        s.L[0].push_back(p);
        s.it[p] = prev(s.L[0].end());
        s.loc[p] = 0;
    }
    bool access(u32 p) override {
        t++;
        if (t % (u64)W == 0) {
            if (ma > mb) bypass = true;
            else if (mb > ma) bypass = false;
            ma = mb = 0;
        }
        bool hit = mainCache.loc[p] >= 0;
        if (hit) mainCache.rm(p);
        else if ((int)mainCache.sz(0) >= cs) mainCache.rm(mainCache.back(0));
        if (hit || !bypass) mainCache.pf(0, p);
        else insBypass(mainCache, p);

        if ((p & (NS - 1)) < NS / 2) {
            if (sa.loc[p] >= 0) sa.rm(p);
            else { ma++; if ((int)sa.sz(0) >= ca) sa.rm(sa.back(0)); }
            sa.pf(0, p);
        } else {
            if (sb.loc[p] >= 0) { sb.rm(p); sb.pf(0, p); }
            else { mb++; if ((int)sb.sz(0) >= ca) sb.rm(sb.back(0)); insBypass(sb, p); }
        }
        return hit;
    }
};

// 20. LRB-style Online Learned Reuse-Distance Predictor (Song et al., NSDI 2020 inspired).
// Learns an online ridge-SGD predictor of log(1 + next_reuse_distance) from
// observed reuse-distance labels within a bounded horizon M = max(64, 8*C)
// (including censored labels for evicted pages not reused within M). On
// eviction, samples K=32 resident candidates and evicts the largest predicted
// reuse distance. No future information is used.
struct LRBStyle : Policy {
    struct Feat { float f[6]; };
    vector<u32> res;
    vector<int> resPos;
    vector<u64> lastSeen, d1, d2;
    vector<double> edFreq;
    vector<Feat> prevFeat;
    deque<pair<u32, u64>> censorQ;
    vector<char> inCensor;
    double w[6] = {2.0, 1.2, 0.5, 0.25, -0.8, -0.3};
    u64 t = 0, horizon;
    double decayRate;
    RNG rng;

    explicit LRBStyle(int c)
        : Policy(c), resPos(NP, -1), lastSeen(NP, 0), d1(NP, 0), d2(NP, 0),
          edFreq(NP, 0.0), prevFeat(NP), inCensor(NP, 0),
          horizon((u64)max(64, 8 * C)), decayRate(1.0 / max(16.0, 2.0 * C)), rng(4242) {}

    Feat makeFeat(u32 p) const {
        Feat ft;
        u64 age = lastSeen[p] ? (t - lastSeen[p]) : horizon;
        double ef = lastSeen[p] ? edFreq[p] * exp(-decayRate * (double)age) : 0.0;
        ft.f[0] = 1.0f;
        ft.f[1] = (float)(log1p((double)age) / 12.0);
        ft.f[2] = d1[p] ? (float)(log1p((double)d1[p]) / 12.0) : 1.0f;
        ft.f[3] = d2[p] ? (float)(log1p((double)d2[p]) / 12.0) : 1.0f;
        ft.f[4] = (float)(log1p(ef) / 4.0);
        ft.f[5] = d1[p] > 0 ? 1.0f : 0.0f;
        return ft;
    }

    double predict(const Feat& ft) const {
        double y = 0.0;
        for (int i = 0; i < 6; i++) y += w[i] * ft.f[i];
        return y;
    }

    void sgdUpdate(const Feat& ft, double target) {
        double pred = predict(ft);
        double err = max(-4.0, min(4.0, pred - target));
        const double lr = 0.015, l2 = 1e-4;
        for (int i = 0; i < 6; i++) {
            w[i] -= lr * (err * ft.f[i] + l2 * w[i]);
        }
    }

    bool access(u32 p) override {
        t++;
        while (!censorQ.empty() && censorQ.front().second <= t) {
            u32 q = censorQ.front().first;
            censorQ.pop_front();
            if (inCensor[q]) {
                inCensor[q] = 0;
                if (resPos[q] < 0 && lastSeen[q] > 0 && (t - lastSeen[q]) >= horizon) {
                    sgdUpdate(prevFeat[q], log1p((double)horizon));
                }
            }
        }
        if (lastSeen[p] > 0) {
            u64 gap = t - lastSeen[p];
            if (gap <= horizon) sgdUpdate(prevFeat[p], log1p((double)gap));
            d2[p] = d1[p];
            d1[p] = gap;
            edFreq[p] = edFreq[p] * exp(-decayRate * (double)gap) + 1.0;
        } else {
            edFreq[p] = 1.0;
        }
        inCensor[p] = 0;
        lastSeen[p] = t;
        prevFeat[p] = makeFeat(p);

        if (resPos[p] >= 0) return true;

        if ((int)res.size() >= C) {
            int kSamp = min<int>(32, (int)res.size());
            int bestIdx = -1;
            double bestScore = -1e18;
            for (int i = 0; i < kSamp; i++) {
                int idx = (int)rng.n((u32)res.size());
                u32 q = res[idx];
                double sc = predict(makeFeat(q));
                if (sc > bestScore) { bestScore = sc; bestIdx = idx; }
            }
            u32 vic = res[bestIdx];
            u32 tail = res.back();
            res[bestIdx] = tail;
            resPos[tail] = bestIdx;
            res.pop_back();
            resPos[vic] = -1;
            if (!inCensor[vic]) {
                inCensor[vic] = 1;
                censorQ.push_back({vic, t + horizon});
            }
        }
        resPos[p] = (int)res.size();
        res.push_back(p);
        return false;
    }
};

static unique_ptr<Policy> mkPolicy(const string& name, int C) {
    if (name == "LRU") return make_unique<LRU>(C, false);
    if (name == "FIFO") return make_unique<FIFO>(C);
    if (name == "CLOCK") return make_unique<CLOCK>(C);
    if (name == "LFU-A") return make_unique<LFUA>(C, 4ull * max(1, C));
    if (name == "MRU") return make_unique<LRU>(C, true);
    if (name == "2Q") return make_unique<TwoQ>(C);
    if (name == "ARC") return make_unique<ARC>(C);
    if (name == "S3-FIFO") return make_unique<S3FIFO>(C);
    if (name == "LeCaR") return make_unique<LeCaR>(C);
    if (name == "LPR-style") return make_unique<LPR>(C);
    if (name == "SIEVE") return make_unique<SIEVE>(C);
    if (name == "W-TinyLFU") return make_unique<WTinyLFU>(C);
    if (name == "LHD") return make_unique<LHD>(C);
    if (name == "CAR") return make_unique<CAR>(C);
    if (name == "LIRS") return make_unique<LIRS>(C);
    if (name == "CLOCK-Pro") return make_unique<CLOCKPro>(C);
    if (name == "CACHEUS") return make_unique<CACHEUS>(C);
    if (name == "3L-style") return make_unique<ThreeL>(C);
    if (name == "MGLRU-style") return make_unique<MGLRU>(C);
    if (name == "DIP-set-duel") return make_unique<SetDuel>(C);
    if (name == "LRB-style") return make_unique<LRBStyle>(C);
    return nullptr;
}

static const vector<string>& allPolicyNames() {
    static const vector<string> v = {
        "LRU", "FIFO", "CLOCK", "LFU-A", "MRU", "2Q", "ARC", "S3-FIFO", "LeCaR",
        "LPR-style", "SIEVE", "W-TinyLFU", "LHD", "CAR", "LIRS", "CLOCK-Pro",
        "CACHEUS", "3L-style", "MGLRU-style", "DIP-set-duel", "LRB-style"
    };
    return v;
}

// ------------------------------------------------------------ Exact DP Oracle
struct PolicyRun {
    string name;
    vector<size_t> winMiss;
    size_t totalMiss = 0;
    double missRatio = 0.0;
    double nsPerRef = 0.0;
};

struct DPOracle {
    double missRatio = 0.0;
    double objectiveRatio = 0.0;
    size_t totalMiss = 0;
    size_t switches = 0;
    vector<size_t> chosen;
    vector<size_t> chosenMiss;
    vector<char> didSwitch;
};

static DPOracle solveDPOracle(const vector<PolicyRun>& ps, double switchCost,
                              size_t window, size_t nWin) {
    DPOracle res;
    size_t P = ps.size();
    res.chosen.assign(nWin, 0);
    res.chosenMiss.assign(nWin, 0);
    res.didSwitch.assign(nWin, 0);
    if (nWin == 0 || P == 0) return res;

    vector<vector<double>> dp(nWin, vector<double>(P, 0.0));
    vector<vector<int>> par(nWin, vector<int>(P, -1));
    for (size_t p = 0; p < P; p++) dp[0][p] = (double)ps[p].winMiss[0];

    for (size_t w = 1; w < nWin; w++) {
        // Find best and second-best previous states in O(P)
        size_t bestQ = 0, secondQ = 0;
        double bestV = numeric_limits<double>::infinity();
        double secondV = numeric_limits<double>::infinity();
        for (size_t q = 0; q < P; q++) {
            double v = dp[w - 1][q];
            if (v < bestV) {
                secondV = bestV; secondQ = bestQ;
                bestV = v; bestQ = q;
            } else if (v < secondV) {
                secondV = v; secondQ = q;
            }
        }
        for (size_t p = 0; p < P; p++) {
            double stay = dp[w - 1][p];
            size_t altQ = (bestQ == p && P > 1) ? secondQ : bestQ;
            double sw = dp[w - 1][altQ] + switchCost;
            if (stay <= sw) {
                dp[w][p] = stay + (double)ps[p].winMiss[w];
                par[w][p] = (int)p;
            } else {
                dp[w][p] = sw + (double)ps[p].winMiss[w];
                par[w][p] = (int)altQ;
            }
        }
    }

    size_t cur = 0;
    for (size_t p = 1; p < P; p++) {
        if (dp[nWin - 1][p] < dp[nWin - 1][cur]) cur = p;
    }
    for (size_t w = nWin; w-- > 0;) {
        res.chosen[w] = cur;
        if (w > 0) cur = (size_t)par[w][cur];
    }
    for (size_t w = 0; w < nWin; w++) {
        res.chosenMiss[w] = ps[res.chosen[w]].winMiss[w];
        res.totalMiss += res.chosenMiss[w];
        if (w > 0 && res.chosen[w] != res.chosen[w - 1]) {
            res.switches++;
            res.didSwitch[w] = 1;
        }
    }
    double evalRefs = (double)(nWin * window);
    res.missRatio = (double)res.totalMiss / evalRefs;
    res.objectiveRatio = ((double)res.totalMiss + (double)res.switches * switchCost) / evalRefs;
    return res;
}

// -------------------------------------------------- Switching Controllers
// Candidate pool for switching controller (6 diverse policies including S3-FIFO & ARC)
static const vector<string>& ctrlCands() {
    static const vector<string> v = {"LRU", "LFU-A", "2Q", "MRU", "S3-FIFO", "ARC"};
    return v;
}

struct CtrlCfg {
    string name;
    string trigger;   // cusum|ph|adwin|periodic|random|oracle_window|contshadow
    string budget;    // low|med|high|cont
    int W = 2000;
    double p = 0.2;
    double csCapF = 0.5;
    double cusumDelta = 0.5, cusumH = 5.0;
    double phDelta = 0.005, phLambda = 5.0;
    double adwinDelta = 0.002;
    int periodicEp = 20;
    double randomProb = 0.05;
    int oracleGapEp = 20; // minimum epochs between oracle-window triggers per budget
    int contEvery = 10;
    int evalDelay = 10, cooldown = 4, dwell = 10, hyst = 30;
    double z = 1.28, H = 50000.0, Kfrac = 0.0;
    bool persistentShadow = false;
    bool useAll21 = false;
};

struct CtrlOutcome {
    string name, trigger, budget;
    size_t evalRefs = 0;
    size_t totalMiss = 0;
    double missRatio = 0.0;
    double objectiveRatio = 0.0; // (totalMiss + switches * C) / evalRefs
    int switches = 0;
    int shadowEvals = 0;
    double nsPerRef = 0.0;
    u64 shadowCpuNs = 0;
    double usPerEval = 0.0;
};

struct SRef { u32 page; int ep; };

struct SwitchingController {
    int C;
    CtrlCfg cfg;
    unique_ptr<Policy> act;
    int actId = 4; // Start on S3-FIFO or LRU? Start on LRU (0), initial eval picks start
    int prevId = -1;
    u64 t = 0, ageRefs;
    int ep = 0, epochRefs = 0, epochMiss = 0;
    enum { BASE, MON, WAIT, COOL } st = BASE;
    bool firstBase = true;
    int B = 8;
    vector<double> bm;
    double mu = 0, sg = 0.02, Sp = 0, Sn = 0;
    double phMean = 0, phSum = 0, phMin = 0;
    long long phN = 0;
    vector<double> adwinWin;
    vector<u32> last;
    vector<uint16_t> cnt;
    u64 thr;
    vector<SRef> win;
    int confEp = 0, evalAt = 0, coolUntil = 0, lastSwitchEp = -1000;
    RNG trigRng;
    int switches = 0, shadowEvals = 0;
    u64 shadowCpuNs = 0;
    array<u64, 21> activeRefs{};
    const vector<size_t>* oracleSwitchRefs = nullptr;
    size_t nextOracleIdx = 0;
    vector<unique_ptr<Policy>> pShad;
    vector<array<double, 4>> pBlk;
    int pEpInWin = 0;

    const vector<string>& cands() const { return cfg.useAll21 ? allPolicyNames() : ctrlCands(); }

    SwitchingController(int c, const CtrlCfg& cfg_, const vector<size_t>* oRefs = nullptr)
        : C(max(1, c)), cfg(cfg_), act(mkPolicy(cands()[0], C)), actId(0),
          ageRefs((u64)50 * cfg_.W), last(NP, 0), cnt(NP, 0),
          trigRng(99), oracleSwitchRefs(oRefs) {
        thr = (cfg.p >= 1.0) ? 0xFFFFFFFFFFFFFFFFULL : (u64)(cfg.p * 18446744073709551615.0);
        if (cfg.persistentShadow) {
            for (const auto& nm : cands()) pShad.push_back(mkPolicy(nm, C));
            pBlk.assign(cands().size(), {0, 0, 0, 0});
        }
    }

    static u64 hsh(u32 x) {
        u64 z = x + 0x9e3779b97f4a7c15ULL;
        z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
        z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
        return z ^ (z >> 31);
    }

    struct Eval {
        bool ok = false;
        vector<array<double, 4>> blk;
        vector<double> tot;
        double Braw = 0;
    };

    Eval evaluate(int startEp) {
        u64 t0 = cpu_ns();
        Eval E;
        if (cfg.persistentShadow) {
            size_t nC = cands().size();
            E.blk = pBlk;
            E.tot.assign(nC, 0.0);
            for (size_t c = 0; c < nC; c++) {
                for (int b = 0; b < 4; b++) E.tot[c] += E.blk[c][b];
            }
            E.Braw = max(1.0, (double)max(1, pEpInWin) * cfg.W / 4.0);
            E.ok = true;
            pBlk.assign(nC, {0, 0, 0, 0});
            pEpInWin = 0;
            shadowEvals++;
            shadowCpuNs += (cpu_ns() - t0);
            return E;
        }
        vector<u32> w;
        for (const auto& s : win) if (s.ep >= startEp) w.push_back(s.page);
        if (w.size() < 100) return E;
        int Cs = max(8, (int)lround(cfg.p * C));
        if (cfg.csCapF > 0.0) {
            unordered_set<u32> uniq(w.begin(), w.end());
            int Dw = (int)uniq.size();
            Cs = min(Cs, max(8, (int)lround(cfg.csCapF * Dw)));
        }
        size_t wm = (size_t)(w.size() * 0.4), rest = w.size() - wm;
        size_t nC = cands().size();
        E.blk.assign(nC, {0, 0, 0, 0});
        E.tot.assign(nC, 0.0);
        for (size_t c = 0; c < nC; c++) {
            auto pol = mkPolicy(cands()[c], Cs);
            for (size_t i = 0; i < w.size(); i++) {
                bool h = pol->access(w[i]);
                if (i >= wm && !h) {
                    int b = min<int>(3, (int)((i - wm) * 4 / max<size_t>(1, rest)));
                    E.blk[c][b]++;
                    E.tot[c]++;
                }
            }
        }
        E.Braw = max(1.0, (double)(ep - startEp) * cfg.W * 0.6 / 4.0);
        E.ok = true;
        shadowEvals++;
        shadowCpuNs += (cpu_ns() - t0);
        return E;
    }

    int decide(const Eval& E, bool initial) {
        if (!E.ok) return actId;
        size_t nC = cands().size();
        if (initial) {
            int b = 0;
            for (size_t c = 1; c < nC; c++) if (E.tot[c] < E.tot[b]) b = (int)c;
            return b;
        }
        double K = cfg.Kfrac * C;
        double best = 0.0;
        int pick = actId;
        for (size_t c = 0; c < nC; c++) {
            if ((int)c == actId) continue;
            double d[4], m = 0.0;
            for (int b = 0; b < 4; b++) { d[b] = E.blk[actId][b] - E.blk[c][b]; m += d[b]; }
            m /= 4.0;
            double v = 0.0;
            for (int b = 0; b < 4; b++) v += (d[b] - m) * (d[b] - m);
            double sd = sqrt(v / 3.0);
            double lcb = m - cfg.z * sd / 2.0;
            double score = (lcb / cfg.p / E.Braw) * cfg.H - K;
            if ((int)c == prevId && ep - lastSwitchEp < cfg.hyst) score -= K;
            if (score > best) { best = score; pick = (int)c; }
        }
        return pick;
    }

    void switchTo(int id) {
        if (id == actId) return;
        auto pg = act->resident();
        sort(pg.begin(), pg.end(), [&](u32 a, u32 b) { return last[a] < last[b]; });
        vector<uint16_t> c;
        c.reserve(pg.size());
        for (u32 q : pg) c.push_back(cnt[q]);
        auto np = mkPolicy(cands()[id], C);
        np->load(pg, c);
        act = std::move(np);
        prevId = actId;
        actId = id;
        lastSwitchEp = ep;
        switches++;
    }

    void endEpoch() {
        double m = (double)epochMiss / cfg.W;
        epochMiss = 0;
        ep++;
        while (!win.empty() && win.front().ep < ep - 45) {
            win.erase(win.begin(), win.begin() + min<size_t>(win.size(), 20000));
        }
        if (st == BASE) {
            bm.push_back(m);
            if ((int)bm.size() == B) {
                double s = 0.0;
                for (double x : bm) s += x;
                mu = s / bm.size();
                double v = 0.0;
                for (double x : bm) v += (x - mu) * (x - mu);
                sg = max(0.02, sqrt(v / bm.size()));
                Sp = Sn = 0.0;
                phMean = 0.0; phN = 0; phSum = 0.0; phMin = 0.0;
                adwinWin.clear();
                if (firstBase) {
                    firstBase = false;
                    switchTo(decide(evaluate(ep - B), true));
                }
                st = MON;
            }
            return;
        }
        if (cfg.trigger == "contshadow") {
            if (ep % cfg.contEvery == 0) switchTo(decide(evaluate(ep - cfg.contEvery), false));
            return;
        }
        if (st == MON) {
            bool fired = false;
            if (cfg.trigger == "cusum") {
                double z = (m - mu) / sg;
                Sp = max(0.0, Sp + z - cfg.cusumDelta);
                Sn = max(0.0, Sn - z - cfg.cusumDelta);
                if (Sp > cfg.cusumH || Sn > cfg.cusumH) fired = true;
            } else if (cfg.trigger == "ph") {
                phN++;
                phMean += (m - phMean) / (double)phN;
                phSum += (m - phMean - cfg.phDelta);
                if (phSum < phMin) phMin = phSum;
                if (phSum - phMin > cfg.phLambda) {
                    fired = true;
                    phMean = 0.0; phN = 0; phSum = 0.0; phMin = 0.0;
                }
            } else if (cfg.trigger == "adwin") {
                adwinWin.push_back(m);
                if (adwinWin.size() > 200) adwinWin.erase(adwinWin.begin());
                size_t n = adwinWin.size();
                if (n >= 10) {
                    double total = 0.0;
                    for (double x : adwinWin) total += x;
                    double sum0 = 0.0;
                    for (size_t cut = 1; cut < n; cut++) {
                        sum0 += adwinWin[cut - 1];
                        size_t n0 = cut, n1 = n - cut;
                        if (n0 < 5 || n1 < 5) continue;
                        double mu0 = sum0 / n0, mu1 = (total - sum0) / n1;
                        double mH = 1.0 / (1.0 / n0 + 1.0 / n1);
                        double eps = sqrt(1.0 / (2.0 * mH) * log(4.0 * (double)n / max(1e-12, cfg.adwinDelta)));
                        if (fabs(mu0 - mu1) > eps) {
                            fired = true;
                            adwinWin.erase(adwinWin.begin(), adwinWin.begin() + (ptrdiff_t)cut);
                            break;
                        }
                    }
                }
            } else if (cfg.trigger == "periodic") {
                if (cfg.periodicEp > 0 && ep % cfg.periodicEp == 0) fired = true;
            } else if (cfg.trigger == "random") {
                if (cfg.randomProb > 0.0 && trigRng.u() < cfg.randomProb) fired = true;
            } else if (cfg.trigger == "oracle_window") {
                if (oracleSwitchRefs) {
                    while (nextOracleIdx < oracleSwitchRefs->size() &&
                           (*oracleSwitchRefs)[nextOracleIdx] < (size_t)(t > (u64)cfg.W ? t - cfg.W : 0)) {
                        nextOracleIdx++;
                    }
                    if (nextOracleIdx < oracleSwitchRefs->size() && (*oracleSwitchRefs)[nextOracleIdx] < (size_t)t) {
                        fired = true;
                        nextOracleIdx++;
                    }
                }
            }
            if (fired) {
                confEp = ep;
                evalAt = ep + cfg.evalDelay;
                st = WAIT;
                Sp = Sn = 0.0;
            }
            return;
        }
        if (st == WAIT) {
            if (ep >= evalAt) {
                int pick = decide(evaluate(confEp), false);
                if (ep - lastSwitchEp >= cfg.dwell) switchTo(pick);
                st = COOL;
                coolUntil = ep + cfg.cooldown;
            }
            return;
        }
        if (st == COOL) {
            if (ep >= coolUntil) { st = BASE; bm.clear(); }
        }
    }

    bool access(u32 p, bool countEval = false) {
        t++;
        if (countEval && actId >= 0 && actId < 21) activeRefs[actId]++;
        last[p] = (u32)min<u64>(t, 0xFFFFFFFFu);
        if (cnt[p] < 65535) cnt[p]++;
        if (ageRefs && t % ageRefs == 0) for (int i = 0; i < NP; i++) cnt[i] >>= 1;
        bool hit = act->access(p);
        if (!hit) epochMiss++;
        if (cfg.persistentShadow) {
            int totWinRefs = max(1, cfg.contEvery * cfg.W);
            int curPos = pEpInWin * cfg.W + epochRefs;
            int b = min(3, (int)((long long)curPos * 4 / totWinRefs));
            u64 ts0 = cpu_ns();
            for (size_t c = 0; c < pShad.size(); c++) {
                if (!pShad[c]->access(p)) pBlk[c][b]++;
            }
            shadowCpuNs += (cpu_ns() - ts0);
        } else if (cfg.p >= 1.0 || hsh(p) < thr) {
            win.push_back({p, ep});
        }
        if (++epochRefs == cfg.W) {
            epochRefs = 0;
            if (cfg.persistentShadow) pEpInWin++;
            endEpoch();
        }
        return hit;
    }
};

static vector<CtrlCfg> buildControllerSuite() {
    vector<CtrlCfg> v;
    auto add = [&](const string& name, const string& trig, const string& bud,
                   function<void(CtrlCfg&)> fn) {
        CtrlCfg c;
        c.name = name; c.trigger = trig; c.budget = bud;
        fn(c);
        v.push_back(c);
    };
    add("CUSUM-high", "cusum", "high", [](CtrlCfg& c){ c.cusumH = 3.0; });
    add("CUSUM-med", "cusum", "med", [](CtrlCfg& c){ c.cusumH = 5.0; });
    add("CUSUM-low", "cusum", "low", [](CtrlCfg& c){ c.cusumH = 8.0; });

    add("PH-high", "ph", "high", [](CtrlCfg& c){ c.phLambda = 2.0; });
    add("PH-med", "ph", "med", [](CtrlCfg& c){ c.phLambda = 5.0; });
    add("PH-low", "ph", "low", [](CtrlCfg& c){ c.phLambda = 9.0; });

    add("ADWIN-high", "adwin", "high", [](CtrlCfg& c){ c.adwinDelta = 0.02; });
    add("ADWIN-med", "adwin", "med", [](CtrlCfg& c){ c.adwinDelta = 0.002; });
    add("ADWIN-low", "adwin", "low", [](CtrlCfg& c){ c.adwinDelta = 0.0002; });

    add("Periodic-high", "periodic", "high", [](CtrlCfg& c){ c.periodicEp = 10; });
    add("Periodic-med", "periodic", "med", [](CtrlCfg& c){ c.periodicEp = 20; });
    add("Periodic-low", "periodic", "low", [](CtrlCfg& c){ c.periodicEp = 40; });

    add("Random-high", "random", "high", [](CtrlCfg& c){ c.randomProb = 0.10; });
    add("Random-med", "random", "med", [](CtrlCfg& c){ c.randomProb = 0.05; });
    add("Random-low", "random", "low", [](CtrlCfg& c){ c.randomProb = 0.025; });

    add("OracleTrig", "oracle_window", "oracle", [](CtrlCfg&){});
    add("ContShadow", "contshadow", "cont", [](CtrlCfg& c){ c.contEvery = 10; });
    return v;
}

int main(int argc, char** argv) {
    string mode = "all"; // oracle | controllers | all
    string tracePath, label = "trace", family = "", source = "", capFrac = "";
    string outPrefix;
    int C = 1000, np = 1 << 20;
    size_t window = 50000;

    for (int i = 1; i < argc; i++) {
        string a = argv[i];
        auto nx = [&]() { return string(argv[++i]); };
        if (a == "--mode") mode = nx();
        else if (a == "--trace") tracePath = nx();
        else if (a == "--label") label = nx();
        else if (a == "--family") family = nx();
        else if (a == "--source") source = nx();
        else if (a == "--cap-frac") capFrac = nx();
        else if (a == "--C") C = stoi(nx());
        else if (a == "--np") np = stoi(nx());
        else if (a == "--window") window = stoull(nx());
        else if (a == "--out-prefix") outPrefix = nx();
        else { fprintf(stderr, "unknown arg: %s\n", a.c_str()); return 2; }
    }
    if (tracePath.empty() || outPrefix.empty()) {
        fprintf(stderr, "usage: pathA_sim --trace FILE --label NAME --family FAM --source SRC --cap-frac F --C N --np N --window N --out-prefix PREFIX [--mode oracle|controllers|all]\n");
        return 2;
    }
    NP = np;

    vector<u32> refs;
    {
        ifstream in(tracePath, ios::binary);
        if (!in) { fprintf(stderr, "cannot open %s\n", tracePath.c_str()); return 1; }
        in.seekg(0, ios::end);
        size_t bytes = (size_t)in.tellg();
        in.seekg(0, ios::beg);
        refs.resize(bytes / sizeof(u32));
        in.read((char*)refs.data(), (streamsize)(refs.size() * sizeof(u32)));
    }
    if (refs.empty()) { fprintf(stderr, "empty trace\n"); return 1; }
    u32 maxPage = *max_element(refs.begin(), refs.end());
    if ((u64)maxPage + 1 > (u64)NP) NP = (int)min<u64>((u64)maxPage + 1, 1ULL << 28);

    unordered_set<u32> distinct(refs.begin(), refs.end());
    size_t wss = distinct.size();
    size_t warm = min<size_t>(100000, refs.size() / 10);
    size_t nEval = refs.size() - warm;
    size_t nWin = nEval / window;
    if (nWin == 0) { fprintf(stderr, "trace too short for window\n"); return 1; }
    size_t evalRefs = nWin * window;
    size_t evalEnd = warm + evalRefs;

    // 1. Always run all 21 static/adaptive/learned policies for oracle & oracle switch points
    const auto& polNames = allPolicyNames();
    vector<PolicyRun> pruns;
    pruns.reserve(polNames.size());
    for (const auto& pname : polNames) {
        auto p = mkPolicy(pname, C);
        PolicyRun pr;
        pr.name = pname;
        pr.winMiss.assign(nWin, 0);
        u64 t0 = cpu_ns();
        for (size_t i = 0; i < evalEnd; i++) {
            bool hit = p->access(refs[i]);
            if (i >= warm && !hit) pr.winMiss[(i - warm) / window]++;
        }
        u64 elapsed = cpu_ns() - t0;
        for (size_t m : pr.winMiss) pr.totalMiss += m;
        pr.missRatio = (double)pr.totalMiss / (double)evalRefs;
        pr.nsPerRef = (double)elapsed / (double)evalEnd;
        pruns.push_back(std::move(pr));
    }

    size_t bestIdx = 0, s3Idx = 0;
    for (size_t i = 0; i < pruns.size(); i++) {
        if (pruns[i].name == "S3-FIFO") s3Idx = i;
        if (pruns[i].totalMiss < pruns[bestIdx].totalMiss ||
            (pruns[i].totalMiss == pruns[bestIdx].totalMiss && pruns[i].name < pruns[bestIdx].name)) {
            bestIdx = i;
        }
    }
    double bestRatio = pruns[bestIdx].missRatio;
    double s3Ratio = pruns[s3Idx].missRatio;

    // Solve exact DP oracle for zero cost and full-cache-refill cost C
    DPOracle dpZero = solveDPOracle(pruns, 0.0, window, nWin);
    DPOracle dpCharged = solveDPOracle(pruns, (double)C, window, nWin);

    if (mode == "windows") {
        ofstream fw(outPrefix + "_windows.csv");
        fw << "trace,window_idx,s3fifo_mr,best_static_name,best_static_mr,oracle0_policy,oracle0_mr,oracle0_switch,oracleC_policy,oracleC_mr\n";
        for (size_t w = 0; w < nWin; w++) {
            fw << label << ',' << w << ',' << fixed << setprecision(6)
               << (double)pruns[s3Idx].winMiss[w] / (double)window << ','
               << pruns[bestIdx].name << ',' << (double)pruns[bestIdx].winMiss[w] / (double)window << ','
               << pruns[dpZero.chosen[w]].name << ',' << (double)dpZero.chosenMiss[w] / (double)window << ','
               << (dpZero.didSwitch[w] ? 1 : 0) << ','
               << pruns[dpCharged.chosen[w]].name << ',' << (double)dpCharged.chosenMiss[w] / (double)window << '\n';
        }
        return 0;
    }

    if (mode == "finesweep") {
        ofstream fsw(outPrefix + "_finesweep.csv");
        fsw << "trace,family,source,cap_frac,C,window,nwin,cost_frac,switch_cost,"
               "best_static,best_static_miss_ratio,s3fifo_miss_ratio,"
               "oracle_miss_ratio,oracle_switches,oracle_objective_ratio,net_gain_vs_best,net_gain_vs_s3fifo\n";
        for (double cf : {0.0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50, 1.00}) {
            double sc = cf * (double)C;
            DPOracle dpc = solveDPOracle(pruns, sc, window, nWin);
            fsw << label << ',' << family << ',' << source << ',' << capFrac << ','
                << C << ',' << window << ',' << nWin << ',' << fixed << setprecision(2) << cf << ','
                << setprecision(1) << sc << ',' << pruns[bestIdx].name << ','
                << setprecision(9) << bestRatio << ',' << s3Ratio << ','
                << setprecision(9) << dpc.missRatio << ','
                << dpc.switches << ',' << dpc.objectiveRatio << ','
                << (bestRatio - dpc.objectiveRatio) << ',' << (s3Ratio - dpc.objectiveRatio) << '\n';
        }
        return 0;
    }

    if (mode == "ranking") {
        // 1. Direct shadow ranking accuracy against full-cache window best among 6 candidates
        // Evaluate every 20,000 refs (10 epochs) across eval range [warm, evalEnd)
        ofstream fr(outPrefix + "_ranking.csv");
        fr << "trace,family,source,cap_frac,C,mode,evals,top1_agree,shadow_picks_s3,true_best_s3\n";
        const auto& c6 = ctrlCands();
        vector<unique_ptr<Policy>> fullCands;
        for (const auto& nm : c6) fullCands.push_back(mkPolicy(nm, C));
        for (size_t i = 0; i < warm; i++) for (auto& fc : fullCands) fc->access(refs[i]);

        u64 thr02 = (u64)(0.20 * 18446744073709551615.0);
        for (auto [mname, pSamp, csCapF] : vector<tuple<string,double,double>>{{"ContShadow-0.2C", 0.20, 0.50}, {"FullShadow-1.0C", 1.00, 0.00}}) {
            // Re-init fullCands cleanly
            vector<unique_ptr<Policy>> fc2;
            for (const auto& nm : c6) fc2.push_back(mkPolicy(nm, C));
            for (size_t i = 0; i < warm; i++) for (auto& p : fc2) p->access(refs[i]);
            int evals = 0, agree = 0, shS3 = 0, trS3 = 0;
            size_t step = 20000;
            for (size_t pos = warm; pos + step <= evalEnd; pos += step) {
                vector<size_t> trueMiss(6, 0);
                vector<u32> samp;
                for (size_t i = pos; i < pos + step; i++) {
                    for (size_t c = 0; c < 6; c++) if (!fc2[c]->access(refs[i])) trueMiss[c]++;
                    if (pSamp >= 1.0 || SwitchingController::hsh(refs[i]) < thr02) samp.push_back(refs[i]);
                }
                if (samp.size() < 100) continue;
                int Cs = max(8, (int)lround(pSamp * C));
                if (csCapF > 0.0) {
                    unordered_set<u32> uniq(samp.begin(), samp.end());
                    Cs = min(Cs, max(8, (int)lround(csCapF * (int)uniq.size())));
                }
                size_t wm = (size_t)(samp.size() * 0.4);
                vector<size_t> shMiss(6, 0);
                for (size_t c = 0; c < 6; c++) {
                    auto sp = mkPolicy(c6[c], Cs);
                    for (size_t i = 0; i < samp.size(); i++) {
                        bool h = sp->access(samp[i]);
                        if (i >= wm && !h) shMiss[c]++;
                    }
                }
                size_t trBest = min_element(trueMiss.begin(), trueMiss.end()) - trueMiss.begin();
                size_t shBest = min_element(shMiss.begin(), shMiss.end()) - shMiss.begin();
                evals++;
                if (trBest == shBest) agree++;
                if (c6[shBest] == "S3-FIFO") shS3++;
                if (c6[trBest] == "S3-FIFO") trS3++;
            }
            fr << label << ',' << family << ',' << source << ',' << capFrac << ',' << C << ','
               << mname << ',' << evals << ',' << agree << ',' << shS3 << ',' << trS3 << '\n';
        }

        // 2. ContShadow-21 (all 21 policies in candidate pool)
        CtrlCfg c21; c21.name = "ContShadow-21"; c21.trigger = "contshadow"; c21.budget = "cont21";
        c21.contEvery = 10; c21.useAll21 = true;
        SwitchingController ctrl21(C, c21, nullptr);
        size_t miss21 = 0;
        u64 t0 = cpu_ns();
        for (size_t i = 0; i < evalEnd; i++) {
            bool hit = ctrl21.access(refs[i], i >= warm);
            if (i >= warm && !hit) miss21++;
        }
        u64 el21 = cpu_ns() - t0;
        ofstream f21(outPrefix + "_pool21.csv");
        f21 << "trace,family,source,cap_frac,C,controller,miss_ratio,s3fifo_miss_ratio,switches,ns_per_ref\n";
        f21 << label << ',' << family << ',' << source << ',' << capFrac << ',' << C << ",ContShadow-21,"
            << fixed << setprecision(9) << ((double)miss21 / (double)evalRefs) << ','
            << s3Ratio << ',' << ctrl21.switches << ',' << setprecision(3) << ((double)el21 / (double)evalEnd) << '\n';
        return 0;
    }

    if (mode == "oracle" || mode == "all") {
        {
            ofstream fs(outPrefix + "_oracle_summary.csv");
            fs << "trace,family,source,cap_frac,C,wss,refs,warm,window,nwin,switch_cost,"
                  "best_static,best_static_miss_ratio,s3fifo_miss_ratio,"
                  "oracle_miss_ratio,oracle_switches,oracle_objective_ratio,"
                  "net_gain_vs_best,net_gain_vs_s3fifo,gross_gain_vs_best\n";
            for (const auto& pair : vector<pair<double, const DPOracle*>>{{0.0, &dpZero}, {(double)C, &dpCharged}}) {
                double sc = pair.first;
                const DPOracle* o = pair.second;
                fs << label << ',' << family << ',' << source << ',' << capFrac << ','
                   << C << ',' << wss << ',' << refs.size() << ',' << warm << ','
                   << window << ',' << nWin << ',' << fixed << setprecision(1) << sc << ','
                   << pruns[bestIdx].name << ',' << setprecision(9) << bestRatio << ',' << s3Ratio << ','
                   << o->missRatio << ',' << o->switches << ',' << o->objectiveRatio << ','
                   << (bestRatio - o->objectiveRatio) << ',' << (s3Ratio - o->objectiveRatio) << ','
                   << (bestRatio - o->missRatio) << '\n';
            }
        }
        {
            ofstream fsw(outPrefix + "_cost_sweep.csv");
            fsw << "trace,family,source,cap_frac,C,window,nwin,cost_frac,switch_cost,"
                   "oracle_miss_ratio,oracle_switches,oracle_objective_ratio,net_gain_vs_best,net_gain_vs_s3fifo\n";
            for (double cf : {0.0, 0.10, 0.25, 0.50, 1.00}) {
                double sc = cf * (double)C;
                DPOracle dpc = solveDPOracle(pruns, sc, window, nWin);
                fsw << label << ',' << family << ',' << source << ',' << capFrac << ','
                    << C << ',' << window << ',' << nWin << ',' << fixed << setprecision(2) << cf << ','
                    << setprecision(1) << sc << ',' << setprecision(9) << dpc.missRatio << ','
                    << dpc.switches << ',' << dpc.objectiveRatio << ','
                    << (bestRatio - dpc.objectiveRatio) << ',' << (s3Ratio - dpc.objectiveRatio) << '\n';
            }
        }
        {
            ofstream fp(outPrefix + "_policy.csv");
            fp << "trace,family,source,cap_frac,C,wss,window,policy,total_miss,miss_ratio,ns_per_ref\n";
            for (const auto& pr : pruns) {
                fp << label << ',' << family << ',' << source << ',' << capFrac << ','
                   << C << ',' << wss << ',' << window << ',' << pr.name << ','
                   << pr.totalMiss << ',' << fixed << setprecision(9) << pr.missRatio << ','
                   << setprecision(3) << pr.nsPerRef << '\n';
            }
        }
    }

    if (mode == "controllers" || mode == "all") {
        // Collect reference positions of zero-cost DP oracle switch boundaries
        // (or charged DP switch boundaries; zero-cost provides all true regime shifts)
        vector<size_t> oracleSwitchRefs;
        for (size_t w = 1; w < nWin; w++) {
            if (dpZero.didSwitch[w]) oracleSwitchRefs.push_back(warm + w * window);
        }

        ofstream fc(outPrefix + "_controllers.csv");
        fc << "trace,family,source,cap_frac,C,wss,window,controller,trigger,budget,"
              "eval_refs,total_miss,miss_ratio,switches,objective_ratio,shadow_evals,"
              "ns_per_ref,shadow_cpu_ns,us_per_eval\n";

        // Include static S3-FIFO measured identically in this suite
        fc << label << ',' << family << ',' << source << ',' << capFrac << ','
           << C << ',' << wss << ',' << window << ",S3-FIFO,static,static,"
           << evalRefs << ',' << pruns[s3Idx].totalMiss << ',' << fixed << setprecision(9) << s3Ratio << ','
           << "0," << s3Ratio << ",0," << setprecision(3) << pruns[s3Idx].nsPerRef << ",0,0.0\n";

        for (const auto& cfg : buildControllerSuite()) {
            SwitchingController ctrl(C, cfg, &oracleSwitchRefs);
            size_t miss = 0;
            u64 t0 = cpu_ns();
            for (size_t i = 0; i < evalEnd; i++) {
                bool hit = ctrl.access(refs[i], i >= warm);
                if (i >= warm && !hit) miss++;
            }
            u64 elapsed = cpu_ns() - t0;
            double mr = (double)miss / (double)evalRefs;
            double obj = ((double)miss + (double)ctrl.switches * (double)C) / (double)evalRefs;
            double nsRef = (double)elapsed / (double)evalEnd;
            double usEval = ctrl.shadowEvals ? ((double)ctrl.shadowCpuNs / 1000.0 / ctrl.shadowEvals) : 0.0;
            fc << label << ',' << family << ',' << source << ',' << capFrac << ','
               << C << ',' << wss << ',' << window << ',' << cfg.name << ',' << cfg.trigger << ',' << cfg.budget << ','
               << evalRefs << ',' << miss << ',' << fixed << setprecision(9) << mr << ','
               << ctrl.switches << ',' << obj << ',' << ctrl.shadowEvals << ','
               << setprecision(3) << nsRef << ',' << ctrl.shadowCpuNs << ',' << usEval << '\n';
        }
    }

    if (mode == "diag") {
        vector<size_t> oracleSwitchRefs;
        for (size_t w = 1; w < nWin; w++) {
            if (dpZero.didSwitch[w]) oracleSwitchRefs.push_back(warm + w * window);
        }
        ofstream fd(outPrefix + "_ctrl_diag.csv");
        fd << "trace,family,source,cap_frac,C,window,controller,miss_ratio,s3fifo_miss_ratio,switches,"
              "lru_frac,lfua_frac,q2_frac,mru_frac,s3fifo_frac,arc_frac\n";
        for (const auto& cfg : buildControllerSuite()) {
            if (cfg.name != "ContShadow" && cfg.name != "CUSUM-med" && cfg.name != "OracleTrig") continue;
            SwitchingController ctrl(C, cfg, &oracleSwitchRefs);
            size_t miss = 0;
            for (size_t i = 0; i < evalEnd; i++) {
                bool hit = ctrl.access(refs[i], i >= warm);
                if (i >= warm && !hit) miss++;
            }
            double mr = (double)miss / (double)evalRefs;
            fd << label << ',' << family << ',' << source << ',' << capFrac << ','
               << C << ',' << window << ',' << cfg.name << ',' << fixed << setprecision(9) << mr << ','
               << s3Ratio << ',' << ctrl.switches;
            for (int k = 0; k < 6; k++) {
                fd << ',' << setprecision(4) << ((double)ctrl.activeRefs[k] / (double)evalRefs);
            }
            fd << '\n';
        }
    }

    if (mode == "ablation") {
        vector<CtrlCfg> abSuite;
        {
            CtrlCfg c; c.name = "FullShadow"; c.trigger = "contshadow"; c.budget = "full";
            c.p = 1.0; c.csCapF = 0.0; c.Kfrac = 0.0; c.contEvery = 10;
            abSuite.push_back(c);
        }
        {
            CtrlCfg c; c.name = "FullShadow-CostAware"; c.trigger = "contshadow"; c.budget = "full_k1";
            c.p = 1.0; c.csCapF = 0.0; c.Kfrac = 1.0; c.contEvery = 10;
            abSuite.push_back(c);
        }
        {
            CtrlCfg c; c.name = "PersistentShadow"; c.trigger = "contshadow"; c.budget = "pers";
            c.p = 1.0; c.csCapF = 0.0; c.Kfrac = 0.0; c.contEvery = 10; c.persistentShadow = true;
            abSuite.push_back(c);
        }
        {
            CtrlCfg c; c.name = "PersistentShadow-CostAware"; c.trigger = "contshadow"; c.budget = "pers_k1";
            c.p = 1.0; c.csCapF = 0.0; c.Kfrac = 1.0; c.contEvery = 10; c.persistentShadow = true;
            abSuite.push_back(c);
        }
        ofstream fa(outPrefix + "_ablation.csv");
        fa << "trace,family,source,cap_frac,C,window,controller,miss_ratio,s3fifo_miss_ratio,switches,shadow_evals,ns_per_ref,"
              "lru_frac,lfua_frac,q2_frac,mru_frac,s3fifo_frac,arc_frac\n";
        for (const auto& cfg : abSuite) {
            SwitchingController ctrl(C, cfg, nullptr);
            size_t miss = 0;
            u64 t0 = cpu_ns();
            for (size_t i = 0; i < evalEnd; i++) {
                bool hit = ctrl.access(refs[i], i >= warm);
                if (i >= warm && !hit) miss++;
            }
            u64 elapsed = cpu_ns() - t0;
            double mr = (double)miss / (double)evalRefs;
            double nsRef = (double)elapsed / (double)evalEnd;
            fa << label << ',' << family << ',' << source << ',' << capFrac << ','
               << C << ',' << window << ',' << cfg.name << ',' << fixed << setprecision(9) << mr << ','
               << s3Ratio << ',' << ctrl.switches << ',' << ctrl.shadowEvals << ',' << setprecision(3) << nsRef;
            for (int k = 0; k < 6; k++) {
                fa << ',' << setprecision(4) << ((double)ctrl.activeRefs[k] / (double)evalRefs);
            }
            fa << '\n';
        }
    }
    return 0;
}
