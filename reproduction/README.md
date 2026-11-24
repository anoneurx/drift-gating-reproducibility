# Reproduction package

## Scope

Everything reported in the revised paper is produced by the artifacts in this
directory. The original simulator, seeds and raw per-trace output of the first
report were not retained, so the paper's main study was **re-run from scratch**
with the released simulator and those reproducible numbers are now the primary
result. The original, non-reproducible report is described only for context and
its numbers are not used in any claim.

## Contents

| File | Purpose |
|---|---|
| `sim_full.cpp` | Authoritative released trace-driven simulator: synthetic generator (5 primitives, 4 scenarios), all baselines, DA controller, ablations, detection tracing, `--da-only`/`--methods` filters, `--np` and `--phase-offset`. |
| `sim_full_diag.cpp` | Additive diagnostic build: logs per-candidate shadow margins, CUSUM statistics, alarms, KS, dwell, purge and activation counts to `--detail-log`. Behaviourally identical to `sim_full.cpp` (0 mismatches on the main study; byte-identical detection CSV). |
| `sim_full_bench.cpp` | Timing-only build that measures shadow-evaluation wall-clock time without diagnostic logging. |
| `sim_full_async.cpp` / `sim_async` | Additive Phase 7 build with a real `--async-shadow` worker thread. Without the flag, deterministic columns 1--6 and detection CSV match the current `sim_full` byte-for-byte; the wall-clock `ns_per_ref` column is excluded by protocol amendment. |
| `phase6_pdl/` | Six 1M-reference CMU PDL prefixes (MSR, Alibaba, Tencent, CloudPhysics, Twitter sample10, MetaKV), manifest with hashes, 18 raw family x capacity runs, summaries and paired statistics. |
| `phase7_async/` | Three real async-shadow prototype repetitions on 80 non-stable seed-5001 traces; raw CSVs, detection CSVs, timing CSV, summary and paired analysis. |
| `phase8_kernel/` | QEMU guest kernel build scripts, workload/controller sources, boot runs and parsers. Guest measurements are reported only when raw CSVs exist. |
| `phase10_capacity_pilot/` | Independent post hoc capacity pilot on the non-evaluation FIU `webusers` trace: 1M-record manifest with SHA256, seven raw capacity CSVs, exact commands and `selection.csv`. Re-selects C=20000; no public performance result changed. |
| `generate_phase_tables.py` | Generates Phase 6--8 LaTeX fragments for both paper trees directly from measured CSVs; no hand-entered numbers. |
| `final_hygiene.py` | Read-only final check of frozen SHA256s, numeric checker, PDF page counts, undefined references, overfull hboxes and placeholder tokens. |
| `sweep_selection.py` | **Released parameter-selection sweep.** Runs all 48 configurations of candidate-set size x cost margin x evaluation delay on training traces with the released simulator and writes `sweep_results.csv` and `sweep_selected.txt`. |
| `run_main_study.sh` | **Primary study driver.** Re-runs the selection sweep, trains on seed 100, freezes parameters, evaluates once on fresh seed 5001; also runs the capacity and sampling-rate sweeps. |
| `analyze_main_study.py` | Builds every primary table from the raw CSVs (no manual transcription). |
| `main_study_*.csv` | Raw, unmodified primary outputs (training, test, capacity, sampling, detection). |
| `generate_offset_table.py` | Generates `latex/offset_table.tex` directly from the five raw boundary-offset detection CSVs (no hand transcription). |
| `detection_offset*.csv` | Raw detection outputs for offsets 0, 250, 500, 1000, 1370. |
| `cost_model.py` | DA-versus-ContShadow break-even model. Recomputes R = 783.28, direct crossover 2196.2 ns (2.20 us), S3-FIFO/DA crossover 2.52 us. |
| `bootstrap_cost_model.py` | 10,000-replicate trace-level bootstrap for R and the DA/ContShadow crossover; writes `cost_model_bootstrap.csv`. |
| `cost_model_bootstrap.csv` | Bootstrap CIs: R [426.3, 1186.7], DA/ContShadow crossover [1.44, 4.06] us. |
| `phase5/total_time_envelope.py` | Re-analysis of frozen seed-5001 results: total-time table, figure and envelope over CLOCK, S3-FIFO, ContShadow and DA. Writes `phase5/total_time_table.{csv,tex}`, `pairwise_crossings.csv`, `envelope_summary.csv`, `phase5/fig_breakeven.pdf`, `fig8_breakeven.png`. |
| `phase5/bootstrap_total_time.py` | Trace-level paired bootstrap (seed 20261124, B=10000) of crossings and the DA minimum excess; writes `phase5/total_time_bootstrap.csv`. |
| `phase5/total_time_bootstrap.csv` | Bootstrap CIs: CLOCK/S3 [0.171,0.274] us, S3/CS [1.660,3.678] us, DA/CS [1.449,4.105] us, DA/S3 [1.086,22.05] us, DA minimum excess [-28.6,40.2] ns. |
| `bench_eval_timing.csv` | Direct shadow-evaluation timing: mean 2.46 ms, median 2.33 ms per evaluation (timing-only build). |
| `check_paper_numbers.py` | Cross-checks every number printed in `latex/main.tex`, both supplement trees and the generated phase fragments against raw outputs. Run `python3 check_paper_numbers.py`: 509/509 checks pass; any mismatch prints FAIL and exits 1. |
| `make_docx_from_pdf.py` | Renders a compiled PDF into a Word copy with one full-page image per page; used for `drift_gating_latex_source/main.docx`. Not suitable for text edits. |
| `Drift_Aware_Page_Replacement_UPDATED_EDITABLE.docx` | Layout-preserving, editable Word conversion of the consolidated 24-page PDF (main + supplement). Created with `pdf2docx`; text is editable rather than page images. Minor PDF-to-Word conversion artifacts are possible. |
| `diag_component_totals.csv` | Raw component activation totals from the diagnostic main-study run (purge/cost/dwell/KS/alarms/evals). |
| `convert_public_traces.py` | Converts public CMU PDL FIU block traces (packed 24-byte records) to page-id traces for `sim_full`. |
| `public_trace_results.csv`, `public_trace_detection.csv` | Raw frozen public-trace run. DA/ContShadow/LRU miss 0.6753, DA zero switches; DA Pareto-dominated by S3-FIFO (0.5772 miss, 31.7 vs 82.5 ns/ref). |
| `public_pilot_C*.csv` | Superseded webresearch-only pilot (C = 1000..50000), retained for provenance; it is no longer the selection source. |
| `phase10_capacity_pilot/C*.csv` | Independent selection pilot on `webusers` (C = 1000..50000, seed 0): LRU/S3-FIFO 0.74182/0.73317 at C=10000 and 0.73590/0.52726 at C=20000; the recorded post hoc rule selected C=20000. |
| `public_diagnostic_summary.csv` | Per-trace public diagnostic summary: initial pick, first-eval candidate miss totals, CUSUM maxima, confirmed alarms. |
| `split_public_traces.py` | Splits the six public traces into 500k training prefixes and held-out suffixes. |
| `sweep_public_selection.py` | 48-config DA re-selection on public training prefixes (capacity--sampling fault makes all configs inert at C=20000). |
| `public_sweep_results.csv`, `public_sweep_selected.txt` | Public re-selection grid and selected config. |
| `run_public_reselect.sh` | Evaluates frozen and re-selected configs on held-out public suffixes. |
| `public_test_frozen.csv`, `public_test_reselected.csv` | Raw held-out suffix results: both 0.66834 miss, 0 switches. |
| `prototype_fault_latency.cpp` | User-space 4 KiB minor-fault microbenchmark used to calibrate the cost break-even. Not a kernel prototype. |
| `fault_latency_results.txt` | Measured fault-latency output. |
| `real_traces.cpp` | Instruments fifteen real programs; logs the 4 KiB page of each data access. |
| `whole_program_holdout.py` | Leave-one-program-out tuning and evaluation driver (fifteen folds), exploratory appendix. |
| `whole_program_holdout_results.csv` | Raw fifteen-program holdout output, exploratory appendix. |
| `appendix_intervals.py` | **Released appendix CI script.** Percentile intervals for the whole-program holdout; writes `appendix_intervals.csv`. |
| `appendix_intervals.csv` | Appendix bootstrap intervals, Holm-adjusted p-values. |
| `scenario_clustered_bootstrap.py` | Scenario-clustered bootstrap and its raw output, exploratory appendix. |
| `make_fig1.py` | Regenerates the controller diagram (Fig. 1). |

