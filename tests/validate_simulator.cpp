// tests/validate_simulator.cpp
// Phase 2 & Phase 3 validation:
//   1. Hand-worked policy hit/miss sequences (LRU, FIFO, MRU, CLOCK, 2Q, ARC, S3-FIFO, SIEVE)
//   2. Brute-force P^T DP oracle verification
//   3. Independent-replay vs. state-carrying switching comparison
//   4. Direct switchTo() metadata-migration latency benchmark across C
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <limits>
#include <numeric>
#include <string>
#include <vector>

#define main pathA_sim_main
#include "../src/pathA_sim.cpp"
#undef main

static int g_pass = 0, g_fail = 0;

static void check(const string& name, bool ok, const string& msg = "") {
    if (ok) {
        g_pass++;
        printf("  PASS  %s\n", name.c_str());
    } else {
        g_fail++;
        printf("  FAIL  %s%s%s\n", name.c_str(), msg.empty() ? "" : ": ", msg.c_str());
    }
}

static string hitStr(const string& polName, int C, const vector<u32>& seq) {
    auto p = mkPolicy(polName, C);
    string out;
    for (u32 x : seq) out.push_back(p->access(x) ? 'H' : 'M');
    return out;
}

// Brute-force P^T solver for small P, nWin
static double bruteForceDP(const vector<PolicyRun>& ps, double switchCost, size_t window, size_t nWin, size_t& outSwitches) {
    size_t P = ps.size();
    size_t totalSchedules = 1;
    for (size_t w = 0; w < nWin; w++) totalSchedules *= P;
    double bestObj = numeric_limits<double>::infinity();
    size_t bestSw = 0;
    for (size_t mask = 0; mask < totalSchedules; mask++) {
        size_t tmp = mask;
        vector<size_t> sched(nWin);
        for (size_t w = 0; w < nWin; w++) {
            sched[w] = tmp % P;
            tmp /= P;
        }
        double miss = 0.0;
        size_t sw = 0;
        for (size_t w = 0; w < nWin; w++) {
            miss += (double)ps[sched[w]].winMiss[w];
            if (w > 0 && sched[w] != sched[w - 1]) sw++;
        }
        double obj = (miss + (double)sw * switchCost) / (double)(nWin * window);
        if (obj < bestObj - 1e-12) {
            bestObj = obj;
            bestSw = sw;
        }
    }
    outSwitches = bestSw;
    return bestObj;
}

