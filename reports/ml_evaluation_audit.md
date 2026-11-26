# Phase 7: Exploratory H3 Machine-Learning Evaluation Audit

**Audited Code:** `reproduction/pathA_study/generate_paper_assets.py:201-293`, `reproduction/pathA_study/audit_h3_ml.py`  
**Target:** Exploratory post-hoc binary label $y_i = \mathbf{1}[\max_{f \in \{0.01,0.05,0.10\}} g_i(c_{\text{switch}}=0, f) \ge 0.005]$ across $n = 88$ traces ($13$ positive, $75$ negative; base rate $14.8\%$).  
**Audit Branch:** `research-validation-revision`  
**Date:** 2026-11-26

---

## 1. Leakage & Cross-Validation Verification

1. **LOFO Grouping:** Leave-one-family-out (30 folds, 1–6 traces per held-out family).
2. **Fold-Local Preprocessing:** `std_fold(X[~te], X[te])` computes feature means and standard deviations strictly on the training fold `~te` and applies them to `te`. Confirmed leak-free.
3. **Threshold Policy:** Fixed default threshold $\tau = 0.50$ (no held-out label tuning).
4. **Prediction Pooling:** Out-of-fold probabilities are pooled across all 30 folds (`n = 88`) before computing pooled ROC-AUC, PR-AUC, and confusion matrix.

---

## 2. Exact Confusion Matrices & Metrics ($\lambda = 0.5$, $\tau = 0.5$)

| Evaluation Split | $n_{\text{test}}$ (Pos / Neg) | $n_{\text{train}}$ | TP | FP | FN | TN | Raw Acc. | Bal. Acc. | Prec. | Rec. | $F_1$ | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **LOFO (30 folds)** | 88 (13 / 75) | 82–87 | 0 | 1 | 13 | 74 | 0.841 | 0.493 | 0.000 | 0.000 | 0.000 | **0.895** | **0.471** |
| **Real-app holdout** | 10 (4 / 6) | 78 | 0 | 0 | 4 | 6 | 0.600 | 0.500 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 |
| **Public holdout** | 78 (9 / 69) | 10 | 9 | 9 | 0 | 60 | 0.885 | 0.935 | 0.500 | 1.000 | 0.667 | 0.932 | 0.496 |
| *Majority baseline* | 88 (13 / 75) | — | 0 | 0 | 13 | 75 | **0.852** | 0.500 | 0.000 | 0.000 | 0.000 | 0.500 | 0.148 |

---

## 3. Baseline Comparisons & Interpretation

1. **Why ROC-AUC = 0.895 Co-occurs with $F_1 = 0.000$:**  
   Because only $14.8\%$ ($13/88$) of traces are positive and $L_2$ regularization ($\lambda = 0.5$) shrinks logistic weights toward zero, the mean predicted probability in LOFO is $0.149$ and the maximum across all $88$ traces is $0.554$. Consequently, $\tau = 0.50$ predicts almost all traces negative (`TP=0, FP=1`), performing worse than the majority-class baseline (`0.841 < 0.852`).
2. **Real-App Holdout (`AUC = 1.000`, `Bal. Acc. = 0.500`):**  
   On the $10$ real-app traces ($4$ positive, $6$ negative), `max_prob = 0.171`. Although the $4$ positive traces rank above all $6$ negatives (`ROC-AUC = 1.000`), every probability lies far below $\tau = 0.50$, yielding $0\%$ recall.
3. **Public Holdout (`n_train = 10`, $p = 11$ features):**  
   Training an 11-feature model on $10$ traces ($p > n$) is underdetermined and cannot be treated as a generalizable classifier despite `Bal. Acc. = 0.935`.
4. **Single-Feature LOFO Baseline:**  
   A single feature, `window_reuse_cv`, achieves LOFO `ROC-AUC = 0.791` and `PR-AUC = 0.594` — outperforming the 11-feature logistic model on `PR-AUC` (`0.594` vs. `0.471`). This confirms that the 11-feature model adds complexity without improving precision-recall over a simple reuse-variability metric.

**Conclusion:** H3 remains **strictly exploratory**. Workload features rank relative zero-cost drift propensity better than chance, but do not yield a reliable binary classifier.
