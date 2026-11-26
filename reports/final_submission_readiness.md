# Phase 12: Final Submission Readiness Report

**Paper:** *When Does Policy Switching Beat the Best Static Policy? A Reproducible Ceiling Study*  
**Revision Branch:** `research-validation-revision`  
**Date:** 2026-11-26

---

## 1. Issue Classification Matrix

| # | Issue | Status | Notes / Evidence |
|---|---|---|---|
| 1 | Manuscript prose vs. `table_ctrl_diag.tex` FIU time-share discrepancy (`24.5%` vs. `69.3%`) | **Resolved** | Fixed in `main_template.tex` and `update_ieee_docs.py` to match `ctrl_diag.csv`. |
| 2 | `update_ieee_docs.py` hardcoded Table II & Table IV mismatches | **Resolved** | Fixed and rebuilt `Drift_Gating_Final_IEEE.docx`. |
| 3 | `main_template.tex` $r_b$ lower bound (`0.91` vs. `0.90`) | **Resolved** | Corrected to $r_b \in [+0.90, +0.97]$. |
| 4 | Independent-replay oracle mathematical proof & upper-bound boundary | **Resolved** | Verified DP exactness; added $C=2$ counterexample `{1,2,3,4,1,4,5,4,5}` in `reports/oracle_verification.md` and Section IV. |
| 5 | Statistical reproduction (`n=30` family-level Wilcoxon, Holm, $r_b$, cluster CIs, 4-way H1 aggregations) | **Resolved** | Reproduced independently in `results/reproduced_statistics/` and `reports/statistical_reproduction.md`. |
| 6 | Switching-cost Proposition 1 units/dwell & `switchTo()` 50-trial percentile benchmark | **Resolved** | Audited in `reports/switching_cost_audit.md`; separated from `real_io_bench` syscall overhead. |
| 7 | H3 ML audit (confusion matrices, PR-AUC, majority & single-feature baselines) | **Resolved** | Audited in `reports/ml_evaluation_audit.md`; `window_reuse_cv` PR-AUC (`0.594`) > 11-feat (`0.471`). |
| 8 | Trace conversion pipeline, pseudocode, worked example, and licensing audit | **Resolved** | Documented in `reports/trace_methodology_audit.md`. |
| 9 | Duplicate `pathA_sim.cpp` copies diverged | **Resolved** | Synced `reproduction/pathA_study/pathA_sim.cpp` with `src/pathA_sim.cpp`. |
| 10 | Reproducibility package & `REPRODUCIBILITY.md` | **Resolved** | Created `REPRODUCIBILITY.md`; `make test` (16+5) and `make verify` (10/10) pass. |
| 11 | Independent simulator validation (`LRU`, `FIFO`, `ARC`, `SIEVE`, `S3-FIFO`) | **Partially resolved** | `LRU`, `FIFO`, `ARC`, `SIEVE` match **bit-for-bit (`0` diff)** against independent reference code; `S3-FIFO` revealed a critical capacity-overrun bug (`|S|+|M| > C`). |
| 12 | `S3-FIFO` capacity-invariant bug (`|S|+|M| > C`) in archived 88-trace CSVs | **Requires additional experiments** | Discovered in Phase 3 (`max(|S|+|M|) = 2,118` at $C=1,130$); raw CSVs preserved untouched per integrity rules; requires user approval to fix `S3FIFO` and re-run 88-trace study. |
| 13 | External `libCacheSim` cross-validation (including remaining 16 policies) | **Unresolved** | `libCacheSim` unavailable in offline environment; disclosed in manuscript and `reports/external_simulator_validation.md`. |
| 14 | Stale `results/raw/h2_controller_analysis.csv` (`p=1.000`) & `h3_lofo_analysis.csv` (`acc=1.000`) | **Partially resolved** | Preserved untouched in `results/raw/`; superseded by `results/reproduced_statistics/h2_family_level_stats.csv`. |
| 15 | Zenodo DOI archival (`TODO_ZENODO_DOI`) | **Unresolved** | Pending final post-bugfix release tag and Zenodo upload. |

---

## 2. Final Journal Submission Readiness Recommendation

**Recommendation: NOT YET READY for final IEEE Q1 submission — Major Revision Required (one critical experimental blocker).**

### Honest Assessment
- **What is Q1-ready right now:** The mathematical formulation (including the exact counterexample), the statistical methodology (30-family cluster inference, 4-way sensitivity aggregations), the leak-free H3 analysis, the switching-cost & migration-latency separation, the trace methodology audit, and the reproducibility/test infrastructure (`make test`, `make verify`, `REPRODUCIBILITY.md`, `reports/`) are all at IEEE Q1 standard.
- **What blocks immediate submission:** Phase 3 independent cross-validation uncovered a genuine **capacity-overrun bug in `S3FIFO`** (`src/pathA_sim.cpp:299-325`) that allowed `|S| + |M|` to grow up to $1.87\times C$. Because `S3-FIFO` is the primary global static baseline in Tables III–IV and Fig. 2, **the 88-trace study must be re-executed after fixing `S3FIFO` to enforce $|S| + |M| \le C$** (and cross-checked against `libCacheSim` on a networked machine) before submitting to an IEEE Q1 journal.
