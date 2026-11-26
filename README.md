# When Does Policy Switching Beat the Best Static Policy?
## A Reproducible Ceiling Study — Artifact README

> **Paper DOI:** `TODO_ZENODO_DOI` | **Code DOI:** `TODO_ZENODO_CODE_DOI`
> **Anonymous for review** — author information omitted per double-blind policy.

---

## 1. Summary

We study whether online cache-policy switching can materially outperform the best single static policy on the same workload. Using an exact Viterbi DP hindsight oracle over 88 traces, 21 replacement policies, 17 online switching controllers, three cache sizes (1%, 5%, 10% WSS), four window sizes (W ∈ {5k, 10k, 25k, 50k} references), and nine switch-cost fractions (0–C), we find that the oracle ceiling is nearly zero in practice once realistic switch costs are applied. All 17 online controllers lose to static S3-FIFO under two-sided Wilcoxon tests (p ≈ 1.0 after Holm correction).

**Simulator:** C++17 single-file `src/pathA_sim.cpp` (~1,900 lines).
**Oracle:** Exact under the *independent-replay model* (each policy runs with its own warm cache; real switching incurs additional cold-start misses not modelled here).

---

## 2. Key Results

| # | Finding | Paper Reference |
|---|---------|-----------------|
| 1 | **0 of 264 pairs** clear ≥ 2% net gain at switch cost c = C (full refill); 2 of 440 at c = C when 25/50% WSS extended traces are included | Table III (H1), Fig. 2 |
| 2 | **At c ≥ 0.50C, W = 50k:** only 4/440 pairs clear the 2% threshold; the oracle ceiling collapses smoothly above c ≈ 0.25C | Table V (cost sweep), Fig. 2 |
| 3 | **All 17 switching controllers lose to static S3-FIFO** (mean miss-ratio excess +0.0412; two-sided Wilcoxon p = 1.000 for every controller after Holm correction) | Table VII (H2), Fig. 3 |

---

## 3. Requirements

| Item | Minimum | Tested on |
|------|---------|-----------|
| Compiler | g++ 14, C++17 | g++ 16.2.0 |
| OS | Linux | Ubuntu 24.04 |
| Python | 3.11 | 3.14.7 |
| numpy | 1.24 | 2.4.6 |
| scipy | 1.10 | 1.17.1 |
| pandas | 1.5 | 2.3.3 |
| matplotlib | 3.6 | 3.10.9 |
| python-docx | 0.8 | 1.2.0 |
| pdflatex | TeX Live 2022 | TeX Live 2024 |
| RAM | 4 GB | 32 GB |
| Disk | 2 GB (without traces) | — |
| CPU | x86-64 | Intel/AMD, 8+ cores recommended |

**Expected runtime:** ~4–8 hours for `make all` on 8 cores (dominated by the oracle simulation over 88 traces).

---

## 4. Quick Start (< 5 minutes)

```bash
# 1. Clone
git clone https://github.com/anoneurx/drift-gating-reproducibility.git
cd drift-gating-reproducibility

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Build the simulator
make build
# → creates src/pathA_sim and src/real_io_bench

# 4. Smoke-test on one trace (the FIU homes trace, already in results/raw/)
./src/pathA_sim \
    --trace reproduction/public_split/fiu_homes_test.bin \
    --label fiu_homes_test --family fiu_homes --source fiu_public \
    --cap-frac 0.01 --C 2455 --np 2455 --window 50000 \
    --out-prefix /tmp/smoke_test --mode oracle

# 5. Unit tests
make test
```

> **Note:** The FIU trace must be downloaded first; see Section 7.

---

## 5. Full Reproduction

```bash
make all
```

This runs, in order:

1. `oracle` — hindsight DP oracle (all traces × caps × W × costs)
2. `controllers` — 17 online controllers
3. `ablation` — shadow-budget variants
4. `reviewer` — fine cost/window sweep + 25/50% WSS
5. `tables` — regenerate all LaTeX tables
6. `figures` — regenerate all figures
7. `pdf` — build the paper PDF

**Outputs:**

| Path | Contents |
|------|----------|
| `results/raw/*.csv` | Raw simulation data (22 CSV files) |
| `drift_gating_latex_source/table_*.tex` | LaTeX tables |
| `drift_gating_latex_source/figs/*.pdf` | Figures |
| `Drift_Gating_Final_IEEE.pdf` | Final compiled paper |

Verify that regenerated tables match stored baselines:

```bash
make verify   # prints PASS/FAIL for each key metric
```

---

## 6. Paper → Script → Output Mapping