## Build and run the primary study

```sh
sh run_main_study.sh
python3 analyze_main_study.py
python3 cost_model.py
```

`run_main_study.sh` compiles the simulator, then runs:

1. **Selection sweep (seed 100)** — 48 configurations over candidate-set size
   {4,5,6} x cost margin K {0,0.05,0.1,0.2} and evaluation delay {2,5,10,20};
   15 stable + 32 non-stable training traces. The rule is the lowest training
   non-stable miss ratio with zero stable-trace false confirmations. Selected:
   5 candidates (add S3-FIFO), K = 0, delay 10 (training miss 0.4400).
2. **Training (seed 100)** — 15 stable + 32 non-stable traces; record only.
3. **Test (seed 5001)** — 30 stable + 80 non-stable traces, never used in the
   sweep. FROZEN configuration, no post-hoc changes, ablations enabled.
4. **Capacity** — C = 500 and C = 2000, frozen controller.
5. **Sampling rate** — p = 0.05 and p = 0.1, frozen controller.

The training command passes `--stable-per-prim 3 --per-scenario 8` explicitly,
because the simulator defaults (30 + 80) are the test-set sizes.

Defaults: C = 1000, epoch W = 2000, p = 0.2, warm-up 20,000, CUSUM h = 5,
KS level 1e-3, z = 1.28, recency purge and cost margin as recorded in the
paper. The KS confirmation is enabled by default; its ablation is reported.

