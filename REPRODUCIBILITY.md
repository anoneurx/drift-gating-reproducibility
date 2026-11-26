# Reproducibility Guide

**Paper:** *When Does Policy Switching Beat the Best Static Policy? A Reproducible Ceiling Study*  
**Repository:** `https://github.com/anoneurx/drift-gating-reproducibility`  
**Revision Branch:** `research-validation-revision` (branched from `47a4261`)  

---

## 1. Software & Hardware Environment

- **OS:** Linux 7.1.5+kali-amd64 (`x86_64`)
- **CPU / RAM:** AMD Ryzen 5 3500U (4 cores / 8 threads), 29 GiB RAM
- **C++ Compiler:** `g++ (Debian 16.2.0-3) 16.2.0` (`-O2 -std=c++17 -Wall -Wextra`)
- **Python:** `3.14.7` with `numpy==2.4.6`, `scipy==1.17.1`, `pandas==2.3.3`, `matplotlib==3.10.9`, `python-docx==1.2.0` (see `requirements.txt` and `environment.md`)
- **LaTeX:** `pdflatex` (TeX Live)

---

## 2. Canonical Artifact Layout

| Path | Purpose |
|---|---|
| `src/pathA_sim.cpp` | Canonical C++17 simulator (21 policies, Viterbi DP oracle, 17 switching controllers, ablations) |
| `src/real_io_bench.cpp` | Linux `pread` OS page-cache syscall microbenchmark |
| `configs/study.yaml` | Complete hyperparameter, seed, capacity, window, and switch-cost specification |
| `results/raw/manifest.csv` | Dataset manifest for all 88 traces (30 families, 4 sources) |
| `results/raw/*.csv` | Unmodified raw experimental outputs (22 CSV files) |
| `results/reproduced_statistics/` | Independent statistical reproduction outputs (`reproduce_statistics.py`) |
| `reproduction/pathA_study/` | Experiment runners, statistical scripts, asset generator, and DOCX builder |
| `tests/validate_simulator.cpp` | 16-check C++ unit & oracle validation suite |
| `tests/external_validation/` | Independent Python reference cross-validation (`LRU`, `FIFO`, `ARC`, `S3-FIFO`, `SIEVE`) |
| `tests/run_tests.py` | 5-check Python CLI & determinism test suite |
| `tests/verify_tables.py` | 10-check automated table/CSV baseline verification (`make verify`) |
| `reports/` | Scientific audit, oracle, external validation, trace, stats, switching-cost, ML, and readiness reports |
| `drift_gating_latex_source/` | Canonical LaTeX source (`main_template.tex`, `build.py`) |
| `supplement/` | Supplementary material (`supplement.tex`, `supplement.pdf`) |

*Note:* Legacy pre-Path-A files at the repository root (`sim.cpp`, `sim_ext.cpp`, `sim_full.cpp`, `paper_final.tex`, `Drift_Aware_Page_Replacement_UPDATED.pdf`) are preserved for historical provenance and are not part of the canonical build.

---

## 3. Dataset Acquisition, Preprocessing & Licensing

- **Redistributable Traces (CC-BY-4.0):**
  - `instrumented_program` (60 `.bin` traces in `traces_real/`): included and verified via `traces/SHA256SUMS`.
  - `real_app_pageref` (10 traces): reproducible locally using `tracer/pc_trace.c` + `tracer/capture_app_traces.py`.
- **Upstream-Only Public Traces (Do Not Redistribute):**
  - `fiu_public` (12 traces) & `pdl_public` (6 traces): sourced from CMU PDL `cacheDatasets` (`https://pdl.cmu.edu/CacheEviction/index.shtml`, `https://pdl.cmu.edu/Publications/copyright.shtml`). Convert using `reproduction/phase6_pdl/convert_pdl_prefix.py` (24-byte `<IQIq` `oracleGeneral` records $\to$ dense first-touch `uint32_t` IDs). Full audit in `reports/trace_methodology_audit.md`.

Verify local trace checksums:
```bash
bash scripts/download_traces.sh --check
```

---

## 4. Exact Commands to Reproduce

### Build & Validate
```bash
make build
make test
python3 tests/external_validation/run_cross_validation.py
```

### Run Primary & Sensitivity Experiments (Requires All 88 `.bin` Traces)
```bash
make oracle       # python3 reproduction/pathA_study/run_study.py --mode oracle
make controllers  # python3 reproduction/pathA_study/run_study.py --mode controllers
make ablation     # python3 reproduction/pathA_study/run_ablation.py
make reviewer     # python3 reproduction/pathA_study/run_reviewer_fixes.py
```

### Reproduce Statistics, Tables, Figures, PDF, and DOCX (From `results/raw/`)
```bash
python3 reproduction/pathA_study/reproduce_statistics.py
python3 reproduction/pathA_study/audit_h3_ml.py
make tables       # regenerates LaTeX tables + PDF figures
make verify       # 10/10 baseline checks
make pdf          # compiles drift_gating_latex_source/main.pdf
python3 reproduction/pathA_study/update_ieee_docs.py
```

### Artifact Checksums (Critical Files)
Generate current SHA-256 checksums for verification:
```bash
sha256sum src/pathA_sim.cpp configs/study.yaml results/raw/oracle_summary.csv results/raw/controllers.csv results/raw/finesweep.csv
```

---

## 5. Zenodo Archival Notes

Before minting a Zenodo DOI:
1. Exclude upstream CMU PDL/FIU `.bin` files (keep `traces/SHA256SUMS`, `results/raw/manifest.csv`, and `convert_pdl_prefix.py`).
2. Tag the final release commit and update `TODO_ZENODO_DOI` in `CITATION.cff` and `README.md`.
