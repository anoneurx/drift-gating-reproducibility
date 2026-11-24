# PROTOCOL

## Version history and evidentiary status

- `8d69a4667ca71a05b79034180b7e42766cfaa66a` — `2026-11-24T17:27:05+01:00` — `Snapshot research artifacts before post hoc relabeling` (pre-relabel snapshot; this file was present in it as then written).
- `e238f52af4e5fce9dedc3ad06190f043ced8841b` — `2026-11-24T17:34:24+01:00` — `Relabel all follow-ups as post hoc and document git provenance` (this relabeling commit).
- No independently timestamped version of this file predating the runs it describes was found. The internal dates below are author-recorded labels, not audited prospective registration timestamps.
- Therefore Phases 1--10 are **post hoc** records. They are reported as post hoc follow-ups in the manuscript and audit files, not as protocol-guided or prospectively registered results.
- Frozen main-study results (seed 5001, C=1000, default config) are not changed.

## Phase 1 - Rankability rule (post hoc record)

**Recorded date:** 2026-11-23 (post hoc; see version history)

### Hypothesis
The FIU/public-trace no-switch failure is caused by unrankable shadow evaluations: shadow capacity `Cs` exceeds the number of distinct sampled pages `Dw` in the evaluation window, making all candidate miss counts equal. A rankability-aware configuration will increase the fraction of rankable evaluations and may allow DA to switch on traces where `Cs/Dw >= 1` caused ties, but it may not improve miss ratio.

### Fixes under test
1. **f-cap sweep (post hoc record):** `f in {0.25, 0.5, 0.75}` with `Cs = min(round(p*C), round(f*Dw))` (`--cs-cap-f f`). This is a real cap when `f*Dw < p*C`.
2. **W/C scaling (post hoc record):** set `W = 2*C` to preserve the default W/C=2 ratio as C changes (`--W <2*C>`). This scales epoch length in references with cache size; evaluation windows are measured in epochs and therefore scale proportionally. Distinct sampled pages `Dw` are observed diagnostically; no post hoc W tuning.

### Diagnostic (required for every Phase 1 shadow evaluation)
Per evaluation log: `ep,startEp,C,W,p,csCapF,Cs,Dw,rankable,miss_c0..miss_c{k-1}` where `rankable=1` if candidate miss counts are not all equal, else 0. Implemented as `--eval-diag <path>`.

### Configurations
- **Synthetic:** C in {500,1000,2000,4000}; p in {0.05,0.1,0.2,0.4}; f in {0,0.25,0.5,0.75} (f=0 means disabled/original cap behavior); W=2*C. Fixed: seed 5001 for test, seed 100 for train; ncand 5, kfrac 0, z 1.28, edelay 10, da-only; default trigger cusum.
- **FIU:** C in {1000,2000,5000,10000,20000}; p in {0.05,0.1,0.2,0.4}; f in {0,0.25,0.5,0.75}; W=2*C. Fixed: default seed 5001, np 1048576, warm 50000, kfrac 0, z 1.28, edelay 10, da-only, s3frac 0.05, twoqkin 125, lprthr 0.1, lecarlr 0.6, lirsfrac 0.05, ncand 5. Traces: 6 FIU public train prefixes for selection, 6 test suffixes for held-out evaluation.

### Selection rule
- Train-only selection: for each (C, trace-set) choose (f,p) minimizing mean DA miss ratio on training traces/prefixes; ties broken by higher rankable fraction, then lower f, then lower p. Evaluate selected config once on held-out test traces/suffixes.
- Report all grid cells, not just selected.

### Metrics
- Primary: mean miss ratio, switches, shadow evals, rankable-eval fraction.
- Diagnostic: Cs, Dw, Cs/Dw, rankable flag per evaluation.

### Outcomes
- **Positive:** rankable fraction increases materially where Cs/Dw>=1 and selected config improves held-out miss ratio or enables meaningful switching without worsening miss.
- **Null:** rankable fraction increases but held-out miss/switching does not improve.
- **Negative:** rankable-aware cap worsens held-out miss ratio or causes harmful switching.

### Baselines/comparators
- f=0 (original) at same C/W/p grid cells.
- Frozen main-study result remains unchanged reference (C=1000, W=2000, p=0.2, f=0).

### Implementation notes
- Default behavior unchanged when `--cs-cap-f 0` and no `--eval-diag`.
- All entries in this file are post hoc records; no prospective protocol claim is made.

## Phase 2 - Budget-matched trigger curve (post hoc record)

**Recorded date:** 2026-11-23 (post hoc; see version history)

### Hypothesis
CUSUM-triggered shadow evaluation achieves a better miss-ratio vs shadow-eval budget frontier than periodic or random triggers at matched budgets; oracle provides the accuracy ceiling. This may be null or negative.

