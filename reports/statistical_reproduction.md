# Phase 5: Independent Statistical Reproduction Report

**Reproduction Script:** `reproduction/pathA_study/reproduce_statistics.py`  
**Output Directory:** `results/reproduced_statistics/` (`oracle_aggregations.csv`, `h2_family_level_stats.csv`, `ctrl_diag_reproduced.csv`)  
**Source Data:** `results/raw/*.csv` (read-only, unmodified)  
**Date:** 2026-11-26

---

## 1. Methodology & Statistical Units

1. **Cluster Structure:** The primary corpus has $264$ `(trace, cap_frac)` pairs ($88$ traces $\times$ $3$ capacities $f \in \{0.01, 0.05, 0.10\}$) nested inside $30$ independent workload families. Capacities from the same trace (and traces from the same family) are **not** independent.
2. **H1 Aggregations (`oracle_aggregations.csv`):**
   - `trace_weighted_all` ($n=264$ pairs)
   - `family_macro_30` ($n=30$ unweighted family means)
   - `source_equal_weighted_4` ($n=4$ unweighted source means)
   - `nonstationary_traces_21` ($n=63$ pairs from the $21$ traces with $g(0) > 0.001$)
3. **H2 Controller Tests (`h2_family_level_stats.csv`):**
   - Family-level aggregation: for each of the $17$ controllers, compute the mean $\Delta \text{MR} = \text{MR}_{\text{ctrl}} - \text{MR}_{\text{S3-FIFO}}$ within each of the $30$ families ($n=30$ independent family means; $0$ zero differences for all $17$ controllers).
   - Two-sided Wilcoxon signed-rank test on the $n=30$ family means (`zero_method="wilcox"`), adjusted across $m=17$ controllers via Holm's step-down procedure.
   - Effect size: matched-pair rank-biserial correlation $r_b = (W^+ - W^-) / (W^+ + W^-)$ on family means.
   - 95% Cluster Bootstrap CIs ($3{,}000$ resamples of $30$ families, seed `42`): both **pair-weighted** (concatenating resampled family arrays, matching `generate_paper_assets.py`) and **family-equal-weighted** (averaging resampled family means).

---

## 2. Exact Reproduced Results

### 2.1 H1 Oracle Aggregations ($W = 50{,}000$, $1\%$–$10\%$ WSS)

| Scope | $n$ | $g(C)$ Mean | $g(C)$ Max | $\ge 0.02$ ($c=C$) | $g(0)$ Mean | $g(0)$ Max | $\ge 0.02$ ($c=0$) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `real_app_pageref` | 30 | 0.0004 | 0.0067 | 0/30 | 0.0028 | 0.0196 | 0/30 |
| `instrumented_program` | 180 | 0.0000 | 0.0001 | 0/180 | 0.0000 | 0.0017 | 0/180 |
| `fiu_public` | 36 | 0.0000 | 0.0000 | 0/36 | 0.0058 | 0.0564 | 2/36 |
| `pdl_public` | 18 | 0.0000 | 0.0000 | 0/18 | 0.0008 | 0.0084 | 0/18 |
| **Trace-weighted** | 264 | **0.0001** | 0.0067 | 0/264 | **0.0012** | 0.0564 | 2/264 |
| **Family-macro** | 30 | **0.0001** | 0.0067 | 0/90 grp | **0.0018** | 0.0564 | 0/90 grp |
| **4-Source equal** | 4 | **0.0001** | 0.0067 | — | **0.0024** | 0.0564 | — |
| **Non-stationary ($g(0)>0.001$)** | 63 (21 tr.) | **0.0002** | 0.0067 | 0/63 | **0.0049** | 0.0564 | 2/63 |

All numbers in `table_h1.tex` and Section VIII of `main_template.tex` match `results/raw/oracle_summary.csv` exactly.

### 2.2 H2 Controllers vs. S3-FIFO ($n=30$ Families, 17 Comparisons)

- Every controller has positive $\Delta \text{MR}$ (worse than `S3-FIFO`): pair mean $\Delta \in [+0.0393, +0.0433]$, family-macro mean $\Delta \in [+0.0320, +0.0367]$.
- Pair-weighted 95% cluster bootstrap CIs all exclude zero (`[+0.0194, +0.0635]` to `[+0.0248, +0.0660]`).
- Family-level two-sided Holm-adjusted $p_{\text{fam,Holm}} \in [1.00\times 10^{-4}, 1.17\times 10^{-4}]$.
- Rank-biserial $r_b \in [+0.905, +0.974]$ (`ADWIN-med` and `ADWIN-high` are `+0.9048`, which rounds to `+0.90`).

### 2.3 Discrepancies Identified

1. **`results/raw/h2_controller_analysis.csv` is stale:** It still contains `pval_wilcoxon = 1.0000` from an earlier one-sided (`alternative="less"`) run of `analyze_pathA_study.py`. The current `generate_paper_assets.py` and `reproduce_statistics.py` both produce $p_{\text{fam,Holm}} \in [1.0\times 10^{-4}, 1.2\times 10^{-4}]$.
2. **`main_template.tex` $r_b$ lower bound:** States $r_b \ge 0.91$, whereas `table_h2.tex` and `h2_family_level_stats.csv` show `ADWIN-med` and `ADWIN-high` at $+0.90$.
3. **`main_template.tex` line 276 (`ContShadow` FIU time-share):** States `24.5%` in `S3-FIFO` and `59.7%` in `2Q/LRU/ARC`, whereas `ctrl_diag.csv` and `table_ctrl_diag.tex` actually show `69.3%` in `S3-FIFO`, `11.0%` in `LRU`, `0.6%` in `2Q`, `0.0%` in `ARC`, `14.2%` in `LFU-A`, and `4.8%` in `MRU`.
4. **Caveat from Phase 3:** Because `S3-FIFO` in `pathA_sim.cpp` had a capacity-invariant overrun (`|S|+|M| > C`), the `S3-FIFO` baseline in `oracle_policy.csv` and `controllers.csv` reflects that buggy implementation (see Phase 3 report).

---

## 3. Reproduction Command

```bash
python3 reproduction/pathA_study/reproduce_statistics.py
```