## Cost break-even and total-time envelope

```sh
python3 cost_model.py
python3 bootstrap_cost_model.py
g++ -O2 -std=c++17 -o prototype_fault_latency prototype_fault_latency.cpp
./prototype_fault_latency
cd phase5 && python3 bootstrap_total_time.py && python3 total_time_envelope.py
```

`cost_model.py` reads the primary test CSVs. With the measured means (DA miss
0.4529, ContShadow 0.4228, S3-FIFO 0.4683; 6.47 vs 27.39 shadow evaluations per
trace; 67.4 vs 133.4 vs 28.5 ns/reference) it reports R = 783.28 (95%
bootstrap CI [426.3, 1186.7]) and a direct DA/ContShadow crossover of 2.20 us
(95% bootstrap CI [1.44, 4.06] us). The S3-FIFO/DA total-time crossover is
2.52 us. The microbenchmark measures a user-space first-touch minor fault at
1.98 us and a refault after `MADV_DONTNEED` at 2.06 us (resident access 16 ns).

Direct timing-only shadow-evaluation measurement (`sim_full_bench.cpp`, 570
evals, no diagnostic logging) gives mean 2.46 ms / median 2.33 ms per
evaluation vs. the 1.72 ms implied by the cost-model decomposition. Both are
unoptimized simulator-side numbers and are reported as an order-of-magnitude
check. Because the direct measurement is larger, the DA/ContShadow crossover
would shift to a lower miss cost, weakening the case for gating.

The total-time envelope adds CLOCK and S3-FIFO to the same model. Using the
measured means (CLOCK 8.90 ns/ref at miss 0.559, S3-FIFO 28.54 ns at 0.468,
ContShadow 133.36 ns at 0.423, DA 67.36 ns at 0.453), CLOCK is cheapest below
0.215539 us, S3-FIFO from 0.215539 to 2.304942 us and ContShadow above
2.304942 us. DA is never on the envelope; its minimum excess over the best
policy is 3.268673 ns/ref at 2.304942 us, with bootstrap 95% CI
[-28.597766, 40.231357] ns (CI includes zero, so this is a point-estimate
ranking only). At the measured minor-fault cost (2.2 us) S3-FIFO is cheapest
and DA is 4.887 ns/ref above it. This is a re-analysis of the frozen seed-5001
data: no new experiment was run and no main-study result changed.

## Public FIU block traces

The six traces come from CMU PDL cacheDatasets
(`https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/fiu/`,
project page `https://pdl.cmu.edu/CacheEviction/index.shtml`, cited as [39]).

- **Independent capacity pilot:** `phase10_capacity_pilot/`. The separate
  non-evaluation FIU trace `webusers` was streamed for exactly 1,000,000
  records (WSS 72539, SHA256 recorded in its manifest). The recorded post hoc
  smallest-qualifying-capacity rule selected C=20000: LRU/S3-FIFO were
  0.74182/0.73317 at C=10000 (gap 0.00865) and 0.73590/0.52726 at C=20000
  (gap 0.20864). The older `public_pilot_C*.csv` webresearch-only pilot is
  retained for provenance but is not the selection source.
