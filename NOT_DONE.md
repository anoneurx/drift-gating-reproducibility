# NOT_DONE

Items not achievable with real data in this workspace run are listed here and are not claimed as results in the manuscript body. This is a chronological ledger: later sections explicitly supersede earlier "still not done" entries where a run was subsequently completed (notably the six remaining PDL families, the async prototype and the QEMU guest phase).

## External-validity gaps
- **Kernel-faithful MGLRU baseline / in-kernel replacement prototype.** Not built. The MGLRU-style baseline is a page-level abstraction without kernel aging/reclaim-pressure signals.
- **Production virtual-memory paging traces.** Not collected. Public traces are FIU storage block/cache prefixes; synthetic traces have generated phase boundaries.
- **In-kernel page-fault or reclaim latency.** Not measured. Cost calibration uses a user-space minor-fault microbenchmark (`prototype_fault_latency.cpp`).

## Repaired capacity-sampling correction (Task B)
- **Public traces:** Re-selection on 500,000-reference training prefixes with the pre-specified repair (`Cs=min(round(p*C), round(f*D_w)), f=1.0`, `--cs-cap-f 1.0`) produced the same selected configuration and identical held-out miss ratio/switches as the original controller. Command/seed/output recorded below; no improvement observed.
- **80 fresh synthetic traces / 30 stable traces:** Repaired re-selection on training traces (seed 100) selected the same configuration; evaluation once on held-out seed 5001 traces produced identical miss ratios, switches, and shadow evaluations to the original controller.
- **15-program whole-program holdout:** Repaired evaluation with the same holdout protocol produced identical mean miss ratios to the original controller.

