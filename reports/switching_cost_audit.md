# Phase 6: Switching-Cost Model and Migration Benchmark Audit

**Audited Components:** Proposition 1 (`main_template.tex:126`), `SwitchingController::switchTo()` (`src/pathA_sim.cpp:1368-1382`), `src/real_io_bench.cpp`  
**Audit Branch:** `research-validation-revision`  
**Date:** 2026-11-26

---

## 1. Mathematical Verification of Proposition 1

In the independent-replay DP model, each switch incurs a fixed penalty $c_{\text{switch}} = \beta C$ measured in **miss-equivalents** (units: cache misses). Suppose a schedule performs $S \ge 1$ switches, dividing the $T$ windows of length $W$ into $S+1$ contiguous dwell segments.

For a single switch entering a dwell of $L \in \{1, \dots, T-1\}$ windows (spanning $L \cdot W$ references):
- Let $\Delta M = \sum_{t \in \text{dwell}} (m_{t, p_{\text{static}}^*} - m_{t, p_t^*})$ be the cumulative miss reduction (in misses) over the dwell relative to staying on the static baseline.
- Let $\overline{\Delta m} = \frac{\Delta M}{L \cdot W}$ be the **mean miss-ratio reduction** across the $L$ windows of the dwell.
- Net objective gain is positive iff $\Delta M > c_{\text{switch}}$, which is equivalent in miss-ratio units to:
  $$\overline{\Delta m} = \frac{\Delta M}{L \cdot W} > \frac{c_{\text{switch}}}{L \cdot W} = \frac{\beta C}{L \cdot W}.$$

**Key Properties Verified:**
1. **Units:** $c_{\text{switch}}$ is in misses; $W \cdot L$ is in references; therefore $c_{\text{switch}} / (W \cdot L)$ is dimensionless (miss ratio), matching $\overline{\Delta m}$.
2. **Multiple switches:** Across $S$ switches over $T$ total windows ($T \cdot W$ references), total net gain is positive iff $\sum_{t=1}^T (m_{t,p^*} - m_{t,p_t^*}) > S \cdot c_{\text{switch}}$, i.e., trace-wide mean miss-ratio reduction exceeds $S \cdot c_{\text{switch}} / (T \cdot W)$.
3. **Window-length sensitivity:** Halving $W$ from $50{,}000$ to $5{,}000$ doubles/decuples the required single-window $\overline{\Delta m}$ if $L=1$, *unless* the regime persists across $L \propto 1/W$ windows (fixed physical dwell in references). Thus finer windows help only when phase transitions occur at sub-$50\text{k}$ boundaries, allowing tighter alignment without shortening total dwell $L \cdot W$.
4. **Model scope:** $c_{\text{switch}} = \beta C$ is an **assumed normalized miss-equivalent penalty scenario** ($\beta \in [0, 1]$), not an empirically calibrated hardware latency.

---

## 2. Direct `switchTo()` Metadata-Migration Latency Benchmark

### 2.1 System & Methodology
- **CPU:** AMD Ryzen 5 3500U (4 cores / 8 threads, x86_64)
- **RAM:** 29 GiB (`free -h`)
- **OS / Kernel:** Linux 7.1.5+kali-amd64 (`#1 SMP PREEMPT_DYNAMIC`)
- **Compiler:** `g++ (Debian 16.2.0-3) 16.2.0`, flags `-O2 -std=c++17`
- **Protocol:** `NP = 100,000`, `WARMUP = 5` untimed switches, `TRIALS = 50` timed `switchTo(ARC)` calls from `S3-FIFO` after `2C` references (`chrono::steady_clock`).

### 2.2 Results (50 Timed Trials per $C$)

| $C$ (pages) | Mean ($\mu$s) | SD ($\mu$s) | Median ($\mu$s) | $p_{95}$ ($\mu$s) | $p_{99}$ ($\mu$s) | Mean $\mu$s/page |
|---:|---:|---:|---:|---:|---:|---:|
| 64 | 438.16 | 41.10 | 418.98 | 509.99 | 516.69 | 6.8463 |
| 512 | 48.19 | 2.05 | 48.75 | 49.73 | 53.01 | 0.0941 |
| 4,096 | 241.53 | 14.95 | 235.44 | 270.57 | 280.13 | 0.0590 |
| 16,384 | 955.72 | 115.78 | 930.22 | 1,037.29 | 1,163.91 | 0.0583 |

**Root Cause of Variability at Small $C$:** `mkPolicy()` allocates `O(NP)` arrays (`loc`, `f`, etc., here `NP = 100,000` $\approx$ 400 KB) inside `switchTo()`, so small-$C$ switches are dominated by allocator/page-fault overhead rather than `O(C log C)` resident-page sorting.

---

## 3. Separation from `real_io_bench` (`pread` Microbenchmark)

`results/raw/real_io_bench.csv` measures user-space `pread` throughput and latency against an OS page-cache-backed file (`sqlite_join_agg_s101`: `S3-FIFO` $p_{50}=1.47\,\mu$s, $p_{99}=4.75\,\mu$s, $319.26$\,kops/s vs. `PersistentShadow` $p_{50}=4.68\,\mu$s, $p_{99}=7.05\,\mu$s, $168.22$\,kops/s). This reflects **Linux syscall + DRAM page-cache copy + simulator CPU overhead**, **NOT** NVMe storage I/O or metadata-migration cost, and must never be presented as direct proof of migration overhead.