- **Frozen run:** `public_trace_results.csv` / `public_trace_detection.csv`.
  DA/ContShadow/LRU miss 0.6753, DA zero switches, 11–15 confirmed alarms per
  trace, no true boundaries. DA Pareto-dominated by S3-FIFO (0.5772 miss,
  31.7 ns/ref).
- **Diagnostics:** `sim_full_diag` with `--detail-log` produced
  `public_diagnostic_summary.csv`. CUSUM max Sp 7.95–20.30 and Sn 6.08–33.30
  crossed h=5 on every trace. Every shadow evaluation returned identical miss
  counts for all five candidates (LRU, LFU-A, 2Q, MRU, S3-FIFO), giving zero
  margins and tie-break to LRU. Cause: `Cs = p*C = 4000` exceeds the sampled
  working set (≈1100–1800 distinct pages) at C=20000. At C=1000 (Cs=200) the
  same trace differentiates candidates and DA switches to S3-FIFO. This is a
  capacity–sampling fault, not evidence of policy equivalence.
- **Re-selection on training prefixes:** `split_public_traces.py`,
  `sweep_public_selection.py`, `run_public_reselect.sh`. All 48 configs gave
  identical train miss 0.68027 and zero switches; tie-break selected ncand=4,
  K=0, edelay=2. Held-out suffixes: frozen and re-selected both 0.66834 miss,
  0 switches. Reported as a failed external validation.

## Phase 6: six further CMU PDL families

Post hoc, recorded in `PROTOCOL.md`; see its version history for timestamp status. `phase6_pdl/convert_pdl_prefix.py`
streams exactly 1,000,000 packed 24-byte records from each of six URLs and writes
`phase6_pdl/manifest.csv` (HTTP status, bytes consumed, WSS, max id, SHA256).
`phase6_pdl/run_pdl.py` runs nine methods at three capacities per family
(`1/5/10%` of WSS, `W=2C`, warm-up 100,000, `np=max_id+1`, fixed controller
`--ncand 5 --kfrac 0 --z 1.28 --edelay 10`); `phase6_pdl/analyze_pdl.py`
writes `summary.csv`, `per_family.csv` and `paired_da_minus_baseline.csv`
(trace-level and family-cluster bootstrap, B=10000, seed 20261125; Wilcoxon
with Holm correction).

```sh
python3 phase6_pdl/convert_pdl_prefix.py
python3 phase6_pdl/run_pdl.py 3
python3 phase6_pdl/analyze_pdl.py
```

Over the 18 family x capacity points the measured mean miss ratios are S3-FIFO
0.4683, ContShadow 0.4739, DA 0.4742, CLOCK 0.4973 and LRU 0.4987. The paired
DA--S3-FIFO difference is +0.0059 (Holm p = 0.0192): DA is **worse** than the
strongest fixed policy on these prefixes. This is reported as a negative result;
no trace-specific tuning was performed.

PDL use is non-commercial scholarly research with citation of the repository
README; no explicit dataset licence file was found. Only a bounded prefix of
each file was downloaded.

## Phase 7: real asynchronous-shadow prototype

Post hoc, recorded in `PROTOCOL.md`; see its version history for timestamp status. Build and run:

```sh
g++ -O2 -std=c++17 -pthread -o sim_async sim_full_async.cpp
./sim_async --seed 5001 --ncand 5 --kfrac 0 --z 1.28 --edelay 10 --da-only \
  --async-shadow --async-timing phase7_async/timing.csv \
  --out phase7_async/async_results1.csv --det phase7_async/async_det1.csv
python3 phase7_async/analyze_async.py
```

The worker thread evaluates a copied shadow/candidate state with queue depth 1;
submission never waits for the worker. With `--async-shadow` absent, the three
deterministic columns `miss_ratio,switches,shadow_evals` and the detection CSV
are byte-identical to the current `sim_full` on the frozen seed-5001 command
(protocol amendment: the wall-clock `ns_per_ref` column is excluded from byte
identity).

