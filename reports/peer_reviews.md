# Phase 11: Three Independent Simulated Peer Reviews

**Manuscript:** *When Does Policy Switching Beat the Best Static Policy? A Reproducible Ceiling Study* (7-page IEEE revision, branch `research-validation-revision`)  
**Date:** 2026-11-26

---

## Reviewer 1 — Operating Systems and Systems Research

**Overall Assessment:**  
The paper asks an important, often-neglected systems question: whether discrete drift-triggered policy switching can beat strong static replacement policies once transition costs are accounted for. The Viterbi DP formulation under independent replay, the $C=2$ counterexample showing why independent replay is not a universal lower bound, and the shadow-ranking diagnosis across 9,564 windows are technically sharp and refreshingly honest. However, the paper's own independent cross-validation (Section VII, Table V) exposes a critical simulator bug in `S3-FIFO` (`|S| + |M| > C` up to $1.87\times C$) that invalidates the archived `S3-FIFO` miss ratios and the controller-vs-`S3-FIFO` comparisons.

**Major Concerns:**
1. **`S3-FIFO` capacity-invariant bug invalidates H2 and Table III/IV baselines:** In `btree_s101` ($C=1{,}130$), the buggy `S3-FIFO` achieved `0.1698` miss ratio using `2,118` resident slots instead of `0.2463` under strict $C=1{,}130$ (where `SIEVE` achieved `0.2348`). Until the 88-trace study is re-run with a fixed strict-capacity `S3-FIFO`, any claim that `S3-FIFO` is the global best static policy or beats all 17 controllers by $+0.04$ cannot be published.
2. **16 of 21 policies lack external cross-validation:** Only `LRU`, `FIFO`, `ARC`, `S3-FIFO`, and `SIEVE` were cross-checked against independent reference code; `CAR`, `LIRS`, `W-TinyLFU`, `CLOCK-Pro`, `LeCaR`, `CACHEUS`, and the learned baselines remain unvalidated against `libCacheSim`.
3. **Trace & kernel realism:** 68.2% of traces are 0.30M-reference instrumented kernels; `LD_PRELOAD` misses post-`mmap` page faults; FIU/PDL traces drop request sizes (`_sz`). Live kernel evaluation (e.g., Linux MGLRU or `cache_ext`) is absent.

**Minor Concerns:**
1. `switchTo()` allocates `O(NP)` vectors inside the hot switching path, distorting small-$C$ latency (`418.98 µs` at $C=64$ vs. `48.75 µs` at $C=512$).
2. Proposition 1 should explicitly state whether `L` is bounded by $T$.

**Specific Required Changes:**
1. Fix `S3FIFO::evict()` and `S3FIFO::access()` in `src/pathA_sim.cpp` to strictly enforce $|S| + |M| \le C$, and re-run all 88 traces for oracle, policy, controller, and ablation CSVs.
2. Cross-validate at least `CAR`, `2Q`, `LIRS`, `W-TinyLFU`, and `CLOCK-Pro` against `libCacheSim`.

**Recommendation:** **Major Revision** (cannot accept until `S3-FIFO` results are re-generated with strict capacity).

---

## Reviewer 2 — Statistics and Experimental Design

**Overall Assessment:**  
The statistical methodology in the revised manuscript is substantially stronger than typical systems papers: it explicitly recognizes the 30-family cluster structure behind the 264 trace–capacity pairs, reports family-level ($n=30$) two-sided Wilcoxon tests with Holm correction, rank-biserial effect sizes, and 3,000-resample cluster bootstrap CIs, and transparently reconciles earlier conflicting $p$-values. The H3 ML evaluation is also commendably honest, reporting `PR-AUC`, confusion matrices, and the failure of $\tau=0.50$ (`F1 = 0.000`).

**Major Concerns:**
1. **H2 inference rests on buggy `S3-FIFO` data:** Although the statistical pipeline is sound, its comparator (`S3-FIFO`) had a capacity bug. The family-level tests must be re-run against the corrected `S3-FIFO` (and/or `SIEVE`) baseline.
2. **Corpus imbalance & short trace length:** 60/88 traces are 0.30M-ref instrumented kernels yielding only 2–5 windows at $W=50\text{k}$–$100\text{k}$. While the 4-way sensitivity aggregates (trace, family, 4-source, 21 non-stationary traces) show robustness for H1, the corpus lacks long, multi-hour real production traces with multiple regime shifts.
3. **Public holdout in H3 (`n_train = 10`, $p = 11$):** Training an 11-feature logistic model on 10 real-app traces is severely underdetermined and should be removed or explicitly flagged as non-interpretable.

**Minor Concerns:**
1. `results/raw/h2_controller_analysis.csv` still contains stale `p = 1.000` values from an earlier run; keep `results/reproduced_statistics/h2_family_level_stats.csv` clearly marked as canonical.
2. Clarify in Table IV whether the bootstrap CI is pair-weighted vs. family-equal-weighted.

**Specific Required Changes:**
1. Re-run `reproduce_statistics.py` after fixing `S3-FIFO`.
2. Drop or demote the `n_train = 10` Public Holdout row in Table VII (`table_h3.tex`).

**Recommendation:** **Major Revision**

---

## Reviewer 3 — IEEE Journal Associate Editor

**Overall Assessment:**  
This manuscript tackles a timely, well-scoped question with an unusually high commitment to scientific transparency and reproducibility. The authors' willingness to document negative results (H1 null ceiling, H3 `F1 = 0.000`), mathematical boundaries (the $C=2$ independent-replay counterexample), and even their own simulator bug (`S3-FIFO` capacity overrun) reflects strong scholarly integrity. However, a reputable IEEE Q1 journal cannot publish empirical tables whose primary static baseline (`S3-FIFO`) had a $1.87\times$ capacity bug.

**Major Concerns:**
1. **Unresolved `S3-FIFO` re-execution:** Because `S3-FIFO` is the central comparator in Abstract, Tables III–IV, Fig. 2, and Section X, publishing archived numbers from the buggy implementation is unacceptable for final publication, even with a disclosure footnote.
2. **External validation scope:** Complete `libCacheSim` cross-validation on a clean external machine before final submission.

**Minor Concerns:**
1. Expand the trace-conversion worked example and full 30-family table into the main paper or verified appendix if journal page limits allow.
2. Mint a permanent Zenodo DOI and replace `TODO_ZENODO_DOI` placeholders in `CITATION.cff` and `README.md`.

**Specific Required Changes:**
1. Fix `S3FIFO` in `src/pathA_sim.cpp`, re-run the full 88-trace study, and update all tables, figures, and statistical tests.
2. Provide `libCacheSim` cross-validation logs for core policies.

**Recommendation:** **Major Revision**
