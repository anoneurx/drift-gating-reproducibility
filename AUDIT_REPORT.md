# Q1 Journal Submission Audit — *When Does Policy Switching Beat the Best Static Policy? A Reproducible Ceiling Study*

**Date:** 2026-11-26  
**Target Venues:** ACM Transactions on Storage (TOS), IEEE Transactions on Computers (TC), IEEE TPDS, Performance Evaluation  
**Audited Artifacts:**
- `drift_gating_latex_source/main_template.tex` & `main.pdf` (currently 6 pages)
- `drift_gating_latex_source/supplement.tex` & `supplement.pdf` (currently 3 pages)
- `Drift_Gating_Final_IEEE.pdf` (6 pages) & `Drift_Gating_Final_IEEE.docx`
- `reproduction/pathA_study/` (simulator, runner scripts, CSVs, asset/DOCX generators)
- `reproduction/final_hygiene.py`

---

## Executive Verdict

**Scientifically sound and reproducible, but NOT YET ready for Q1 journal submission.**  
The core empirical claims, exact Viterbi DP oracle, 5-point cost sweep, 17-controller comparison, failure-mode decomposition, and unseen-family LOFO predictive rule are all verified against the raw CSVs in `reproduction/pathA_study/results/`. However, **four concrete gaps** block Q1 readiness:

1. **Manuscript length (Critical):** `main.pdf` is 6 IEEE two-column pages (conference/workshop length). Q1 systems/storage journals expect **10–14 pages** with a formal problem formulation, thorough 2024–2026 related-work positioning, per-source & per-trace case studies, deeper sensitivity analysis, and an expanded threat model.
2. **Unused bibliography entries (Moderate):** `drift_gating_latex_source/build.py` defines 42+ references—including 13 recent 2024–2026 works (`eaclock`, `clock2q`, `s4fifo`, `pudd`, `spc`, `dynthr`, `tae`, `htm`, `adwinu`, `msched`, `gpuext`, `prefix`, `stale`)—that are currently uncited in `main_template.tex`.
3. **Word document formatting (Moderate):** `Drift_Gating_Final_IEEE.docx` renders mathematical symbols (`c_switch`, `C_s`, `D_w`, `M_oracle`) as plain ASCII/Unicode text instead of proper Word subscript/superscript runs, and needs to be synced with the expanded manuscript.
4. **Hygiene / deliverable parity (Minor):** `Drift_Aware_Page_Replacement_UPDATED.pdf` was removed in commit `bd244f7`, causing `final_hygiene.py` to report `missing` for the unified PDF, while `check_paper_numbers.py` still targets the legacy `latex/` tree.

---

## 1. Verified Claims & Numbers (PASS)

Every headline number in the current manuscript matches `reproduction/pathA_study/results/*.csv`:

