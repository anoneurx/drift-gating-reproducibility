# Phase 3: Independent Simulator Validation Report

**Target Simulator:** `src/pathA_sim.cpp`  
**Validation Suite:** `tests/external_validation/ref_policies.py`, `tests/external_validation/dump_policies.cpp`, `tests/external_validation/run_cross_validation.py`  
**Audit Branch:** `research-validation-revision`  
**Date:** 2026-11-26

---

## 1. External Tooling Availability

- **`libCacheSim`:** Not installed on the host (`which cachesim`, `python3 -c "import libcachesim"`, and `pkg-config --modversion libCacheSim` all returned not found; sandbox is offline).
- **Mitigation:** Implemented clean, independent textbook/paper reference implementations in Python (`tests/external_validation/ref_policies.py`) for the five core policies:
  1. `LRU` (standard doubly-linked list / `OrderedDict`)
  2. `FIFO` (standard queue)
  3. `ARC` (Megiddo & Modha, FAST 2003)
  4. `S3-FIFO` (Yang et al., SOSP 2023, enforcing strict resident invariant $|S| + |M| \le C$)
  5. `SIEVE` (Zhang et al., NSDI 2024, Algorithm 1)

---

## 2. Cross-Validation Setup

Both `src/pathA_sim.cpp` (`mkPolicy`) and `tests/external_validation/ref_policies.py` were executed with identical reference streams, capacities $C$, warm-up prefix $N_{\text{warm}} = \min(100{,}000, \lfloor N/10 \rfloor)$, and evaluation miss-ratio definition ($\text{eval\_misses} / (N - N_{\text{warm}})$) across:
- `synth_zipf`: 20,000 synthetic Zipfian references ($\alpha = 1.8 \bmod 500$), $C \in \{10, 50\}$.
- `btree_s101.bin`, `hashjoin_s101.bin`, `bfs_s101.bin`: 300,000-reference real instrumented traces from `traces_real/`, at $1\%, 5\%, 10\%$ WSS.

---

## 3. Exact Results

| Trace | $C$ | Policy | `pathA_sim` evalM | Reference evalM | Diff | `pathA_sim` MR | Reference MR | Status |
|---|---:|---|---:|---:|---:|---:|---:|---|
| `synth_zipf` | 10 | `LRU` | 2,794 | 2,794 | **0** | 0.155222 | 0.155222 | EXACT MATCH |
| `synth_zipf` | 10 | `FIFO` | 3,732 | 3,732 | **0** | 0.207333 | 0.207333 | EXACT MATCH |
| `synth_zipf` | 10 | `ARC` | 2,362 | 2,362 | **0** | 0.131222 | 0.131222 | EXACT MATCH |
| `synth_zipf` | 10 | `S3-FIFO` | 1,395 | 2,043 | **-648** | 0.077500 | 0.113500 | **DIVERGENCE** |
| `synth_zipf` | 10 | `SIEVE` | 2,138 | 2,138 | **0** | 0.118778 | 0.118778 | EXACT MATCH |
| `synth_zipf` | 50 | `LRU` | 769 | 769 | **0** | 0.042722 | 0.042722 | EXACT MATCH |
| `synth_zipf` | 50 | `FIFO` | 1,091 | 1,091 | **0** | 0.060611 | 0.060611 | EXACT MATCH |
| `synth_zipf` | 50 | `ARC` | 607 | 607 | **0** | 0.033722 | 0.033722 | EXACT MATCH |
| `synth_zipf` | 50 | `S3-FIFO` | 398 | 585 | **-187** | 0.022111 | 0.032500 | **DIVERGENCE** |
| `synth_zipf` | 50 | `SIEVE` | 567 | 567 | **0** | 0.031500 | 0.031500 | EXACT MATCH |
| `btree_s101` | 113 | `LRU`, `FIFO`, `ARC`, `SIEVE` | — | — | **0** | — | — | EXACT MATCH |
| `btree_s101` | 113 | `S3-FIFO` | 113,683 | 133,761 | **-20,078** | 0.421048 | 0.495411 | **DIVERGENCE** |
| `btree_s101` | 565 | `LRU`, `FIFO`, `ARC`, `SIEVE` | — | — | **0** | — | — | EXACT MATCH |
| `btree_s101` | 565 | `S3-FIFO` | 66,168 | 86,811 | **-20,643** | 0.245067 | 0.321522 | **DIVERGENCE** |
| `btree_s101` | 1130 | `LRU`, `FIFO`, `ARC`, `SIEVE` | — | — | **0** | — | — | EXACT MATCH |
| `btree_s101` | 1130 | `S3-FIFO` | 45,851 | 66,508 | **-20,657** | 0.169819 | 0.246326 | **DIVERGENCE** |
| `hashjoin_s101` | 10/50/101 | `LRU`, `FIFO`, `ARC`, `SIEVE` | — | — | **0** | — | — | EXACT MATCH |
| `hashjoin_s101` | 10/50/101 | `S3-FIFO` | — | — | **-1,346 / -7,339 / -12,074** | — | — | **DIVERGENCE** |
| `bfs_s101` | 11/53/106 | `LRU`, `FIFO`, `ARC`, `SIEVE` | — | — | **0** | — | — | EXACT MATCH |
| `bfs_s101` | 11/53/106 | `S3-FIFO` | — | — | **-10,217 / -1,706 / -1,578** | — | — | **DIVERGENCE** |