## Commands / seeds / outputs for real runs
- Repaired public re-selection: `python3 sweep_public_selection_repaired.py` (cwd `reproduction/`, default seed in script, `C=20000`, `cs-cap-f=1.0`) -> `reproduction/public_sweep_repaired_results.csv`, `reproduction/public_sweep_repaired_selected.txt`, raw `reproduction/public_sweep_repaired_raw/`.
- Repaired public held-out eval: `./sim_full --np 1048576 --C 20000 --warm 50000 --kfrac 0 --z 1.28 --s3frac 0.05 --twoqkin 125 --lprthr 0.1 --lecarlr 0.6 --lirsfrac 0.05 --methods LRU,S3-FIFO,DA --ncand 4 --edelay 2 --cs-cap-f 1.0 --trace public_split/fiu_homes-110108-112108.oracleGeneral.test.bin --trace public_split/fiu_ikki-110108-112108.oracleGeneral.test.bin --trace public_split/fiu_madmax-110108-112108.oracleGeneral.test.bin --trace public_split/fiu_online.cs.fiu.edu-110108-113008.oracleGeneral.test.bin --trace public_split/fiu_webmail.cs.fiu.edu-110108-113008.oracleGeneral.test.bin --trace public_split/fiu_webresearch-030409-033109.oracleGeneral.test.bin --out public_test_reselected_repaired.csv --det public_test_reselected_repaired_det.csv` (cwd `reproduction/`, default seed) -> `reproduction/public_test_reselected_repaired.csv`, `reproduction/public_test_reselected_repaired_det.csv`.
- Repaired synthetic re-selection: `python3 sweep_selection_repaired.py --jobs 4` (cwd `reproduction/`, seed 100, `cs-cap-f=1.0`) -> `reproduction/sweep_repaired_results.csv`, `reproduction/sweep_repaired_selected.txt`, raw `reproduction/sweep_repaired_raw/`.
- Repaired synthetic held-out test: `./sim_full --seed 5001 --ncand 5 --kfrac 0 --z 1.28 --edelay 10 --cs-cap-f 1.0 --ablations --out main_study_repaired_results.csv --det main_study_repaired_detection.csv` (cwd `reproduction/`) -> `reproduction/main_study_repaired_results.csv`, `reproduction/main_study_repaired_detection.csv`.
- Repaired 15-program holdout: `python3 whole_program_holdout.py --cs-cap-f 1.0 --out whole_program_holdout_repaired_results.csv` (cwd `reproduction/`, default seed/trace protocol in script) -> `reproduction/whole_program_holdout_repaired_results.csv`.
- Detection offsets (Task C): `./sim_full --seed 5001 --per-scenario 20 --stable-per-prim 6 --ncand 5 --kfrac 0 --z 1.28 --edelay 10 --da-only --phase-offset 333 --out /tmp/opencode/off333.csv --det detection_offset333.csv` and same with `--phase-offset 1501` -> `reproduction/detection_offset333.csv`, `reproduction/detection_offset1501.csv`. Table regenerated via `python3 generate_offset_table.py` -> `latex/offset_table.tex`.
- Post hoc trigger-variant code change (labeled post hoc): added `--trigger cusum|periodic|random|oracle`, `--trigger-period`, `--trigger-rand`, `--trigger-seed`, `--delta` to `reproduction/sim_full.cpp`; default CUSUM DA output verified byte-identical (110 rows, 0 mismatches, detection identical). Build: `g++ -O2 -std=c++17 -o sim_full sim_full.cpp` (cwd `reproduction/`).
- Synthetic trigger comparison (real, post hoc, seed 5001, ncand 5, kfrac 0, z 1.28, edelay 10, da-only, 80 non-stable + 30 stable traces): `./sim_full --seed 5001 --ncand 5 --kfrac 0 --z 1.28 --edelay 10 --da-only --trigger oracle --out trigger_real/oracle.csv --det trigger_real/oracle_det.csv`; periodic `--trigger periodic --trigger-period {10,14,16,30,40}` -> `trigger_real/periodic_p*.csv`; random `--trigger random --trigger-rand {0.04,0.05,0.07,0.10} --trigger-seed 99` -> `trigger_real/random_r*.csv`. Outputs under `reproduction/trigger_real/`.
- FIU trigger comparison (real, post hoc, default seed 5001, np 1048576, warm 50000, kfrac 0, z 1.28, edelay 10, da-only, s3frac 0.05, twoqkin 125, lprthr 0.1, lecarlr 0.6, lirsfrac 0.05, ncand 5, default C=1000, default p=0.2): oracle/periodic-p40/random-r04 with same 6 FIU public test traces -> `reproduction/trigger_real/fiu_oracle.csv`, `fiu_periodic_p40.csv`, `fiu_random_r04.csv` and corresponding `_det.csv`. Oracle produced 0 confirms because FIU traces have no ground-truth bounds in the trace format.
- CUSUM parameter sensitivity sweep (real, post hoc, one-at-a-time from default config, seed 5001, ncand 5, kfrac 0, z 1.28, edelay 10, da-only, 80 non-stable + 30 stable synthetic traces): `python3 run_param_sweep.py` (cwd `reproduction/`) -> `reproduction/param_sweep/*.csv`, `reproduction/param_sweep/summary.csv`.
- FIU rankability/capacity-p sweep (real, post hoc, default seed 5001, same FIU base args as above, da-only): `python3 run_rankability_fiu.py` (cwd `reproduction/`) -> `reproduction/rankability_real/fiu_C*_p*.csv`, `reproduction/rankability_real/fiu_sweep.csv`.
- Synthetic rankability/capacity-p sweep (real, post hoc, seed 5001, ncand 5, kfrac 0, z 1.28, edelay 10, da-only): `python3 run_rankability_synth.py` (cwd `reproduction/`) -> `reproduction/rankability_real/synth_C*_p*.csv`, `reproduction/rankability_real/synth_sweep.csv`.
- Independent capacity pilot (registered in `PROTOCOL.md` Phase 10 before download/conversion): `python3 phase10_capacity_pilot/convert_pilot_prefix.py` then `python3 phase10_capacity_pilot/run_pilot.py` then `python3 phase10_capacity_pilot/select_capacity.py` (cwd `reproduction/`). Exact seven simulator commands in `reproduction/phase10_capacity_pilot/commands.csv`; raw `C*.csv`/`C*_det.csv`, manifest with WSS 72539 and SHA256, and `selection.csv` in the same directory. Selected C=20000; no existing result changed.