### Configurations (all on frozen synthetic main-study traces, seed 5001, C=1000, default params unless noted; da-only where applicable)
- **ContShadow:** existing continuous evaluation (main_study_results.csv, ContShadow) - fixed point.
- **DA CUSUM:** sweep h in {2,3,5,7,10} and delta in {0.1,0.3,0.5,0.7,1.0} (one-at-a-time and/or small grid) to move along budget. Default h=5, delta=0.5.
- **Periodic:** sweep trigger period in {5,10,14,16,20,30,40,60,80} epochs to cover ~2-30 shadow evals/trace.
- **Random:** sweep trigger probability in {0.01,0.02,0.04,0.05,0.07,0.10,0.15,0.20} with trigger-seed 99.
- **Oracle:** existing oracle trigger (trigger_real/oracle.csv) - fixed point.

### Selection / pairing rule
- No train/test selection for this frontier plot: all points evaluated on same frozen 80 non-stable seed-5001 traces for budget-matched comparison. This is a measurement, not a tuned claim.
- Paired tests (Wilcoxon + Holm) at matched budgets: for each CUSUM point, pair with nearest-budget periodic and random point by absolute difference in mean shadow evals/trace; if tie, prefer lower miss. Pairing rule recorded here post hoc. Also report nearest-budget within 10% when available.

### Metrics
- Mean miss ratio (non-stable 80), mean shadow evals/trace, mean switches/trace.
- 95% bootstrap CI for mean miss (10k, seed 0).
- Paired DA-minus-other diffs, W/L/T, Wilcoxon p, Holm-adjusted p at matched budgets.

### Outcomes
- **Positive:** CUSUM frontier dominates or is significantly better than periodic/random at matched budgets.
- **Null:** no significant difference at matched budgets.
- **Negative:** periodic/random equal or better at matched budgets.

## Phase 3 - Other detectors (post hoc record)

**Recorded date:** 2026-11-23 (post hoc; see version history)

### Hypothesis
Page-Hinkley and ADWIN detectors on the epoch miss-ratio signal may close part of the oracle gap relative to CUSUM, at comparable or different shadow-eval budgets. This may be null or negative.

### Implementations
- **Page-Hinkley (PH):** Standard Page-Hinkley on epoch miss ratio m_t. Mean estimate x̄_t updated incrementally; cumulative sum S_t = Σ (m_i - x̄_i - delta_ph); M_t = min(S_t); alarm when S_t - M_t > lambda. After alarm, reset S/M/mean (or reset statistics) and enter same WAIT->eval->COOL flow as CUSUM. Source: Mouss et al./standard PH test; Page, 1954; Gama et al. survey usage.
- **ADWIN:** Adaptive windowing on epoch miss-ratio stream. Maintain window Wsplit into W0,W1; alarm when |mean(W0)-mean(W1)| > eps_cut with Hoeffding bound. Use standard ADWIN (Bifet & Gavalda, 2007) simplified for scalar mean. After alarm, shrink window to newer part and enter WAIT->eval->COOL.

### Tuning (train only)
- Tune on synthetic training traces (seed 100, 80 non-stable, C=1000 default) with fixed grid. PH: delta_ph in {0.001,0.005,0.01,0.02}, lambda in {1,2,5,10,20}. ADWIN: delta_conf in {0.002,0.01,0.05,0.1}. Select by min mean miss; tie-break lower shadow evals. Evaluate selected once on seed 5001 test.

### Metrics
- Mean miss, shadow evals, switches on 80 non-stable test; fraction of oracle gap closed: (CUSUM_miss - det_miss)/(CUSUM_miss - oracle_miss) where CUSUM default 0.4529, oracle 0.4335.
- Detection recall, delay, spurious counts using existing offset/detection protocol (30k absolute window, same as CUSUM).

### Outcomes
- Positive: detector closes meaningful oracle gap with comparable/better budget.
- Null/negative: no improvement or worse budget/accuracy.

## Phase 4 - Stronger baselines and large real traces (post hoc record)

**Recorded date:** 2026-11-23 (post hoc; see version history)

### Baseline implementations
- **SIEVE:** Zhang et al., NSDI 2024. FIFO queue with visited bit; hand pointer sweeps for eviction, clearing visited bits. Source: https://cachemon.github.io/SIEVE-website/ algorithm description / paper. Sanity check: small reference string behavior against published description.
- **W-TinyLFU:** Einziger et al., FAST 2017 / "TinyLFU: A Highly Efficient Cache Admission Policy". Window LRU + main SLRU (probation/protected) + Count-Min Sketch admission. Simplified implementation if needed; document deviations. Source: paper algorithm.
- **LHD:** only if time allows; otherwise NOT_DONE.

### Trace availability/licensing (to be checked before use)
- MSR Cambridge, Alibaba block, Tencent block, CloudPhysics, Twitter/Meta KV: check license/availability; use only legally downloadable/available. Report what cannot be obtained.