| Claim | Verified Value | Source File |
|---|---|---|
| Corpus size | 88 traces, 30 families, 264 trace–capacity pairs | `manifest.csv`, `oracle_summary.csv` |
| H1 ($c_{\text{switch}}=C$, $W=50\text{k}$) | 0/90 groups $\ge 0.02$; mean $g=0.0001$, median $0.0000$, max $0.0067$ | `h1_oracle_analysis.csv`, `oracle_summary.csv` |
| H1 zero-cost ($c_{\text{switch}}=0$, $W=50\text{k}$) | Mean $g=0.0012$ (macro $0.0024$), 2/264 $\ge 0.02$ (`fiu_online` $0.0564$, $0.0208$) | `oracle_summary.csv` |
| $W=100\text{k}$ sensitivity | $c=C$: 0/264 $\ge 0.02$ (max $0.0067$); $c=0$: 1/264 $\ge 0.02$ (max $0.0419$) | `oracle_summary_w100000.csv` |
| 5-point cost sweep | $0/264$ clear $0.02$ whenever $c_{\text{switch}} \ge 0.50C$; at $W=10\text{k}, c=0$: $14/264$ ($5.3\%$) | `cost_sweep.csv` |
| Best static policy | `S3-FIFO`: mean miss ratio $0.4890$ ($59.5\text{ ns/ref}$), best on $176/264$ ($66.7\%$) | `oracle_policy.csv`, `oracle_summary.csv` |
| H2 (17 controllers vs `S3-FIFO`) | All lose by $+0.0393$ to $+0.0433$, Holm $p=1.000$, $92.9$–$199.1\text{ ns/ref}$ | `h2_controller_analysis.csv`, `controllers.csv` |
| Failure-mode decomposition | `ContShadow` spends $67.1\%$ in `S3-FIFO`, $18.9\%$ `LRU`, $6.0\%$ `MRU`, $4.4\%$ `LFU-A`, $3.4\%$ `2Q`, $0.2\%$ `ARC` | `ctrl_diag.csv` |
| H3 exploratory LOFO ($g(0) \ge 0.005$) | 13/88 positive; LOFO acc $=84.1\%$, $\text{AUC}=0.901$ | `h3_lofo_analysis.csv`, `h3_exploratory_weights.csv` |
| Candidate pool consistency | 6-policy pool (`LRU`, `LFU-A`, `2Q`, `MRU`, `S3-FIFO`, `ARC`) matches `pathA_sim.cpp` | `pathA_sim.cpp` |

---

## 2. Issues to Fix Before Q1 Submission

### Issue 1: Paper Length & Depth (6 pages → Target 10–12 IEEE pages)
- **Add Section III (Formal Problem Formulation):** Define the trace, working-set capacity $C$, windowing, candidate policy pool $\mathcal{P}$, exact switch-cost model, sampled shadow evaluation constraint $\Cs/\Dw < 1$, and formal H1–H3 hypotheses in the main text.
- **Expand Section II (Related Work):** Integrate the 13 uncited 2024–2026 references from `build.py` (`eaclock`, `clock2q`, `s4fifo`, `pudd`, `spc`, `dynthr`, `tae`, `htm`, `adwinu`, `msched`, `gpuext`, `prefix`, `stale`) to situate the study against current learned eviction, unsupervised drift detection, and extensible OS/GPU memory management.
- **Add Per-Source & Trace Case Studies:** Explain *why* `fiu_online.cs.fiu.edu_test` ($g(0)=0.0564$, `window_reuse_cv=2.5916`) and `git_repo_s202` ($g(0)=0.0196$) exhibit zero-cost headroom while `sqlite_join_agg_s101` ($g(C)=0.0005$, `window_reuse_cv=0.0012`) does not, and break down the `W=10k` zero-cost sweep by source (`fiu_public`: 10/36, `real_app_pageref`: 4/30, `instrumented_program`: 0/180, `pdl_public`: 0/18).
- **Expand Sensitivity & Threat Model:** Incorporate the `W=100k` results directly into Section VI, add a per-source cost-sweep breakdown table, and deepen the threats-to-validity discussion (user-space `LD_PRELOAD` vs. kernel page-fault/readahead/writeback, corpus weighting, sub-10k micro-phases, and local-git post-hoc status).

### Issue 2: Word Document (`.docx`) Fidelity
- Update `reproduction/pathA_study/update_ieee_docs.py` to mirror all new sections and tables.
- Format mathematical subscripts/superscripts (`c_switch`, `C_s`, `D_w`, `M_oracle`, `M_best`, `n_warm`, `n_eval`, `p_90`, `p_Holm`) using proper Word `rPr/vertAlign` runs rather than plain underscores.

### Issue 3: Unified Deliverable & Clean Build
- Ensure `Drift_Gating_Final_IEEE.pdf`, `Drift_Gating_Final_IEEE.docx`, and `Drift_Aware_Page_Replacement_UPDATED.pdf` (merged `main.pdf` + `supplement.pdf`) are all rebuilt, verified for 0 undefined references and 0 overfull hboxes, and committed cleanly.