## Capacity provenance repair (Phase 10)

- The earlier C=20000 choice was based on a pilot over `webresearch`, one of the six evaluated traces. The independent `webusers` pilot now re-selects C=20000 with a pre-registered rule (smallest C with both miss ratios at least 0.01 and LRU--S3-FIFO gap at least 0.10). The superseded `public_pilot_C*.csv` files are retained but are no longer used as the selection source; only provenance paragraphs in the two supplement trees and the reproduction ledger changed.

## Not attempted / not claimable (no mock/assumed data)
- ~~MSR / Alibaba / Tencent / CloudPhysics traces: not present/licensed/verified.~~ **Superseded on 2026-11-24:** all six remaining PDL families were streamed as bounded 1M-reference prefixes and run (Phase 6, see below).
- ~~W-TinyLFU / SIEVE baselines: not implemented.~~ **Superseded:** both are implemented as simplified independent re-implementations and were run.
- ~~ADWIN / Page-Hinkley detectors: not implemented.~~ **Superseded:** both are implemented as simplified independent detectors and were run.
- ~~Real asynchronous shadow-evaluation prototype: not implemented.~~ **Superseded on 2026-11-24:** `sim_full_async.cpp` with a real worker thread was built and run three times (Phase 7, below).
- **Kernel-faithful MGLRU / in-kernel replacement policy:** still not built and outside the approved kernel scope; the approved scope is a guest-kernel MGLRU observation, real in-kernel fault/reclaim latency, and a userspace coupled controller.
- **Reference [39] URL/licence:** URLs and non-commercial scholarly-use terms were verified; no explicit dataset licence file was found and no new dataset licence claim is made.

## Phase 1-5 pre-specified follow-ups (2026-11-23)

### Completed (real, from released code/CSVs)
- Phase 1: `--eval-diag` and rankability grid run (`reproduction/run_phase1_rankability.py`, `phase1_rankability/all_summary.csv`, 64,280 eval diags). Sharp boundary: Cs/Dw>=1 -> 0/1514 rankable. Train-only f/W selection gave no meaningful FIU repair gain (null/negative).
- Phase 2: Budget-matched frontier (`phase2_budget/frontier_points.csv`, `matched_pairs.csv`, `frontier.png`). CUSUM better than periodic/random at matched budgets in most pairs; Oracle/ContShadow show accuracy ceiling.
- Phase 3: PH/ADWIN implemented in `sim_full.cpp` (simplified ADWIN, Hoeffding window; documented). Train seed 100 grid, selected PH (d=0.001,l=2) and ADWIN (d=0.05), evaluated once on seed 5001. Neither closed oracle gap; PH miss 0.4552, ADWIN 0.4991 vs CUSUM 0.4529.
- Phase 4: SIEVE/W-TinyLFU added (independent re-implementations; documented assumptions). Smoke tests passed. Synthetic 80 non-stable: SIEVE 0.5557, W-TinyLFU 0.4913. Real-trace run on available FIU (500k prepared splits) + 15-program traces at 1/5/10% WSS: overall DA 0.5477, S3-FIFO 0.5162 best; FIU DA 0.7087 worse than LRU 0.7011. Results in `phase4_baselines/`.
- Phase 5: Break-even table extended (`phase5/breakeven_table.csv`), async analytical model (`phase5/async_model.csv`), t3 LCB robustness (`phase5/t3_seed5001.csv`) gave DA 0.4586 delta +0.0057 (negative robustness).
- Cost-claim correction (re-analysis of the same frozen seed-5001 data, not a new experiment): `phase5/total_time_envelope.py` and `phase5/bootstrap_total_time.py` regenerate total-time Table XIII and Fig. 6 over CLOCK, S3-FIFO, ContShadow and DA. The lower envelope is CLOCK below 0.215539 us, S3-FIFO 0.215539-2.304942 us and ContShadow above 2.304942 us; DA is never on it (minimum excess 3.268673 ns/ref at 2.304942 us, bootstrap 95% CI [-28.597766, 40.231357] ns includes zero). The earlier claim that gating pays off only when misses are cheap is withdrawn; point estimates show DA is never best in these measurements.

