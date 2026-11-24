# Changes

## 2026-11-24: Single updated PDF; stale manuscript PDFs removed

- **Change:** Created `Drift_Aware_Page_Replacement_UPDATED.pdf` by concatenating the current `drift_gating_latex_source/main.pdf` (11 pages) and `drift_gating_latex_source/supplement.pdf` (13 pages), for 24 pages total.
- **Change:** Removed all superseded manuscript PDFs from the repository root, both LaTeX trees and `reproduction/`; retained only figure PDFs needed by the LaTeX sources.
- **Change:** Updated `reproduction/final_hygiene.py` to validate the single consolidated PDF instead of deleted per-tree PDFs.
- **Note:** The main and supplement retain their independent reference numbering, so the consolidated PDF contains main `[12]`/`[27]` and supplement `[41]`.

## 2026-11-24: Reviewer-flagged references verified and corrected

- **Change:** Kept Patel & Maniar and EACLOCK after DOI/publisher verification; added direct DOI/journal URLs and the Nov. 2026 EACLOCK issue date to all bibliography sources.
- **Change:** Narrowed the CMU PDL licence wording. The manuscript now states the verified project page, FTP `cacheDatasets` listing, exact FIU `madmax` filename and README format/citation terms, and explicitly says no dataset-specific licence file was found; use is described as non-commercial research with citation, not as use under a dataset licence.
- **Evidence:** `REFERENCE_VERIFICATION.md`; `AUDIT_REPORT.md` section 2.3a; `claims_to_sources.csv`.
- **Files:** `drift_gating_latex_source/build.py`, `drift_gating_latex_source/main.tex`, `drift_gating_latex_source/supplement.tex`, `paper_final.tex`, `latex/main.tex`, `latex/supplement.tex`, and audit/protocol ledgers. Rebuilt current PDFs and regenerated `main.txt`/`paper.txt`; no performance result changed.

## 2026-11-23: Real post hoc experiments integrated; manuscript/audit updated

### Post hoc simulator/code (real, labeled)
- **Change:** Added `--trigger cusum|periodic|random|oracle`, `--trigger-period`, `--trigger-rand`, `--trigger-seed`, `--delta` to `reproduction/sim_full.cpp`; rebuilt `sim_full`.
- **Evidence:** Default CUSUM DA verification: 110 rows, 0 mismatches, detection identical vs `main_study_results.csv`/`main_study_detection.csv`. Raw outputs in `reproduction/trigger_real/`.

### Real post hoc experiments completed
- **Synthetic trigger variants (seed 5001, 80 non-stable+30 stable, da-only):** oracle/periodic/random runs in `reproduction/trigger_real/*.csv`, with paired DA-minus-other bootstrap 10k seed 0 + Wilcoxon/Holm computed from raw CSVs.
- **FIU trigger check (default seed 5001, C=1000, same FIU base args, da-only):** `trigger_real/fiu_oracle.csv`, `fiu_periodic_p40.csv`, `fiu_random_r04.csv`; oracle confirms=0 because FIU traces expose no ground-truth bounds.
- **Param sensitivity sweep (seed 5001, one-at-a-time delta/h/W/p):** `reproduction/param_sweep/summary.csv` via `python3 run_param_sweep.py`.
- **Rankability/capacity-p sweeps:** `reproduction/rankability_real/fiu_sweep.csv` via `run_rankability_fiu.py`; `reproduction/rankability_real/synth_sweep.csv` via `run_rankability_synth.py`.
- **Evidence/commands:** recorded in `NOT_DONE.md`.

### Manuscript fixes
- **Change:** Added `\subsection{Post Hoc Measurement Experiments}` (`sec:posthoc`) in `latex/main.tex`/`paper_final.tex` reporting trigger/param/rankability real results; all labeled post hoc; FIU oracle no-bounds caveat included.
- **Change:** Updated Limitations to include post hoc caveats and explicit unavailable gaps (MSR/Alibaba/Tencent/CloudPhysics; W-TinyLFU/SIEVE; ADWIN/Page-Hinkley; real async/kernel prototype).
- **Change:** No mock/assumed data added; unavailable items remain only in `NOT_DONE.md`.

### Audit/reproducibility
- **Change:** Updated `reproduction/check_paper_numbers.py` to verify post hoc measurements (255/255 PASS).
- **Change:** Updated `claims_to_sources.csv` with 13 post hoc real-run rows.
- **Change:** Updated `selfaudit.md`, `NOT_DONE.md`; rebuilt `latex/main.pdf` (17 pages, pdflatex twice) and synced `paper_final.tex`.

## Prior 2026-11-23 A-F pass (retained)
- Repaired capacity-sampling correction (post hoc, `--cs-cap-f`, f=1.0 recorded post hoc): identical public/synthetic/holdout outcomes; original primary.
- Detection offsets 333/1501 added; offset table regenerated from raw CSVs.
- Abstract/Intro/Conclusion/Methods/Results wording normalized; failed external validation and repaired outcome reported.
- Claim-to-source/check script/self-audit/NOT_DONE created; manuscript forbidden-string grep clean for body.