Three real repetitions on the 80 non-stable traces gave mean miss ratios
0.5611, 0.5676 and 0.5599; paired async-minus-synchronous differences are
+0.1082, +0.1147 and +0.1070 with bootstrap CIs excluding zero. The timing CSV
has 240 rows, 15,066 stale decisions, 1,192 applied results and zero dropped
requests. Its timings also give a direct cost for the implemented shadow
evaluator: 1,232 completed evaluations took 711.8 ms wall and 709.0 ms CPU
(577.8 and 575.5 us each). With R=783 from `cost_model.csv`, 577.8 us
per evaluation implies a 0.74 us miss-cost break-even, below the
1.44--4.06 us bootstrap interval and the 1.98--2.06 us minor-fault
calibration. This is an unoptimised userspace prototype measurement, not a
kernel or optimised latency. The prototype is therefore **worse** than
synchronous DA; this is reported as measured, with no tuning.
`phase5/async_model.csv` remains an analytical model and is not compared as if
it were a prototype measurement.

## Phase 8: QEMU guest kernel (build/run recipe)

`phase8_kernel/` is additive. The host has no sudo, no kernel headers, no
`perf`/`bpftrace`, so the measurements are made inside a user-built QEMU guest
with `/dev/kvm`. All protocol choices, discarded attempts and amendments are
in `PROTOCOL.md`. The completed run produced nine real guest boots and the
CSVs listed below; the result is a null observation (no reclaim event and no
controller toggle), reported as such in the paper.

```sh
sh phase8_kernel/build_guest.sh > phase8_kernel/build.log 2>&1
sh phase8_kernel/run_guest.sh
python3 generate_phase_tables.py
```

The build downloads Linux 6.6.1 into `/home/kashie/opencode_kernel_build`,
records the tarball SHA256 in `phase8_kernel/kernel_tarball.sha256`, applies the
recorded config options, and writes `bzImage`, `kernel.config`,
`manifest.csv`, compiler/bison versions and the full `build.log`. Because the
host lacks system `bison` and libelf headers, local bison 3.8.2 and elfutils
0.191 libelf are built under the same scratch path; neither changes the kernel
config. The host compiler is GCC 16, whose C23 default breaks Linux 6.6.1
real-mode code, so the recorded clean build passes
`CC="gcc-15 -std=gnu11" HOSTCC="gcc-15 -std=gnu11"` as make command-line
variables (environment variables are overridden by the kernel Makefiles).

`run_guest.sh` performs one discovery boot to select only recorded ftrace
functions present in the guest, then three fresh boots for each of
`fixed_lru`, `fixed_mglru` and `coupled`. Console output, guest `uname`, vmstat
before/after, controller samples/toggles and raw function-graph traces are kept
under `phase8_kernel/results/`. `make_ftrace_filter.py`, `parse_ftrace.py` and
`summarize_kernel.py` derive `ftrace_durations.csv`, `kernel_summary.csv` and
`ftrace_summary.csv` from those raw files. `generate_phase_tables.py` writes
`phase8_kernel_main_table.tex` and `phase8_kernel_ftrace_table.tex` into both
paper trees only after the measured CSVs exist.

The final nine runs parsed 191,370 function-graph duration samples. Every run
has 131,138 minor faults, zero major faults, zero `workingset_refault_anon`,
zero `pgscan_anon`/`pgsteal_anon` deltas and zero controller toggles. Only
`handle_mm_fault` and `do_wp_page` were sampled; the cgroup
`memory.max`/`memory.peak` capture files were empty, so memory pressure was not
demonstrated and no reclaim-latency claim is made. Earlier build/boot attempts
and one complete but defective boot sequence were discarded before reporting
and are documented in `PROTOCOL.md` and `NOT_DONE.md`.

## Detection boundary-offset check

Change points in the generator fall on epoch boundaries, which favours
detection. `--phase-offset N` prepends N references from the first phase and
shifts all recorded boundaries by N; offset 0 reproduces the released detection
output exactly. Offsets 250, 500, 1000, 1370 were run and
`generate_offset_table.py` produces the manuscript table from the five raw CSVs.

| Offset | Detected | Spurious |
|---:|---:|---:|
| 0 | 278/380 | 169 |
| 250 | 274/380 | 171 |
| 500 | 274/380 | 171 |
| 1000 | 279/380 | 173 |
| 1370 | 281/380 | 173 |

Stable traces: 23 spurious confirmations at every offset (1 after ref 100,000).
All shifts stay inside a phase-generator epoch, so the alignment artefact is
not removed.