### Evaluation
- If traces obtained: full-length where possible, capacities at 1%,5%,10% of working-set size defined from trace content (post hoc record). Compare DA, ContShadow, periodic, CUSUM, PH, ADWIN, S3-FIFO, W-TinyLFU, SIEVE, ARC, LRU, OPT with paired stats across traces.
- If not obtained: report plainly in NOT_DONE/Limitations; no weaker silent substitution.

### Outcomes
- Positive/null/negative reported as-is.

## Phase 4 - Stronger baselines and large real traces (execution addendum, post hoc record)

**Recorded date:** 2026-11-23 (post hoc; see version history)

### Trace availability (checked)
- **Available in workspace:** synthetic generator (seed 5001 main-study), 6 FIU public split traces in `reproduction/public_split/*.bin` (12 files, 418k-500k refs each, 500k-request prepared splits; original .zst not in workspace, so full-length original unavailable here - stated), 15-program real-program traces in `traces_real/*.bin` (60 files, 300k refs each).
- **Not available/licensed in workspace:** MSR Cambridge (SNIA IOTTA license terms must be checked; not downloaded), Alibaba block, Tencent block, CloudPhysics, Twitter/Meta KV. Not obtained/used; no substitution.

### Capacity rule (post hoc record, deterministic)
For each real trace file, `WSS = number of distinct uint32 IDs in trace`. Capacities `C in {max(1,round(0.01*WSS)), max(1,round(0.05*WSS)), max(1,round(0.10*WSS))}`. This is computed from trace content only (post hoc record).

### Methods/baselines
Run available methods: LRU, ARC, S3-FIFO, SIEVE, W-TinyLFU, DA (CUSUM default), ContShadow, and DA-ph/DA-adwin selected configs where feasible. OPT omitted on large/real trace runs unless small enough (stated). LHD/TinyLFU full Caffeine implementation: NOT_DONE (no implementation in sim_full; W-TinyLFU is simplified independent re-implementation with documented assumptions).

### Metrics
Miss ratio per trace/capacity; paired comparisons across traces/capacities where applicable; report raw tables. No tuning on test results.

## Phase 5 - Cost model and uncertainty (post hoc record)

**Date:** 2026-11-23

### 5a. Break-even model
- Replace single 2.2us point with break-even function/table parameterized by miss penalty (DRAM, NVMe, remote/RDMA, swap/SSD illustrative ranges) and shadow-eval cost. Use measured means from `main_study_results.csv` and `bench_eval_timing.csv`; report formulas and assumptions. Keep user-space minor-fault (2.2us) as calibration only, not as a claim about kernel page-fault cost.

### 5b. Async shadow-eval variant
- Analytical variant: shadow evaluation runs off critical path; critical-path eval cost = 0, background CPU cost reported separately. Assumptions stated explicitly. No kernel/async prototype fabricated.

### 5c. LCB uncertainty
- Replace normal z=1.28 4-block LCB with t-quantile df=3 (t_{0.90,3}=1.637744) as a post hoc robustness variant; default remains normal for frozen reproducibility. Rerun DA on 80 non-stable seed 5001 traces with `--lcb-dist t3` and report delta vs default. This is a robustness check, not a replacement of frozen main result unless clearly better and reported.

### 5d. Block bootstrap CIs
- Where 4-block normal CIs were used in analysis, add block/trace bootstrap (10k, seed fixed) as robustness; report both.

## Phase 4b - LHD baseline and CMU PDL external traces (post hoc record)

**Recorded date:** 2026-11-23 (post hoc; see version history)

