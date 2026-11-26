# Phase 8: Results and Sensitivity Consistency Audit

**Audited Files:** `results/raw/{oracle_summary,finesweep,oracle_policy,controllers,shadow_ablation,pool21,shadow_ranking,ctrl_diag}.csv`, `results/tables/*.tex`, `drift_gating_latex_source/main_template.tex`  
**Audit Branch:** `research-validation-revision`  
**Date:** 2026-11-26

---

## 1. Verified Quantitative Consistency

| Component | Verified Metric(s) | Status |
|---|---|---|
| **Primary H1 ($1\%$–$10\%$ WSS, $W=50$k)** | $0/90$ family–cap groups clear $0.02$ at $c=C$; trace mean $g(C)=0.0001$ ($0.0000503$), max $0.0067$; $c=0$: $2/264$ clear $0.02$, mean $0.0012$, max $0.0564$. | **PASS** |
| **Aggregations (Phase 5)** | Family-macro ($n=30$): $g(C)=0.0001, g(0)=0.0018$; 4-source equal: $g(C)=0.0001, g(0)=0.0024$; Non-stationary ($n=21$ traces): $g(C)=0.0002, g(0)=0.0049$. | **PASS** |
| **Capacity Scaling ($1\%$–$50\%$ WSS, $W=50$k)** | Table III rows ($n=88$/row): $1\%$ (`S3=0.5545, Best=0.5496, gC=0.0000`), $5\%$ (`0.4750, 0.4741, 0.0000`), $10\%$ (`0.4376, 0.4364, 0.0001`), $25\%$ (`0.3348, 0.3294, 0.0006`, $2/88$ clear), $50\%$ (`0.1695, 0.1503, 0.0003`, $0/88$ clear); total $2/440$ ($0.45\%$) at $c=C$. | **PASS** |
| **Cost $\times$ Window Sweep (`finesweep.csv`)** | $W=5$k: $20/264$ ($7.6\%$) at $c=0$, $13/264$ ($4.9\%$) at $0.10C$, $7/264$ at $0.25C$; $0/264$ for $c \ge 0.50C$ across all $W \in \{5\text{k},10\text{k},25\text{k},50\text{k}\}$. | **PASS** |
| **Best Static vs. S3-FIFO** | `S3-FIFO` = global best static ($0.4890$ mean MR, wins $176/264$ pairs); `Per-Pair Best Static` = ex-post min of $21$ policies per pair. Clearly distinguished. | **PASS** |
| **Shadow Ablations & Pool21** | `FullShadow`: $+0.0284$ ($705$\,ns/ref); `FullShadow-CostAware`: $+0.0286$; `PersistentShadow`: $+0.0175$ ($2{,}985$\,ns/ref); `PersistentShadow-CostAware`: $+0.0191$; `ContShadow-21`: $+0.0470$. | **PASS** |
| **Shadow Ranking (`shadow_ranking.csv`)** | $4{,}770 + 4{,}794 = 9{,}564$ eval windows; `ContShadow-0.2C` top-1 agree $= 67.67\%$ ($67.7\%$); `FullShadow-1.0C` $= 67.90\%$ ($67.9\%$). | **PASS** |

---

## 2. Discrepancies Found Requiring Correction

1. **CRITICAL — `main_template.tex:276` FIU time-share prose contradicts `table_ctrl_diag.tex`:**  
   Prose says *"spends only 24.5% of references in S3-FIFO on FIU traces while mis-allocating 59.7% to 2Q/LRU/ARC"*. Actual `ctrl_diag.csv` & `table_ctrl_diag.tex` show `ContShadow (FIU)` spends **69.3%** in `S3-FIFO`, **11.0%** in `LRU`, **0.6%** in `2Q`, **0.0%** in `ARC`, **14.2%** in `LFU-A`, and **4.8%** in `MRU` (`11.6%` in `2Q/LRU/ARC`; `30.7%` non-`S3-FIFO`).
2. **HIGH — `main_template.tex:65, 222` $r_b$ lower bound:**  
   Prose states $r_b \ge 0.91$, whereas `table_h2.tex` & `h2_family_level_stats.csv` show `ADWIN-med` and `ADWIN-high` at $+0.90$ ($+0.9048$).
3. **HIGH — `update_ieee_docs.py` hardcoded Table II & Table IV mismatches:**  
   Hardcoded values in `update_ieee_docs.py` disagreed with `table_h1.tex` and `table_h2.tex`.
4. **CRITICAL SIMULATOR CAVEAT (from Phase 3):**  
   All `S3-FIFO` miss ratios in `results/raw/*.csv` reflect `src/pathA_sim.cpp`'s `S3FIFO` bug (`|S|+|M| > C`). We must disclose this transparently in the manuscript and readiness report (or re-run if approved by the user).
