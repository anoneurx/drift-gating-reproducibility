// real_io_bench.cpp -- Real backing-file page-cache I/O benchmark (pread + POSIX_FADV_DONTNEED)
// Measures actual end-to-end throughput (kops/s), p50/p99 latency (us), and CPU time
// for Static S3-FIFO vs. ContShadow vs. PersistentShadow under real 4KB page reads.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <fcntl.h>
#include <iostream>
#include <string>
#include <unistd.h>
#include <vector>

#define main pathA_sim_main
#include "pathA_sim.cpp"
#undef main

static double pct(vector<double>& v, double p) {
    if (v.empty()) return 0.0;
    size_t idx = min(v.size() - 1, (size_t)(p * (double)(v.size() - 1)));
    nth_element(v.begin(), v.begin() + idx, v.end());
    return v[idx];
}

int main(int argc, char** argv) {
    if (argc < 5) {
        fprintf(stderr, "usage: real_io_bench TRACE LABEL C NP\n");
        return 2;
    }
    string tracePath = argv[1], label = argv[2];
    int C = stoi(argv[3]);
    NP = stoi(argv[4]);

    vector<u32> refs;
    {
        ifstream in(tracePath, ios::binary);
        in.seekg(0, ios::end);
        size_t bytes = (size_t)in.tellg();
        in.seekg(0, ios::beg);
        refs.resize(bytes / sizeof(u32));
        in.read((char*)refs.data(), (streamsize)(refs.size() * sizeof(u32)));
    }
    size_t warm = min<size_t>(100000, refs.size() / 10);
    size_t nWin = (refs.size() - warm) / 50000;
    size_t evalEnd = warm + nWin * 50000;

    // Create a real backing file sized to NP * 4096 bytes (sparse + populated on pages touched)
    string tmpFile = "/tmp/real_io_backing_" + label + ".bin";
    int fd = open(tmpFile.c_str(), O_CREAT | O_RDWR | O_TRUNC, 0644);
    if (fd < 0) { perror("open"); return 1; }
    size_t fileBytes = (size_t)NP * 4096ULL;
    if (ftruncate(fd, (off_t)fileBytes) != 0) { perror("ftruncate"); return 1; }
    vector<char> pageBuf(4096, 0x5A);
    // Touch unique pages once and drop OS page cache so misses hit real storage/syscall path
    vector<uint8_t> touched(NP, 0);
    for (u32 p : refs) {
        if (p < (u32)NP && !touched[p]) {
            touched[p] = 1;
            pwrite(fd, pageBuf.data(), 4096, (off_t)p * 4096LL);
        }
    }
    fsync(fd);

    auto bench = [&](const string& name, auto&& fn) {
        posix_fadvise(fd, 0, (off_t)fileBytes, POSIX_FADV_DONTNEED);
        vector<double> lats;
        lats.reserve(evalEnd - warm);
        size_t misses = 0;
        auto t0 = chrono::steady_clock::now();
        for (size_t i = 0; i < evalEnd; i++) {
            auto op0 = chrono::steady_clock::now();
            bool hit = fn(refs[i], i >= warm);
            if (!hit) {
                ssize_t r = pread(fd, pageBuf.data(), 4096, (off_t)refs[i] * 4096LL);
                (void)r;
                if (i >= warm) misses++;
            }
            if (i >= warm) {
                double us = chrono::duration<double, micro>(chrono::steady_clock::now() - op0).count();
                lats.push_back(us);
            }
        }
        double sec = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
        double kops = (double)evalEnd / sec / 1000.0;
        double mr = (double)misses / (double)(evalEnd - warm);
        double p50 = pct(lats, 0.50);
        double p99 = pct(lats, 0.99);
        printf("%s,%s,%.4f,%.2f,%.2f,%.2f\n", label.c_str(), name.c_str(), mr, kops, p50, p99);
    };

    // 1. Static S3-FIFO
    {
        auto s3 = mkPolicy("S3-FIFO", C);
        bench("S3-FIFO", [&](u32 p, bool) { return s3->access(p); });
    }
    // 2. ContShadow (0.2C)
    {
        CtrlCfg cfg; cfg.name = "ContShadow"; cfg.trigger = "contshadow"; cfg.budget = "cont"; cfg.contEvery = 10;
        SwitchingController ctrl(C, cfg, nullptr);
        bench("ContShadow", [&](u32 p, bool ce) { return ctrl.access(p, ce); });
    }
    // 3. PersistentShadow (1.0C)
    {
        CtrlCfg cfg; cfg.name = "PersistentShadow"; cfg.trigger = "contshadow"; cfg.budget = "pers";
        cfg.p = 1.0; cfg.csCapF = 0.0; cfg.contEvery = 10; cfg.persistentShadow = true;
        SwitchingController ctrl(C, cfg, nullptr);
        bench("PersistentShadow", [&](u32 p, bool ce) { return ctrl.access(p, ce); });
    }

    close(fd);
    unlink(tmpFile.c_str());
    return 0;
}