### Still NOT DONE / blocked
- External traces not in workspace/licensed: MSR Cambridge (SNIA IOTTA terms), Alibaba, Tencent, CloudPhysics, Twitter/Meta. No substitution made.
- LHD not implemented.
- W-TinyLFU/SIEVE/ADWIN/PH are simplified independent implementations, not authors' reference code.
- FIU files are 500k-request prepared splits; original .zst not in workspace.
- Kernel-faithful MGLRU, in-kernel replacement prototype, real async shadow-evaluation prototype, in-kernel page-fault/reclaim latency - not built/measured.
- [39] URL/licence still unverified; do not assert.
- Full statistical rerun with block-bootstrap CIs across all affected analyses not completed for every legacy script; main new results use 10k bootstrap seed 0 where stated.
- Manuscript is 17 pages (over 10-12 target); compression pass still needed.

## Remaining-part pass (same day, after Phase 1-5 report)

### Newly completed
- **[39] verified by webfetch:** both URLs live; FTP index lists fiu/msr/alibabaBlock/tencentBlock/cloudphysics/twitter/metaKV. README states zstd format + citation; PDL copyright notice (pdl.cmu.edu/Publications/copyright.shtml) covers non-commercial scholarly use with citation; no explicit dataset licence file found.
- **LHD implemented:** simplified independent hit-density heuristic (Beckmann NSDI 2018 inspired; score=(hits+1)/(age+1), unit-size objects, exact min-score set). Registered as `--methods LHD`; synth miss 0.6736, real 0.6979, FIU 0.9577, 15-prog 0.6462. Far worse than LRU/S3-FIFO - negative result for this simplification.
- **External traces obtained:** 3 original FIU traces from [39] (madmax 918,010 refs full; webresearch 3,274,061 refs full; homes 5,000,000-request prefix - explicitly stated). Converted with `convert_public_traces.py`; replayed at 1/5/10% WSS in `reproduction/phase4_external/` (9 points). Means: S3-FIFO 0.6188, ARC 0.6208, DA 0.6280, W-TinyLFU 0.6306, ContShadow 0.6335, LRU 0.6412, SIEVE 0.6538, LHD 0.9358.
- **claims_to_sources.csv** extended to 87 rows; **check_paper_numbers.py** extended to 285/285 PASS.
- **Compression:** main 17 -> 15 pages (arraystretch, figure widths, literature/appendix/detail tables moved to 5-page supplement); supplement.pdf rebuilt.

### Still NOT DONE / blocked
- Remaining PDL traces (MSR, Alibaba, Tencent, CloudPhysics, Twitter, Meta) not downloaded or run.
- Kernel-faithful MGLRU, in-kernel replacement prototype, real async shadow-eval prototype, in-kernel page-fault/reclaim latency - not built/measured.
- SIEVE/W-TinyLFU/ADWIN/PH/LHD remain simplified independent implementations.
- Main paper 15 pages + 5-page supplement at that point: above the original 10-12 page target. Phase 9 compression by moving detail to the supplement is in progress; no result content is deleted.

## Phases 6-9 (pre-registered 2026-11-24 in `PROTOCOL.md`)