---

## 4. Critical Discovery: Capacity-Invariant Bug in `S3FIFO` (`src/pathA_sim.cpp:299-325`)

Direct instrumentation of `S3FIFO` in `src/pathA_sim.cpp` reveals **two bugs** that violate the cache capacity invariant $|S| + |M| \le C$:

1. **Promotion without eviction when $|M| < M_{\text{cap}}$ (`src/pathA_sim.cpp:305-308`):**  
   During warm-up, items enter $S$ until $|S| = C$ ($|M| = 0$). On subsequent misses, if the tail $t$ of $S$ has `f[t] > 0`, `evict()` pops $t$ from $S$, skips `evictMain()` (because `sz(1) < M`), pushes $t$ into $M$, and returns. `access()` then inserts the new page into $S$, increasing $|S| + |M|$ beyond $C$.
2. **Ghost-hit insertion into $M$ after evicting from $S$ (`src/pathA_sim.cpp:320-325`):**  
   When `g == true` (ghost hit), `evict()` evicts from $S$ whenever $|S| \ge S_{\text{cap}}$, yet `access()` inserts the ghost-hit page into $M$ (`s.pf(1, x)`). Consequently, $|M|$ grows far beyond $M_{\text{cap}}$ while $|S|$ remains at $S_{\text{cap}}$.

**Measured Capacity Overrun (`btree_s101`, $C = 1{,}130$, $S_{\text{cap}} = 113$, $M_{\text{cap}} = 1{,}017$):**
- `max(|S| + |M|) = 2,118` (**1.87× configured capacity $C$**; final $|S| = 113, |M| = 2{,}005$).

### Scientific Impact on the Paper

- `LRU`, `FIFO`, `ARC`, and `SIEVE` are **100% bit-for-bit validated** against independent reference implementations (`0` miss difference across all 11 test cases).
- `S3-FIFO` in the current dataset (`results/raw/*.csv`) benefited from an unintended **up-to-2× cache size overrun** (`|S| + |M| > C`). On `btree_s101` ($C=1{,}130$), strict-capacity `S3-FIFO` achieves `0.2463` miss ratio (worse than `SIEVE` `0.2348` and slightly better than `ARC` `0.2551`), whereas the buggy `pathA_sim` `S3-FIFO` achieved `0.1698`.
- **Consequence:** Any claim in the current manuscript that `S3-FIFO` is the global best static policy (`0.4890`, winning 176/264 pairs) or that all 17 controllers lose to `S3-FIFO` by `+0.04` is **confounded by this capacity bug** until `S3-FIFO` is fixed and the affected runs are re-evaluated.
- **Policies Not Independently Validated:** The remaining 16 policies (`CAR`, `LIRS`, `W-TinyLFU`, `2Q`, `CLOCK-Pro`, `LeCaR`, `CACHEUS`, `LHD`, `DIP-set-duel`, `LPR-style`, `3L-style`, `MGLRU-style`, `LRB-style`, `CLOCK`, `LFU-A`, `MRU`) have not been cross-checked against `libCacheSim`.