### [39] verification (done by webfetch, reported)
- Both [39] URLs are live. The FTP index lists `fiu`, `msr`, `alibabaBlock`, `tencentBlock`, `cloudphysics`, `twitter`, `metaKV`, etc.; the `fiu/` listing contains `fiu_madmax-110108-112108.oracleGeneral.zst` (HTTP 200, Content-Length 3,189,409). README states zstd 24-byte record format and citation requirements. PDL copyright notice (https://pdl.cmu.edu/Publications/copyright.shtml) says documents/software are provided for timely dissemination of scholarly work on a **non-commercial basis**, copyright remains with authors, and copying for commercial redistribution/republication/dissemination/reposting requires explicit permission. No dataset-specific licence file was found; we use only publicly downloadable traces for non-commercial research with citation and do not claim a dataset licence.

### LHD (Least Hit Density, Beckmann et al., NSDI 2018)
- Implement a **simplified independent** LHD-style hit-density heuristic in `sim_full.cpp` (uniform object size; score = (hits+prior)/(age+1); min-heap with lazy invalidation). It is NOT the paper's exact conditional-probability estimator; report as a heuristic with this limitation.
- Register as method `LHD`, compile, smoke-check, then include in synthetic and real-trace runs. No tuning on test results.

### External traces
- Download a small, publicly served subset from [39] (CMU PDL cacheDatasets `fiu/` directory; e.g. `fiu_madmax-110108-112108.oracleGeneral.zst`; non-commercial research use with citation, no dataset-specific licence asserted). Convert with `convert_public_traces.py` (24-byte records, zstd). If a trace is too large for full replay, convert an explicit request prefix and state the exact limit; no silent truncation. Capacities 1/5/10% WSS as in Phase 4a.
- Compare DA, ContShadow, SIEVE, W-TinyLFU, LHD, S3-FIFO, ARC, LRU with paired per-trace results; report raw CSVs and means.

## Phase 5e - Total-time envelope re-analysis (2026-11-24)

This is a **re-analysis of already frozen seed-5001 results**, not a new experiment; no simulator run, seed, trace, or main-study metric is changed, so no new prospective registration claim is made.

- Read the 80 non-stable test rows of `reproduction/main_study_results.csv` and compute, for CLOCK, S3-FIFO, ContShadow and DA, the mean per-reference time `t` and mean miss ratio `m` from the released frozen outputs.
- Define total time `T_policy(c_m) = t_policy + m_policy * c_m` for miss cost `c_m` in ns. Report the lower envelope of CLOCK, S3-FIFO and ContShadow, the crossing points, and the minimum excess of DA over that envelope.
- Bootstrap: resample the 80 non-stable traces pairwise with replacement, B=10000, seed 20261124; report percentile 95% CIs for all crossings and the minimum DA excess, and the positive-replicate count for the DA/S3-FIFO crossing. Because the minimum-gap CI includes zero, state the ranking as point estimates only.
- Replace the DA-versus-ContShadow-only break-even table with a generated total-time table over all four policies (`\input{total_time_table.tex}`) and a four-policy figure. Do not claim that gating pays off in total time; withdraw that earlier claim.

## Phase 6 - Remaining CMU PDL families (post hoc record)

**Recorded date:** 2026-11-24 (post hoc; see version history)

This is a new external-validity experiment. It does not change the frozen seed-5001 main study.

### Sources (exact URLs, one trace per remaining family)

1. MSR: `https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/msr/msr_hm_0.oracleGeneral.zst`
2. Alibaba block (old): `https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/alibabaBlock/old/io_traces.ns42.oracleGeneral.zst`
3. Tencent block (old): `https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/tencentBlock/old/tencentBlock.ns1089.oracleGeneral.zst`
4. CloudPhysics: `https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/cloudphysics/w64.oracleGeneral.bin.zst`
5. Twitter sample10: `https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/sample10/cluster10.oracleGeneral.sample10.zst`
6. MetaKV: `https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/metaKV/202206_kv_traces_all.csv.oracleGeneral.zst`

Use is non-commercial scholarly research with citation of the PDL/README citations. No dataset-specific licence file was found; PDL's site-wide notice states only that server materials are provided on a non-commercial basis. This limitation is reported.

### Conversion and prefix rule

- Decode a **bounded prefix of exactly 1,000,000 packed 24-byte records** from each URL by streaming zstd (`zstandard.ZstdDecompressor().stream_reader`) and stopping after 1,000,000 records; do not download the full MetaKV/Twitter files.
- Structure is `struct <IQIq>` (`uint32 timestamp; uint64 obj_id; uint32 obj_size; int64 next_access_vtime`).
- Map first-touch `obj_id` to a dense `uint32` id; ignore timestamp, size and next-access fields because the simulator is capacity-only. This is the existing `convert_public_traces.py` rule; reuse it with a URL-reading wrapper `phase6_pdl/convert_pdl_prefix.py`.
- Write `phase6_pdl/<family>.bin`; record URL, HTTP status, compressed bytes consumed, record count, dense-object count, SHA256 of the `.bin`, and UTC download timestamp in `phase6_pdl/manifest.csv`. A short or malformed read is a failed run, not a substituted trace.

### Capacity and command rule

- For each converted prefix, compute `WSS = len(unique(uint32 ids))` from trace content only (post hoc record). Capacities are `C in {max(1,round(0.01*WSS)), max(1,round(0.05*WSS)), max(1,round(0.10*WSS))}`; `W = 2*C`; `--warm 100000`; `--np max_id+1`.
- Fixed controller parameters: `--ncand 5 --kfrac 0 --z 1.28 --edelay 10`. No train/test tuning on these traces.
- Method set: `LRU,CLOCK,S3-FIFO,ARC,SIEVE,W-TinyLFU,LHD,ContShadow,DA` (the simulator adds DA; `ContShadow` is requested explicitly). Run one command per family/capacity with raw outputs `phase6_pdl/raw/<family>_C<C>.csv` and `_det.csv`. Example command shape: `./sim_full --trace <bin> --C <C> --W <2C> --warm 100000 --np <max_id+1> --ncand 5 --kfrac 0 --z 1.28 --edelay 10 --methods LRU,CLOCK,S3-FIFO,ARC,SIEVE,W-TinyLFU,LHD,ContShadow --out <out> --det <det>`.
- Analysis script `phase6_pdl/analyze_pdl.py` writes `phase6_pdl/summary.csv` (mean miss, evals, switches, ns/ref by method), `phase6_pdl/per_family.csv`, and `phase6_pdl/paired_da_minus_baseline.csv`.

### Statistics and outcomes

- Primary: paired DA-minus-baseline miss-ratio difference over the 18 family×capacity points; report each point and the mean.
- Uncertainty: trace-level paired bootstrap, B=10000, seed 20261125; additionally cluster bootstrap over the six families, B=10000, same seed. Wilcoxon signed-rank with Holm adjustment across the nine DA-vs-baseline comparisons.
- Positive/null/negative are reported as measured. If DA is worse or tied, that is the result; no tuning until a preferred method wins.

## Phase 7 - Real userspace asynchronous-shadow prototype (post hoc record)

**Recorded date:** 2026-11-24 (post hoc; see version history)

### Implementation contract

- Add an additive build `reproduction/sim_full_async.cpp`, compiled as `sim_async` with `g++ -O2 -std=c++17 -pthread`. A flag `--async-shadow` enables a real worker thread. Without the flag, the binary must reproduce the current `sim_full.cpp` output on the frozen seed-5001 command: columns 1–6 (`scenario,seed,method,miss_ratio,switches,shadow_evals`) byte-for-byte and `det.csv` byte-for-byte. The `ns_per_ref` timing column is measured wall clock and is excluded from byte identity. This clarification is recorded post hoc (see version history).
- The worker performs the **same shadow-evaluation routine** used by synchronous DA on a copied shadow/candidate state. The main thread only enqueues a request and checks for a completed result at the existing decision point; it never blocks for the worker.
- Bounded queue depth is 1. If a trigger arrives while the worker is busy, count a dropped request; do not queue more. If a result is ready, the controller uses the most recent completed result and counts superseded results; if none is ready, it keeps the current policy and counts a stale decision.
- Instrument `steady_clock` durations for enqueue/check on the critical path (ns/ref) and worker wall/CPU time; write them to `phase7_async/timing.csv`. These are measured prototype timings, not an analytical assumption.

### Run and comparison

- Command: `./sim_async --seed 5001 --ncand 5 --kfrac 0 --z 1.28 --edelay 10 --da-only --async-shadow --out phase7_async/async_results.csv --det phase7_async/async_det.csv`; analyse only the 80 non-stable seed-5001 traces, as in the frozen study.
- Comparator: frozen synchronous DA from `main_study_results.csv`, unchanged. Repeat the async run three times; report all three raw CSVs because thread scheduling is real and not seeded.
- No parameter tuning. The analytical `phase5/async_model.csv` remains labeled analytical and is not compared as if it were a prototype.

### Metrics and statistics

- Metrics: miss ratio, switches, enqueued/dropped/superseded/stale-eval counts, critical-path ns/ref, worker wall/CPU ms, queue wait.
- Paired bootstrap over 80 non-stable traces, B=10000, seed 20261126, plus Wilcoxon+Holm for miss ratio. Report null or negative outcomes directly.

### Execution record: direct shadow-evaluation cost (post hoc)

- The three real `--async-shadow` repetitions produced 240 non-stable timing rows in `reproduction/phase7_async/timing.csv`. `analyze_async.py` records 1,232 enqueued and completed evaluations, zero dropped requests, 1,192 applied results and 15,066 stale decisions.
- Measured worker time was 711,793,385 ns wall and 709,039,242 ns CPU, giving 577.8 us wall and 575.5 us CPU per completed evaluation; enqueueing cost 9.85 us per submitted request and the main thread spent 0.115 ms per trace checking worker status.
- At the frozen cost-model ratio R=783.28 (`reproduction/cost_model.csv`), 577.8 us per evaluation implies a miss-cost break-even of 0.74 us. This lies below the 1.44--4.06 us bootstrap interval and the 1.98--2.06 us user-space minor-fault calibration. The separate timing-only build in Phase 5 measured 2.46 ms per evaluation, so the two unoptimised userspace measurements bracket the 1.72 ms implied by the frozen time decomposition.
- These are real timings of the implemented userspace shadow-evaluation routine in an unoptimised prototype. No kernel shadow evaluator was built or measured, and no frozen main-study result is replaced by these numbers.

## Phase 8 - QEMU guest kernel: real MGLRU and in-kernel latency (post hoc record)

**Recorded date:** 2026-11-24 (post hoc; see version history)

Host constraints: no passwordless sudo, no host headers, no host `perf`/`bpftrace`; `/dev/kvm`, QEMU, `gcc`, `clang`, `make`, BusyBox, zstd and network are available. All kernel work therefore runs in an unprivileged user-built guest.

### Guest build

- Kernel source: `https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.6.1.tar.xz`, SHA256 recorded in `phase8_kernel/manifest.csv` (post hoc record).
- Build as user from the space-free scratch path `/home/kashie/opencode_kernel_build/linux-6.6.1` (the Linux Makefile rejects source directories containing spaces, and `/tmp` has insufficient free space); copy `bzImage` and `.config` back into `phase8_kernel/`. The host has no `bison` and no sudo, so first build GNU bison 3.8.2 from `https://ftp.gnu.org/gnu/bison/bison-3.8.2.tar.xz` into `/home/kashie/opencode_kernel_build/bison-install` and prepend its `bin` to `PATH` for all kernel `make` invocations; record bison version. Run `make defconfig`; then `scripts/config --enable LRU_GEN --enable LRU_GEN_ENABLED --enable MEMCG --enable CGROUP_MEMORY --enable FTRACE --enable FUNCTION_TRACER --enable FUNCTION_GRAPH_TRACER --enable KPROBES --enable KPROBE_EVENTS --enable TRACING --enable DEBUG_FS --enable PROC_FS --enable SYSFS --enable TMPFS --enable BLK_DEV_INITRD --enable RD_GZIP --enable DEVTMPFS --enable DEVTMPFS_MOUNT --enable NET_9P --enable NET_9P_VIRTIO --enable 9P_FS --enable VIRTIO_PCI`; `make olddefconfig`; `make -j$(nproc) bzImage`. Record `.config`, compiler version, kernel version, tarball SHA256 and build log. If build fails, report the failure; do not infer kernel results.
- **Amendment recorded 2026-11-24 (post hoc; see version history).** The first build attempt failed while compiling objtool: `tools/objtool/include/objtool/elf.h:10:10: fatal error: gelf.h: No such file or directory`. Inspection of Linux 6.6.1 Kconfig shows x86_64 selects `HAVE_OBJTOOL` unconditionally and `HAVE_UACCESS_VALIDATION` selects `OBJTOOL`, so disabling `UNWINDER_ORC`/`STACK_VALIDATION` cannot remove the objtool dependency. Recorded fix: build elfutils 0.191 (`https://sourceware.org/elfutils/ftp/0.191/elfutils-0.191.tar.bz2`) from source with `--disable-debuginfod --disable-libdebuginfod` into `/home/kashie/opencode_kernel_build/elfutils-install`, and export `CPATH`/`LIBRARY_PATH` so the unmodified kernel build finds `gelf.h` and links `-lelf`. The kernel configuration (including ORC unwinder and the tracing options above) is **not** changed by this build-dependency fix; the resulting `.config` is still copied to `phase8_kernel/kernel.config` and checked. A subsequent elfutils compile failed only because GCC treats a `const`-qualifier warning in `libcpu/riscv_disasm.c` as an error (`-Werror`), so the same local build is retried with `CFLAGS="-g -O2 -Wno-error"`; this affects no kernel source or measured value. A later kernel compile failed in `arch/x86/realmode/rm/wakemain.c` because host GCC 16 defaults to C23, where `false`/`bool` are keywords; the real-mode Makefile uses its own CFLAGS that do not carry the kernel's `-std=gnu11`. Recorded fix: a **clean** rebuild with `CC=gcc-15 HOSTCC=gcc-15`, retaining the same `.config` options, local bison and local libelf. A first attempt exported these variables in the environment, but kernel Makefiles override environment `CC`/`HOSTCC`, so GCC 16 was still used; additionally, the installed GCC 15 also defaults to C23. Final recorded invocation: pass `CC="gcc-15 -std=gnu11" HOSTCC="gcc-15 -std=gnu11"` as **make command-line variables** to every `make` call. This only selects the compiler and language standard for an older kernel; it changes no workload, config option or measured value. A subsequent pass built `arch/x86/boot/bzImage` successfully but failed to link the static guest controller because `-lm` was placed before the source file, leaving `fmax`/`sqrt` unresolved; the recorded fix is `gcc -O2 -static -o guest_da_ctl guest_da_ctl.c -lm`. This is a guest-tool link-order fix only, with no kernel-config or measurement change. The first boot then failed with `Failed to execute /init (error -2)`: the host BusyBox copied into the initramfs is dynamically linked, but the initramfs lacked `/lib64/ld-linux-x86-64.so.2`, `libc.so.6` and `libresolv.so.2`. Recorded fix: copy those loader/runtime files into the same paths in the initramfs. This is a root-filesystem build fix only; no guest workload or measurement was run, and no measured value is inferred. The first completed boot sequence is likewise discarded: (i) `make_ftrace_filter.py` wrote `ftrace_functions.txt` outside the 9p-mounted results directory, so `init` did not find it and the trace was unfiltered (0 matching samples despite a 3 MB trace); (ii) `/dev/null` was absent, so the background controller never started; (iii) the `uname` applet was not linked, so `guest_uname.txt` was empty; and (iv) the cgroup cap actually seen by the guest was not recorded alongside the zero refault counts. Recorded fixes: write/read the filter file inside `results/`, create `/dev/null` in guest `init`, link the `uname` applet, and write `memory.max`, `memory.swap.max` and `memory.peak` into each run directory. These are instrumentation/root-filesystem corrections, not workload or tuning changes; no value from the discarded boots is used in the paper. This is a host build-tool dependency only; no measured number is inferred from it.
- Root filesystem: BusyBox initramfs containing `guest_workload`, `guest_da_ctl`, startup script, and required `/dev`, `/proc`, `/sys`, `/sys/fs/cgroup` mounts. Boot with `qemu-system-x86_64 -enable-kvm -m 2048 -smp 2 -no-reboot -display none -serial file:<per-run-console.log> -kernel bzImage -initrd initramfs.cpio.gz -append "console=ttyS0 panic=-1"` plus a virtio-9p results mount; `-display none -serial file:` replaces `-nographic` so each repetition's console is retained, and all other boot parameters are unchanged. Record `qemu-system-x86_64 --version` and guest `uname -a` per run.

### Workload and conditions

- `guest_workload.c`: `mmap` 512 MiB anonymous, join cgroup with `memory.max=268435456` (256 MiB) and swap disabled, touch 1,000,000 references in four 250,000-reference phases. Each phase uses a 128 MiB page set and a fixed permutation seeded 101,202,303,404; first 100,000 references are warm-up. Record guest `CLOCK_MONOTONIC` userspace times and page-fault counts from `getrusage`.
- Conditions, each repeated three times with the guest rebooted: (a) `enabled=0` fixed LRU-style kernel behavior; (b) `enabled=7` fixed MGLRU; (c) `guest_da_ctl` coupled controller. Leave `min_ttl_ms` at the guest boot default and record it. Record exact `lru_gen/enabled` and `min_ttl_ms` values for each run.
- `guest_da_ctl` reads `/proc/vmstat` and `/proc/meminfo` every fixed 10 ms wall interval (recorded in `phase8_kernel/manifest.csv`), computes CUSUM on normalized `workingset_refault_anon` deltas with `h=5`, `delta=0.5` (same constants as the frozen simulator), and toggles `enabled` between 0 and 7 only after a confirmed alarm. Uses `edelay=10` sample intervals before the next allowed decision. No tuning. Results are mounted from the host through QEMU 9p; enabling 9p in the guest kernel is part of the recorded build config.

### In-kernel latency measurement

- Record the exact list of available ftrace functions from guest `/sys/kernel/debug/tracing/available_filter_functions` that match `handle_mm_fault`, `do_anonymous_page`, `do_wp_page`, `shrink_folio_list`, `shrink_page_list`, `reclaim_pages`, and `do_swap_page`. Only functions present in that recorded list are traced.
- Use `function_graph` tracer with `set_ftrace_filter` restricted to that list; parse duration fields from `/sys/kernel/debug/tracing/trace` into `phase8_kernel/ftrace_durations.csv` (function, duration_ns, condition, repetition). Also collect `/proc/vmstat` counters: `pgscan_anon`, `pgsteal_anon`, `workingset_refault_anon`, `workingset_activate_anon`, `majflt/minflt` from `getrusage`.
- Statistics: per-function/median/p95/max duration, refaults per million refs, scans/steals, total runtime. Bootstrap across the three repetitions plus within-run function samples is not claimed as independent; report the three raw repetitions and medians only. Wilcoxon is not applied to n=3.
- Outcomes: report as-is. A controller that does not improve refaults or latency is a null/negative result. This phase measures a **kernel-coupled userspace controller**, not an in-kernel DA replacement policy.

## Phase 9 - Manuscript compression and full verification

**Recorded date:** 2026-11-24 (post hoc; see version history)

- After Phases 6–8 produce real CSVs, generate new LaTeX fragments directly from those CSVs; no hand-entered numbers.
- Move exact commands, schemas, long literature tables, offset diagnostics, per-family raw tables and detailed follow-up tables to `latex/supplement.tex`. Keep only the result tables/figures needed for the main argument in `main_template.tex`/`latex/main.tex`.
- Compile iteratively until the main PDF is within 10–12 total pages at readable 10pt IEEEtran layout; supplement may grow. If this cannot be achieved without illegible type or deleting result content, keep the smallest readable result and report the actual page count in the audit, not in the paper as a fabricated target.
- Update `claims_to_sources.csv` and `reproduction/check_paper_numbers.py` for every new printed number; require all checks PASS.
- Verify frozen seed-5001 artifacts by SHA256 before/after all additive code changes; verify default `sim_full` and `sim_async` (without `--async-shadow`) produce byte-identical deterministic columns 1–6 and byte-identical detection CSVs (the wall-clock `ns_per_ref` column is excluded); rebuild drift/root PDFs/DOCX; check 0 undefined references and 0 overfull hboxes.

## Phase 10 - Independent capacity pilot (post hoc record)

**Recorded date:** 2026-11-24 (post hoc; see version history)

A reviewer noted that the FIU public-trace capacity $C=20{,}000$ had been
selected from a pilot on `webresearch`, which is itself one of the six
evaluated test traces. This phase replaces that provenance with a pilot on a
**separate** trace. No new controller parameter is tuned; only the external
trace replay capacity is selected. The frozen seed-5001 main study and its two
SHA256-pinned CSVs are untouched.

### Pilot trace (post hoc record)

- Trace: `fiu_webusers-030409-033109.oracleGeneral.zst`.
- Exact URL: `https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/fiu/fiu_webusers-030409-033109.oracleGeneral.zst`.
- This trace is **not** among the six evaluated FIU traces (`homes`, `ikki`,
  `madmax`, `online.cs.fiu.edu`, `webmail.cs.fiu.edu`, `webresearch`) and is not
  used in any reported performance comparison. It was chosen from the PDL `fiu/`
  index by name and collection date (post hoc record); no miss result or
  working-set value from it was used in the choice, and no alternative trace was
  substituted after seeing results.
- Use is non-commercial scholarly research with PDL citation, as recorded in
  Phase 4b/6.

### Conversion and manifest (post hoc record)

- Reuse the Phase 6 streaming rule in a new wrapper
  `phase10_capacity_pilot/convert_pilot_prefix.py`: decode **exactly
  1,000,000** packed 24-byte `<IQIq` records (timestamp, obj_id, obj_size,
  next_access_vtime), map first-touch `obj_id` to dense `uint32`, ignore the
  other fields, and write `phase10_capacity_pilot/webusers.bin`.
- Record URL, HTTP status, UTC start, compressed bytes consumed, record count,
  WSS (`len(unique ids)`), max id, and SHA256 of the output in
  `phase10_capacity_pilot/manifest.csv`. A short or malformed stream is a
  failed run; it is reported, never replaced by another trace or a fabricated
  prefix.

### Simulator grid (post hoc record)

- Capacities, ascending: $C \in \{1000, 5000, 10000, 15000, 20000, 25000,
  50000\}$.
- Methods: `LRU,S3-FIFO,DA`; seed `0`; `--np 1048576`; explicit frozen
  controller constants `--ncand 5 --kfrac 0 --z 1.28 --edelay 10 --p 0.2`;
  epoch `--W 2000` and `--warm 100000`. No ablations, no detector change, no
  re-selection.
- One command per capacity, raw outputs `phase10_capacity_pilot/C<C>.csv` and
  `C<C>_det.csv`, stderr in `C<C>.stderr`, exact command lines in
  `phase10_capacity_pilot/commands.csv`.

### Deterministic selection rule (post hoc record)

Let $m_L(C)$ and $m_S(C)$ be the pilot miss ratios of LRU and S3-FIFO at
capacity $C$, read from the raw CSVs.

1. **Primary rule.** Select the **smallest** $C$ in the ascending grid for
   which both policies are non-saturated ($m_L(C) \ge 0.01$ and
   $m_S(C) \ge 0.01$) and the policies are distinguishable by at least ten
   percentage points ($m_L(C) - m_S(C) \ge 0.10$). This makes the external
   replay informative for a controller whose candidates must be ranked, and
   does not use DA's miss ratio or any drift-detection outcome.
2. **Fallback.** If no capacity meets the primary rule, select the **largest**
   $C$ with $m_L(C) \ge 0.01$ and $m_S(C) \ge 0.01$. If no capacity is
   non-saturated, report the pilot as unusable; do not silently substitute a
   capacity or trace.

The rule is applied once by `phase10_capacity_pilot/select_capacity.py`, which
writes `selection.csv` with every capacity's two miss ratios, the separation,
the saturation flags, and the selected capacity. No manual override is
permitted after the run.

### Consequence rule (post hoc record)

- If the selected capacity is 20,000, retain the already frozen public-trace
  results and change **only their provenance text** to cite this independent
  pilot; report the pilot's own raw numbers and the selection rule in the
  supplement and in the reproduction ledger.
- If the selected capacity is any other grid value, re-run every public-trace
  experiment that used $C=20{,}000$ at the selected capacity, regenerate all
  affected manuscript numbers from the new raw CSVs, and update the checker
  and claim ledger. The frozen synthetic main study is never re-run.
- Outcome sections report the pilot outcome as measured, including a null or
  negative result. No tuning is performed to make DA win.

### Execution record (factual, not a protocol amendment)

- The recorded URL returned HTTP 200; 1,000,000 records were decoded,
  WSS = 72,539, and the output SHA256 is
  `f09a2450a1b9dc7eb521191dfbeea1213d1a7fd63cbec5cb601dffec46c85403`
  (`phase10_capacity_pilot/manifest.csv`).
- All seven recorded simulator commands ran; exact lines are in
  `phase10_capacity_pilot/commands.csv`.
- The rule selected `C=20000` by the **primary** rule (`selection.csv`):
  at `C=10000` the LRU--S3-FIFO gap was 0.00865 (not qualifying), and at
  `C=20000` it was 0.20864 (qualifying). Because this equals the already frozen
  replay capacity, no public-trace performance run was repeated and no
  main-study artifact was touched.