### Completed (real runs, recorded before execution in `PROTOCOL.md`)
- **Phase 6 PDL external traces:** exact 1,000,000-record prefixes from MSR `msr_hm_0`, Alibaba `io_traces.ns42`, Tencent `tencentBlock.ns1089`, CloudPhysics `w64`, Twitter `sample10/cluster10` and MetaKV `202206_kv_traces_all`; URLs, HTTP status, bytes consumed, WSS, max ids and SHA256 in `reproduction/phase6_pdl/manifest.csv`. 18 family x capacity simulator runs (`summary.csv`, `per_family.csv`, `paired_da_minus_baseline.csv`, `commands.csv`, raw CSVs). Means: S3-FIFO 0.4683, ContShadow 0.4739, DA 0.4742, CLOCK 0.4973, LRU 0.4987; DA--S3-FIFO +0.0059 (Holm p=0.0192), i.e. DA worse on these prefixes.
- **Phase 7 async prototype:** `reproduction/sim_full_async.cpp` compiled as `sim_async` with `-pthread`; default deterministic columns 1--6 and detection CSV byte-identical to current `sim_full` (protocol amendment excludes wall-clock `ns_per_ref`). Three real `--async-shadow` repetitions with fixed parameters: `reproduction/phase7_async/async_results*.csv`, `timing.csv`, `summary.csv`, `paired.csv`, `timing_summary.csv`. Means 0.5611/0.5676/0.5599; paired async-minus-sync +0.1082/+0.1147/+0.1070. Negative result; no tuning.
- **Numeric checker:** `reproduction/check_paper_numbers.py` 342/342 PASS after adding Phase 6/7 checks.

### Phase 8 QEMU guest kernel (completed after recorded build/boot fixes)
- Built Linux 6.6.1 from the space-free path `/home/kashie/opencode_kernel_build`. Build-tool fixes were recorded in `PROTOCOL.md` before affected runs: moved out of a path with spaces; built GNU bison 3.8.2 locally (no sudo); built elfutils 0.191 libelf locally because objtool needs `gelf.h`; passed `CC="gcc-15 -std=gnu11"` and `HOSTCC="gcc-15 -std=gnu11"` as make command-line variables because kernel Makefiles ignore environment `CC` and GCC 15 defaults to C23; fixed `-lm` link order in the guest controller.
- The first boot sequence failed before `/init` (`/dev/null` and the dynamic loader/libc were absent). A second complete boot sequence was discarded before reporting: the ftrace filter file was outside the 9p-mounted results directory, `/dev/null` was missing so the controller never started, `uname` was not linked, and cgroup metadata was not captured. All fixes were recorded in `PROTOCOL.md` before the final rerun. No number from a discarded boot is used.
- Final artifacts: `reproduction/phase8_kernel/kernel_summary.csv` (nine real boots), `ftrace_summary.csv` (18 function groups), `ftrace_durations.csv` (191,370 raw samples), raw traces/console/vmstat/controller logs under `results/`, and `manifest.csv` with kernel SHA256, compiler versions and controller constants.
- **Result is null:** all nine runs have 131,138 minor faults, zero major faults, zero `workingset_refault_anon`, zero `pgscan_anon`/`pgsteal_anon` deltas and zero controller toggles. Only `handle_mm_fault` and `do_wp_page` produced samples; no reclaim function was reached. `memory.max`/`memory.peak` capture files were empty, so memory pressure was not demonstrated. `handle_mm_fault` median/p95 ranged 641/1532 ns to 761/1593 ns. These are real in-kernel fault-path timings, not a reclaim-latency or kernel-DA result.

### Phase 9 paper compression/new-result insertion (completed)
- Both main PDFs were compressed to 10 pages by relocating detail to standalone supplements (root 15 pages, drift 12 pages); no result content was deleted.
- Phase 6/7/8 main paragraphs and CSV-generated table fragments were inserted into both trees; numeric checker extended to 425/425 PASS.

### Still not claimed
- No in-kernel DA replacement policy, no kernel-faithful MGLRU baseline, no production VM paging traces, no `perf`/`bpftrace` host measurements, no fabricated or inferred kernel latency, no reclaim-latency result from the guest (no reclaim function was reached), and no demonstrated cgroup memory pressure.
