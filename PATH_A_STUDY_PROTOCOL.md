# Path A Study Pre-Specified Protocol

**Status:** Pre-specified BEFORE compiling and running `reproduction/pathA_study/`.  
**Local registration commit:** recorded in git history immediately prior to running `reproduction/pathA_study/run_study.py` (local git record, not an external third-party registry).

## 1. Research Question

> When, if ever, does dynamic policy switching beat strong static replacement policies such as S3-FIFO on real-application and public traces once switching costs, evaluation budgets, and runtime overheads are accounted for?

## 2. Pre-Specified Hypotheses

- **H1 (Switching headroom ceiling):** Across real-application page-level traces and public block/object traces at working-set-relative capacities ($1\%, 5\%, 10\%\ \mathrm{WSS}$), an exact dynamic-programming (DP) per-window hindsight oracle paying an explicit full-cache-refill switch penalty ($c_{\mathrm{switch}} = C$ misses) achieves less than the smallest worthwhile gain ($\ge 0.02$ net miss-ratio reduction on at least $2/3$ of traces in a family-capacity group) across most trace families.
- **H2 (Controller and budget comparison):** Practical switching controllers (CUSUM, Page--Hinkley, ADWIN, periodic, random, and oracle-window triggers across low/medium/high evaluation budgets, plus continuous shadow evaluation) do not consistently outperform static S3-FIFO on net objective or total-time cost across families.
- **H3 (Unseen-family predictive rule):** Observable trace features (working-set density, reuse-distance dispersion, and temporal working-set turnover across windows) predict on **unseen trace families** (evaluated via Leave-One-Family-Out and cross-source holdout) whether switching yields positive net headroom over the best static policy and over S3-FIFO.

## 3. Endpoints and Smallest Worthwhile Gain

For each `(trace, C, window)` after warm-up:

- **Primary endpoint (net oracle gain):**
  $$\mathrm{net\_gain} = \mathrm{best\_static\_miss\_ratio} - \mathrm{oracle\_objective\_ratio}$$
  where $\mathrm{oracle\_objective\_ratio} = (\mathrm{oracle\_misses} + c_{\mathrm{switch}} \cdot \mathrm{switches}) / N_{\mathrm{eval}}$ is solved via **exact Dynamic Programming** (`dp[w][p]`). Because staying on `best_static` with zero switches is always feasible, $\mathrm{net\_gain} \ge 0$ identically.
- **Secondary endpoints:**
  - `net_gain_vs_s3fifo = s3fifo_miss_ratio - oracle_objective_ratio`
  - `gross_gain_vs_best = best_static_miss_ratio - oracle_miss_ratio`
  - `zero_cost_gain`: DP oracle with $c_{\mathrm{switch}} = 0$ as an absolute upper bound
  - `oracle_switches`
  - Live controller `miss_ratio`, `objective_ratio = (misses + switches * C) / N_eval`, `shadow_evals`, and consistently measured `ns_per_ref` / `us_per_eval` (`CLOCK_PROCESS_CPUTIME_ID`).
- **Smallest worthwhile gain:** A family-capacity group `(family, source, cap_frac)` achieves a worthwhile switching gain iff:
  1. family mean $\mathrm{net\_gain} \ge 0.02$ (2.0 percentage points), and
  2. at least $2/3$ of traces in that group have $\mathrm{net\_gain} \ge 0.02$.
  All families and capacities are retained; failures are reported without exclusion.

## 4. Trace Corpus (Local Real Applications + Public Traces)

1. **Real-application OS page-cache traces (`LD_PRELOAD` on unmodified Linux binaries):**
   - `sqlite_oltp_scan` (2 seeds), `sqlite_join_agg` (2 seeds), `sqlite_mixed_rw` (2 seeds) via `/usr/bin/sqlite3` (`PRAGMA cache_size=2`)
   - `git_repo` (2 seeds) via `/usr/bin/git`
   - `python_etl` (2 seeds) via `/usr/bin/python3`
2. **Real-application virtual-memory data-page traces (`clang++ -O2 -fsanitize=thread` load/store instrumentation):**
   - `vm_bwt` (3 seeds), `vm_kv` (3 seeds), `vm_graph` (3 seeds), `vm_cache` (3 seeds)
3. **Instrumented-program page-level traces (`traces_real/`):** 15 families $\times$ 4 seeds = 60 traces.
4. **Public block/object traces (`reproduction/public_split/` and `reproduction/phase6_pdl/`):**
   - 12 FIU held-out prefixes (6 families $\times$ train/test; `webusers.bin` excluded as the earlier capacity-pilot trace)
   - 6 CMU PDL 1M-record prefixes (`msr`, `alibaba`, `tencent`, `cloudphysics`, `twitter`, `metakv`)

## 5. Baselines, Triggers, Budgets, and Simulation Settings

- **21 Candidate Policies:** `LRU, FIFO, CLOCK, LFU-A, MRU, 2Q, ARC, S3-FIFO, LeCaR, LPR-style, SIEVE, W-TinyLFU, LHD, CAR, LIRS, CLOCK-Pro, CACHEUS, 3L-style, MGLRU-style, DIP-set-duel, LRB-style` (online SGD reuse-distance predictor).
- **Capacities:** $C \in \{\max(1, \mathrm{round}(0.01\,\mathrm{WSS})), \max(1, \mathrm{round}(0.05\,\mathrm{WSS})), \max(1, \mathrm{round}(0.10\,\mathrm{WSS}))\}$.
- **Warm-up:** $\min(100{,}000, \lfloor 0.10 \cdot N \rfloor)$.
- **Windows:** $W_{\mathrm{win}} = 50{,}000$ references (primary) and $100{,}000$ references (sensitivity).
- **Triggers & Budgets:** CUSUM (`h=3,5,8`), Page--Hinkley (`lambda=2,5,9`), ADWIN (`delta=0.02,0.002,0.0002`), Periodic (`period=10,20,40` epochs), Random (`p=0.10,0.05,0.025`), Oracle-window trigger, and ContShadow (`every 10 epochs`), all using rankable shadow capacity $C_s = \min(\mathrm{round}(0.2 C), \max(8, \mathrm{round}(0.5 D_w)))$.
- **Consistent Cost Model:** Every policy and controller reports CPU time (`CLOCK_PROCESS_CPUTIME_ID`) inside `pathA_sim`, producing one consistent `ns_per_ref` and `us_per_eval` metric and break-even miss cost $c_m^*$.
- **Unseen-Family Predictive Rule:** Evaluated strictly out-of-family using Leave-One-Family-Out (LOFO) and Cross-Source Holdout (training on application + program traces, testing on unseen public FIU/PDL families, and vice versa).