int main() {
    NP = 1 << 16;
    printf("=================================================================\n");
    printf("Phase 2 & 3: Simulator & Viterbi DP Oracle Validation\n");
    printf("=================================================================\n");

    // 1. Hand-worked trace: {1,2,3,4,1,2,5,1,2,3,4,5}, C=3
    // LRU:   1(M) 2(M) 3(M) 4(M,ev1) 1(M,ev2) 2(M,ev3) 5(M,ev4) 1(H) 2(H) 3(M,ev5) 4(M,ev1) 5(M,ev2) -> 10 misses, 2 hits
    // FIFO:  1(M) 2(M) 3(M) 4(M,ev1) 1(M,ev2) 2(M,ev3) 5(M,ev4) 1(H) 2(H) 3(M,ev1) 4(M,ev2) 5(H)     -> 9 misses, 3 hits
    // MRU:   1(M) 2(M) 3(M) 4(M,ev3) 1(H) 2(H) 5(M,ev2) 1(H) 2(M,ev1) 3(M,ev2) 4(H) 5(H)           -> 7 misses, 5 hits
    vector<u32> beladySeq = {1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5};
    check("LRU hand-worked C=3",  hitStr("LRU", 3, beladySeq)  == "MMMMMMMHHMMM", hitStr("LRU", 3, beladySeq));
    check("FIFO hand-worked C=3", hitStr("FIFO", 3, beladySeq) == "MMMMMMMHHMMH", hitStr("FIFO", 3, beladySeq));
    check("MRU hand-worked C=3",  hitStr("MRU", 3, beladySeq)  == "MMMMHHMHMMHH", hitStr("MRU", 3, beladySeq));

    // Repeated reference test: {1,1,1,1,1}, C=1
    check("Repeated-ref LRU C=1",     hitStr("LRU", 1, {1,1,1,1,1}) == "MHHHH");
    check("Repeated-ref CLOCK C=1",   hitStr("CLOCK", 1, {1,1,1,1,1}) == "MHHHH");
    check("Repeated-ref S3-FIFO C=2", hitStr("S3-FIFO", 2, {1,1,1,1,1}) == "MHHHH");
    check("Repeated-ref ARC C=2",     hitStr("ARC", 2, {1,1,1,1,1}) == "MHHHH");
    check("Repeated-ref SIEVE C=2",   hitStr("SIEVE", 2, {1,1,1,1,1}) == "MHHHH");

    // Sequential scan after hot set: hot={1,2,3,4} x5, scan={10..29}, hot={1,2,3,4}, C=6
    vector<u32> scanSeq;
    for (int r = 0; r < 5; r++) for (u32 x = 1; x <= 4; x++) scanSeq.push_back(x);
    for (u32 x = 10; x < 30; x++) scanSeq.push_back(x);
    for (u32 x = 1; x <= 4; x++) scanSeq.push_back(x);
    auto countMiss = [](const string& s) {
        int m = 0; for (char c : s) if (c == 'M') m++; return m;
    };
    int lruScanM = countMiss(hitStr("LRU", 6, scanSeq));
    int s3ScanM  = countMiss(hitStr("S3-FIFO", 6, scanSeq));
    int arcScanM = countMiss(hitStr("ARC", 6, scanSeq));
    check("Scan resistance: S3-FIFO <= LRU", s3ScanM <= lruScanM,
          "S3=" + to_string(s3ScanM) + " LRU=" + to_string(lruScanM));
    check("Scan resistance: ARC <= LRU", arcScanM <= lruScanM,
          "ARC=" + to_string(arcScanM) + " LRU=" + to_string(lruScanM));

    // Capacity monotonicity for S3-FIFO and LRU on mixed trace
    vector<u32> mixSeq;
    for (int i = 0; i < 400; i++) mixSeq.push_back((u32)((i * 7 + (i / 40) * 13) % 30));
    int m5 = countMiss(hitStr("S3-FIFO", 5, mixSeq));
    int m10 = countMiss(hitStr("S3-FIFO", 10, mixSeq));
    int m20 = countMiss(hitStr("S3-FIFO", 20, mixSeq));
    check("S3-FIFO capacity monotonicity (C=5 >= C=10 >= C=20)", m5 >= m10 && m10 >= m20);

    // 2. Brute-force P^T DP Oracle verification (P=4, nWin=5)
    vector<PolicyRun> ps(4);
    ps[0].name = "P0"; ps[0].winMiss = {10, 50, 10, 50, 10};
    ps[1].name = "P1"; ps[1].winMiss = {50, 10, 50, 10, 50};
    ps[2].name = "P2"; ps[2].winMiss = {25, 25, 25, 25, 25};
    ps[3].name = "P3"; ps[3].winMiss = {12, 12, 40, 40, 12};
    for (double sc : {0.0, 15.0, 35.0, 100.0}) {
        DPOracle dp = solveDPOracle(ps, sc, 100, 5);
        size_t bfSw = 0;
        double bfObj = bruteForceDP(ps, sc, 100, 5, bfSw);
        bool ok = fabs(dp.objectiveRatio - bfObj) < 1e-12;
        check("Viterbi DP == BruteForce (sc=" + to_string((int)sc) + ")", ok,
              "dp=" + to_string(dp.objectiveRatio) + " bf=" + to_string(bfObj));
    }

    // 3. Independent-replay vs. State-carrying switching on phase-shifting trace
    // Phase 1 (2000 refs): working set {0..9} repeated -> LRU/S3-FIFO optimal
    // Phase 2 (2000 refs): cyclic scan {100..115} at C=10 -> MRU optimal, LRU thrashes
    // Phase 3 (2000 refs): working set {0..9} repeated -> LRU/S3-FIFO optimal
    {
        const int C = 10;
        const size_t W = 2000;
        vector<u32> tr;
        for (size_t i = 0; i < W; i++) tr.push_back((u32)(i % 10));
        for (size_t i = 0; i < W; i++) tr.push_back((u32)(100 + (i % 16)));
        for (size_t i = 0; i < W; i++) tr.push_back((u32)(i % 10));

        // Independent replay (LRU, MRU, S3-FIFO)
        auto runInd = [&](const string& nm) {
            auto pol = mkPolicy(nm, C);
            vector<size_t> wm(3, 0);
            for (size_t i = 0; i < 3 * W; i++) if (!pol->access(tr[i])) wm[i / W]++;
            return wm;
        };
        auto mLRU = runInd("LRU"), mMRU = runInd("MRU"), mS3 = runInd("S3-FIFO");
        size_t indOracle0 = min(mLRU[0], min(mMRU[0], mS3[0]))
                          + min(mLRU[1], min(mMRU[1], mS3[1]))
                          + min(mLRU[2], min(mMRU[2], mS3[2]));
        // State-carrying execution following schedule: LRU -> MRU -> LRU with switchTo() metadata migration
        auto act = mkPolicy("LRU", C);
        vector<u32> last(NP, 0);
        vector<uint16_t> cnt(NP, 0);
        size_t scMiss = 0;
        for (size_t i = 0; i < 3 * W; i++) {
            if (i == W || i == 2 * W) {
                string nxt = (i == W) ? "MRU" : "LRU";
                auto pg = act->resident();
                sort(pg.begin(), pg.end(), [&](u32 a, u32 b) { return last[a] < last[b]; });
                vector<uint16_t> cv; cv.reserve(pg.size());
                for (u32 q : pg) cv.push_back(cnt[q]);
                auto np = mkPolicy(nxt, C);
                np->load(pg, cv);
                act = std::move(np);
            }
            u32 p = tr[i];
            last[p] = (u32)(i + 1);
            if (cnt[p] < 65535) cnt[p]++;
            if (!act->access(p)) scMiss++;
        }
        printf("  INFO  Phase-shift trace (3x2000, C=10): indReplay_c0=%zu (%.4f), stateCarrying=%zu (%.4f), diff=%+zd misses\n",
               indOracle0, (double)indOracle0 / (3 * W), scMiss, (double)scMiss / (3 * W),
               (ssize_t)scMiss - (ssize_t)indOracle0);
        check("State-carrying misses >= independent-replay c=0 bound", scMiss >= indOracle0);
    }

    // 4. Direct switchTo() metadata-migration latency benchmark (n=30 trials per C)
    printf("\n--- Direct switchTo() Metadata-Migration Latency (S3-FIFO -> ARC, n=30) ---\n");
    printf("C,mean_us,sd_us,ci95_lo_us,ci95_hi_us,us_per_page\n");
    for (int C : {64, 512, 4096, 16384}) {
        vector<double> us;
        for (int trial = 0; trial < 30; trial++) {
            auto s3 = mkPolicy("S3-FIFO", C);
            vector<u32> last(NP, 0);
            vector<uint16_t> cnt(NP, 1);
            for (int i = 0; i < C * 2; i++) {
                u32 p = (u32)(i % (C + 10));
                s3->access(p);
                last[p] = (u32)(i + 1);
            }
            auto t0 = chrono::steady_clock::now();
            auto pg = s3->resident();
            sort(pg.begin(), pg.end(), [&](u32 a, u32 b) { return last[a] < last[b]; });
            vector<uint16_t> cv; cv.reserve(pg.size());
            for (u32 q : pg) cv.push_back(cnt[q]);
            auto arc = mkPolicy("ARC", C);
            arc->load(pg, cv);
            double el = chrono::duration<double, micro>(chrono::steady_clock::now() - t0).count();
            us.push_back(el);
        }
        double mean = accumulate(us.begin(), us.end(), 0.0) / us.size();
        double var = 0.0;
        for (double x : us) var += (x - mean) * (x - mean);
        double sd = sqrt(var / (us.size() - 1));
        double se = sd / sqrt((double)us.size());
        printf("%d,%.2f,%.2f,%.2f,%.2f,%.4f\n", C, mean, sd, mean - 1.96 * se, mean + 1.96 * se, mean / C);
    }

    printf("=================================================================\n");
    printf("Results: %d passed, %d failed\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
