// Page-fault latency calibration microbenchmark.
//
// This is NOT a kernel page-replacement prototype and does not implement DA.
// It measures the user-space cost of (a) a resident 4 KiB page access, (b) a
// first-touch minor fault on a fresh anonymous mapping, and (c) a refault
// after MADV_DONTNEED, which discards the page and forces it to be faulted
// back in.  Those numbers calibrate the cost-model break-even in
// cost_model.py: if a miss costs less than the break-even, drift gating wins
// on total time; if it costs more, continuous shadow evaluation wins.
//
// Build: g++ -O2 -std=c++17 -o prototype_fault_latency prototype_fault_latency.cpp
// Run:   ./prototype_fault_latency
#include <algorithm>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <vector>
#include <sys/mman.h>
#include <unistd.h>

static const size_t PAGE = 4096;
static const size_t N = 32768;          // 128 MiB of 4 KiB pages
static const size_t BYTES = N * PAGE;

static double now_ns() {
    timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1e9 + ts.tv_nsec;
}

static void touch_all(volatile char* p, size_t n) {
    for (size_t i = 0; i < n; i++) p[i * PAGE] = (char)(i & 0x7f);
}

static double median(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    size_t n = v.size();
    return n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}

int main() {
    long ps = sysconf(_SC_PAGESIZE);
    if ((size_t)ps != PAGE) {
        fprintf(stderr, "warning: system page size %ld, using %zu\n", ps, PAGE);
    }

    // Resident-access baseline: one warm mapping, no faults after the first
    // pass.  Subtract this per-access cost from the fault measurements.
    char* base = (char*)mmap(nullptr, BYTES, PROT_READ | PROT_WRITE,
                             MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (base == MAP_FAILED) { perror("mmap"); return 1; }
    madvise(base, BYTES, MADV_NOHUGEPAGE);
    touch_all((volatile char*)base, N);

    std::vector<double> resident, first_touch, refault;
    for (int rep = 0; rep < 7; rep++) {
        double t0 = now_ns();
        touch_all((volatile char*)base, N);
        double t1 = now_ns();
        resident.push_back((t1 - t0) / N);

        // First-touch minor faults on a fresh mapping.  The mmap/munmap cost
        // is measured separately and subtracted below only in the report.
        char* fresh = (char*)mmap(nullptr, BYTES, PROT_READ | PROT_WRITE,
                                  MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (fresh == MAP_FAILED) { perror("mmap fresh"); return 1; }
        madvise(fresh, BYTES, MADV_NOHUGEPAGE);
        t0 = now_ns();
        touch_all((volatile char*)fresh, N);
        t1 = now_ns();
        first_touch.push_back((t1 - t0) / N);
        munmap(fresh, BYTES);

        // Refault after the pages are discarded, the trace-replay analogue of
        // a reclaim/eviction followed by a re-reference.
        madvise(base, BYTES, MADV_DONTNEED);
        t0 = now_ns();
        touch_all((volatile char*)base, N);
        t1 = now_ns();
        refault.push_back((t1 - t0) / N);
    }

    double r = median(resident);
    double ft = median(first_touch);
    double rf = median(refault);
    double fault_ft = ft - r;
    double fault_rf = rf - r;

    printf("pages=%zu page_size=%zu bytes=%zu reps=7 (median)\n", N, PAGE, BYTES);
    printf("resident_access_ns=%.2f\n", r);
    printf("first_touch_ns_per_page=%.2f\n", ft);
    printf("refault_after_madv_dontneed_ns_per_page=%.2f\n", rf);
    printf("first_touch_minor_fault_ns=%.2f\n", fault_ft);
    printf("refault_minor_fault_ns=%.2f\n", fault_rf);
    printf("first_touch_minor_fault_us=%.3f\n", fault_ft / 1000.0);
    printf("refault_minor_fault_us=%.3f\n", fault_rf / 1000.0);
    printf("# Compare with cost_model.py break-even ~2.20 us per miss.\n");

    munmap(base, BYTES);
    return 0;
}