| Paper Item | Generating Script | Output File |
|------------|-------------------|-------------|
| Table I (trace sources) | `reproduction/pathA_study/generate_paper_assets.py` | `drift_gating_latex_source/table_sources.tex` |
| Table II (hyperparameters) | — (manual / `configs/study.yaml`) | `configs/study.yaml` |
| Table III (H1 oracle ceiling) | `generate_paper_assets.py` | `drift_gating_latex_source/table_h1.tex` |
| Table IV (family breakdown) | `generate_paper_assets.py` | `drift_gating_latex_source/table_all_families.tex` |
| Table V (cost sweep) | `generate_paper_assets.py` | `drift_gating_latex_source/table_cost_sweep.tex` |
| Table VI (fine sweep grid) | `generate_paper_assets.py` | `drift_gating_latex_source/table_finesweep.tex` |
| Table VII (H2 controllers) | `generate_paper_assets.py` | `drift_gating_latex_source/table_h2.tex` |
| Table VIII (ctrl diagnostics) | `generate_paper_assets.py` | `drift_gating_latex_source/table_ctrl_diag.tex` |
| Table IX (shadow ablation) | `generate_paper_assets.py` | `drift_gating_latex_source/table_ablation.tex` |
| Table X (pread benchmark) | `reproduction/pathA_study/run_reviewer_fixes.py` | `results/raw/real_io_bench.csv` |
| Table XI (H3 feature weights) | `generate_paper_assets.py` | `drift_gating_latex_source/table_feat_weights.tex` |
| Fig. 1 (oracle ceiling) | `generate_paper_assets.py` | `drift_gating_latex_source/figs/fig_oracle_ceiling.pdf` |
| Fig. 2 (cost sweep) | `generate_paper_assets.py` | `drift_gating_latex_source/figs/fig_cost_sweep.pdf` |
| Fig. 3 (controllers vs S3-FIFO) | `generate_paper_assets.py` | `drift_gating_latex_source/figs/fig_controllers_vs_s3fifo.pdf` |
| Fig. 4 (shadow ranking accuracy) | `generate_paper_assets.py` | `drift_gating_latex_source/figs/fig_shadow_ranking.pdf` |
| Fig. 5 (shadow ablation) | `generate_paper_assets.py` | `drift_gating_latex_source/figs/fig_shadow_ablation.pdf` |
| Fig. 6 (LOFO ROC curve) | `generate_paper_assets.py` | `drift_gating_latex_source/figs/fig_lofo_roc.pdf` |
| Fig. 7 (window timeline) | `generate_paper_assets.py` | `drift_gating_latex_source/figs/fig_window_timeline.pdf` |
| Table S1 (all families) | `generate_paper_assets.py` | `supplement/table_all_families.tex` |
| Table S2 (feature weights) | `generate_paper_assets.py` | `supplement/table_feat_weights.tex` |

---

## 7. Traces

### In-repository (no download needed)

| Family | Count | Location | License |
|--------|-------|----------|---------|
| Instrumented kernels (`bfs`, `dfs`, `sqlite`, `redis`, …) | 60 | `traces_real/` | MIT (this repo) |
| Real-app traces (`git_repo`, `npm_install`, …) | 10 | `reproduction/app_traces/bins/` | MIT (this repo) |

### Must be downloaded separately

| Family | Source | URL | Redistribution |
|--------|--------|-----|----------------|
| FIU WebSearch (homes, mail, webserver, webvm) | Koller & Rangaswami 2010 | `https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/` | Non-commercial research only |
| PDL traces | CMU PDL | `https://ftp.pdl.cmu.edu/pub/datasets/` | Non-commercial research only |

**Download and convert FIU traces:**

```bash
bash scripts/download_traces.sh   # follows prompts for restricted traces
# or manually:
wget https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/fiu.tar.gz
tar xf fiu.tar.gz -C /tmp/fiu
python3 reproduction/split_public_traces.py   # converts to uint32 binary format
```

**Verify checksums:**

```bash
bash scripts/download_traces.sh --check
# or:
sha256sum -c traces/SHA256SUMS
```

### Trace format

Binary little-endian `uint32` page IDs, one per 4 bytes. No header. The simulator reads with `fread`.

---

## 8. Configuration

All hyperparameters are in [`configs/study.yaml`](configs/study.yaml):

```yaml
windows:    [10000, 25000, 50000, 100000]
cap_fracs:  [0.01, 0.05, 0.10]           # main study; reviewer adds 0.25, 0.50
cost_fracs: [0.0, 0.10, 0.25, 0.50, 1.0] # fine sweep adds 0.02,0.05,0.15,0.20
threshold:  0.02                           # 2% net gain threshold (H1)
warmup_frac: 0.10                          # 10% of trace discarded as warmup
```

---

## 9. Seeds and Determinism

| Component | Seed | Location | Notes |
|-----------|------|----------|-------|
| `LRBStyle` RNG | `4242` (`RNG`) | `src/pathA_sim.cpp` line 992 | Hardcoded; not a CLI flag yet |
| `SwitchingController` RNG | `99` (`trigRng`) | `src/pathA_sim.cpp` line 1270 | Used by `Random-*` triggers |
| Cluster bootstrap (Python) | `42` | `generate_paper_assets.py` line 148 | `np.random.default_rng(42)` |
| DP oracle | deterministic | — | Viterbi DP has no randomness |