## Seeds

| Purpose | Seeds |
|---|---|---|
| Primary main study | 100 (training + selection sweep), 5001 (fresh test, evaluated once) |
| Exploratory real programs | 12345 (default), 101, 202, 303 (whole-program folds use all four) |
| Public FIU traces / boundary offsets | 5001 (default / as shown in the commands above) |

One earlier report used unretained artifacts; its numbers are not used in any
claim and it is described in a single paragraph in the paper.

## Exploratory appendix: real programs

```sh
g++ -O2 -std=c++17 -o real_traces real_traces.cpp
./real_traces && ./real_traces 101 && ./real_traces 202 && ./real_traces 303
python3 whole_program_holdout.py
python3 appendix_intervals.py
```

Each trace has 300,000 references; C = 1000, warm-up 100,000. Fifteen programs
x four seeds = 60 traces. Six of the fifteen kernels have miss ratios below
0.02 at this capacity (hash join, breadth-first search, sort, stencil, radix
scatter, string search); the mean is dominated by five high-miss kernels
(sparse gathers, random walk, hash table, linked list, union-find). The
whole-program holdout tunes on fourteen programs and evaluates once on the
omitted one. Reported result: DA 0.3304, S3-FIFO 0.3291, LRU 0.3540;
DA--S3-FIFO +0.0013 [-0.0019, +0.0044] (a tie). No comparison survives Holm
correction (smallest adjusted p = 0.096 for 2Q).

## Notes on interpretation

- The primary study is a trace-driven simulation, not a kernel implementation.
  The only latency measurement is the user-space minor-fault calibration above;
  no in-kernel page-fault or reclaim latency is measured.
- ContShadow (continuous shadow evaluation) has a **lower miss ratio than DA**
  in the primary study, at higher cost. Gating saves shadow evaluations but
  does not preserve miss ratio there; the paper states this explicitly.
- A multi-generation LRU baseline is deliberately **not** claimed as kernel
  MGLRU: page-level trace replay has no kernel aging/reclaim-pressure signal,
  so the `MGLRU-style` policy is a generation-indexed LRU abstraction.
- The trace-level interval over the 80 non-stable traces is the primary
  uncertainty statement; the four-cluster bootstrap has only 35 distinct
  cluster resamples and is reported as a coarse sensitivity check only.
- On the 30 stable traces DA's advantage over LRU is a start-up policy-selection
  effect, not drift handling (DA 0.3071 with 0.80 switches / 1.73 evaluations;
  LRU 0.5186, S3-FIFO 0.3301, ContShadow 0.3065). It is not added to the
  drift-handling claim.
- On the six public FIU traces DA never switches and is Pareto-dominated by
  S3-FIFO; these are storage block/cache traces, not virtual-memory paging
  traces, and are an external check only.

## NOT DONE with real data in this session

1. Kernel-faithful MGLRU or other in-kernel replacement prototype: the
   MGLRU-style policy in the released simulator remains a page-level abstraction,
   and the guest-kernel phase observes Linux MGLRU rather than implementing a
   kernel DA policy.
2. Production virtual-memory paging traces as primary evidence (public data are
   storage block/cache traces; real-program traces are instrumented kernels).
3. Full-shadow ranking-agreement validation of the sampled selector (not
   measured; H4 remains not evaluated).

Phases 6--8 are no longer open: six further 1M-reference PDL prefixes and a
real asynchronous shadow worker were run (both negative for DA), and the nine
guest-kernel boots produced real fault-path timings but a null reclaim result.
`reproduction/final_hygiene.py` verifies the frozen seed-5001 SHA256s, the
numeric checker, PDF page counts, undefined references, overfull hboxes and
placeholder tokens.

These items are stated in the paper's Limitations and are not claimed as
results.

## Reference verification

Two citations that reviewers could not locate are real and verifiable:

- [17] EACLOCK — Crossref `10.1109/TKDE.2026.3724159`: *IEEE Trans. Knowl.
  Data Eng.*, vol. 38, no. 11, pp. 7387-7401, Nov. 2026.
- [29] Patel and Maniar — Zenodo record 20576370, DOI
  `10.5281/zenodo.20576370`: *Int. J. Sci. Res. Technol.*, vol. 3, no. 6,
  pp. 556-564, 2026.

Both entries in the paper now carry the DOI and a resolvable URL.