The DP oracle and all static-policy miss ratios are fully deterministic. Controller results use seed 4242; re-running the simulator binary with identical arguments produces identical CSV output.

> **TODO:** Add `--seed` CLI flag to `src/pathA_sim.cpp` for full reproducibility documentation.

---

## 10. Known Limitations

As disclosed in the paper (Section X):

1. **User-space LD_PRELOAD tracer** — does not capture kernel page-fault traffic (OS page cache). Block-I/O traces are proxies, not page traces.
2. **Short traces** — most instrumented-kernel traces have ~0.3M references; at W = 100k, the DP has only 2–3 windows to switch between.
3. **Independent-replay oracle** — each policy runs with its own warm cache. A real switch would incur additional cold-start misses (the new policy inherits no eviction state from the old one).
4. **No live Linux MGLRU or `cache_ext` experiment** — results are simulation-only.
5. **Capacities capped at 10% WSS** in the main study (25/50% added in reviewer pass but not yet fully integrated into all tables).
6. **68% of traces are stationary kernels** — the "no switching gain" result is nearly guaranteed for this family.
7. **No cross-validation against libCacheSim** — simulator policy correctness is validated by hand on small traces only (see Section 11).

---

## 11. Validation

| Policy | Validation method |
|--------|-------------------|
| LRU | Hand-trace on 10-ref sequence; miss count matches expected |
| FIFO | Hand-trace on 10-ref sequence |
| S3-FIFO | Miss ratio decreases monotonically as capacity increases (verified programmatically) |
| ARC | Verified invariant: `|T1| + |T2| ≤ C` at all times |
| DP oracle | Verified: oracle miss ratio ≤ best-static miss ratio for all 264 pairs |

> **TODO:** Cross-validate S3-FIFO and ARC against libCacheSim on standard traces.

Run the unit tests with:

```bash
make test
# or:
python3 tests/run_tests.py
```

---

## 12. Citation

```bibtex
@article{anon2025driftgating,
  title   = {When Does Policy Switching Beat the Best Static Policy?
             A Reproducible Ceiling Study},
  author  = {Anonymous Authors},
  journal = {TODO: venue},
  year    = {2025},
  doi     = {TODO_ZENODO_DOI},
  note    = {Artifact: \url{https://github.com/anoneurx/drift-gating-reproducibility}}
}
```

**License:** Code is MIT (see [LICENSE](LICENSE)). Trace data redistributed under their original licenses (see [traces/README.md](traces/README.md)).

---

## 13. Contact

> **Anonymous for double-blind review.**
> Contact: `TODO: anonymized for review` — will be revealed upon acceptance.

---

## Appendix: Repository Structure

```
.
├── Makefile                  # build / test / verify / all targets
├── README.md                 # this file
├── LICENSE                   # MIT (code) + data license notes
├── CITATION.cff              # machine-readable citation
├── environment.md            # exact compiler/Python versions used
├── requirements.txt          # Python dependencies
├── configs/
│   └── study.yaml            # all hyperparameters (Table II)
├── src/
│   ├── pathA_sim.cpp         # C++17 simulator (oracle + controllers)
│   └── real_io_bench.cpp     # pread latency benchmark
├── tracer/                   # LD_PRELOAD page-access tracer
├── scripts/
│   ├── download_traces.sh    # download + SHA-256 verify traces
│   ├── run_all.sh            # full end-to-end reproduction
│   └── make_anon.sh          # create anonymised copy
├── traces/
│   ├── README.md             # sources, licenses, download steps
│   └── SHA256SUMS            # checksums for all 88 traces
├── traces_real/              # 60 instrumented-kernel .bin traces
├── results/
│   ├── raw/                  # 22 CSV files (oracle, controllers, ablation, …)
│   └── tables/               # LaTeX table .tex files (copies)
├── figures/                  # figure PDFs + generating script
├── tests/
│   ├── run_tests.py          # unit tests (policy correctness, oracle bound)
│   ├── verify_tables.py      # `make verify` baseline comparisons
│   └── expected/
│       └── baseline_numbers.csv
├── supplement/               # Tables S1, S2 (supplement.tex, supplement.pdf)
├── reproduction/
│   └── pathA_study/          # canonical study scripts
│       ├── run_study.py      # oracle + controller sweep
│       ├── run_reviewer_fixes.py  # fine sweep + benchmark
│       ├── run_ablation.py   # shadow-budget ablation
│       └── generate_paper_assets.py  # tables + figures
└── drift_gating_latex_source/
    ├── build.py              # LaTeX → PDF compiler
    ├── main_template.tex     # paper source
    └── figs/                 # figure PDFs (output of generate_paper_assets.py)
```
