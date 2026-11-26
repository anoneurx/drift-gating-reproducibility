#!/usr/bin/env python3
"""
Path A study analysis.
Requires ONLY numpy, scipy, pandas (no sklearn).
Implements:
 1. Summary statistics per (family, cap_frac): mean net_oracle_gain,
    fraction of traces meeting the >=0.02 threshold (H1)
 2. Wilcoxon signed-rank test + Holm correction: each controller vs S3-FIFO (H2)
 3. Leave-One-Family-Out (LOFO) logistic regression via scipy.optimize (H3)
 4. Cross-source holdout (real_app_pageref vs public traces)
Writes: analysis_summary.csv, lofo_rule.csv, tables for paper.
"""
import csv
import sys
from pathlib import Path
import numpy as np
import scipy.stats as stats
import scipy.optimize as opt

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"

WORTHWHILE_GAIN = 0.02
WORTHWHILE_FRAC = 2 / 3


# ── helpers ────────────────────────────────────────────────────────────────

def load_csv(name):
    p = RESULTS / name
    if not p.exists():
        print(f"WARNING: {p} not found", file=sys.stderr)
        return []
    with open(p, newline="") as fh:
        return list(csv.DictReader(fh))


def holm_correction(pvals):
    """Return Holm-corrected p-values."""
    n = len(pvals)
    indexed = sorted(enumerate(pvals), key=lambda x: x[1])
    corrected = [0.0] * n
    for rank, (orig_i, p) in enumerate(indexed):
        corrected[orig_i] = min(1.0, p * (n - rank))
    # make monotone
    order = [i for i, _ in sorted(enumerate(pvals), key=lambda x: x[1])]
    max_so_far = 0.0
    for i in order:
        corrected[i] = max(corrected[i], max_so_far)
        max_so_far = corrected[i]
    return corrected


def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -50, 50)))


def logreg_loss(w, X, y, lam=1.0):
    p = sigmoid(X @ w)
    p = np.clip(p, 1e-10, 1 - 1e-10)
    nll = -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()
    reg = 0.5 * lam * (w[1:] ** 2).sum()
    return nll + reg


def logreg_grad(w, X, y, lam=1.0):
    p = sigmoid(X @ w)
    err = p - y
    g = X.T @ err / len(y)
    g[1:] += lam * w[1:]
    return g


def fit_logreg(X, y, lam=1.0):
    w0 = np.zeros(X.shape[1])
    res = opt.minimize(logreg_loss, w0, jac=logreg_grad,
                       args=(X, y, lam), method="L-BFGS-B",
                       options={"maxiter": 500, "ftol": 1e-9})
    return res.x


def predict_logreg(w, X):
    return sigmoid(X @ w)


def auc_roc(y_true, scores):
    """Compute AUC-ROC."""
    pos = y_true == 1
    neg = y_true == 0
    if pos.sum() == 0 or neg.sum() == 0:
        return float("nan")
    s_pos = scores[pos]
    s_neg = scores[neg]
    # Mann-Whitney U
    u = sum(1.0 if sp > sn else 0.5 if sp == sn else 0.0
            for sp in s_pos for sn in s_neg)
    return u / (pos.sum() * neg.sum())


# ── H1: Oracle gain analysis ────────────────────────────────────────────────

def analyze_oracle(oracle_rows):
    if not oracle_rows:
        print("No oracle_summary rows — study may still be running.")
        return []

    # filter zero-cost switch (cost=0) for ceiling; also keep cost=C (switch_cost == C)
    rows0 = [r for r in oracle_rows if float(r["switch_cost"]) == 0.0]
    rowsC = [r for r in oracle_rows if float(r["switch_cost"]) > 0.0 and
             abs(float(r["switch_cost"]) - float(r["C"])) < 1.0]

    print(f"\n=== H1: Oracle gain (switch_cost=0: {len(rows0)}, cost=C: {len(rowsC)}) ===")
    groups = {}
    for r in rows0:
        key = (r["family"], r["cap_frac"])
        groups.setdefault(key, []).append(float(r["net_oracle_gain"]))

    h1_rows = []
    for (fam, cap), vals in sorted(groups.items()):
        arr = np.array(vals)
        frac_meet = (arr >= WORTHWHILE_GAIN).mean()
        row = {
            "family": fam, "cap_frac": cap,
            "n_windows": len(arr),
            "mean_gain": f"{arr.mean():.4f}",
            "median_gain": f"{np.median(arr):.4f}",
            "p90_gain": f"{np.quantile(arr, 0.90):.4f}",
            "frac_meet_threshold": f"{frac_meet:.3f}",
            "threshold_met": "yes" if frac_meet >= WORTHWHILE_FRAC else "no",
        }
        h1_rows.append(row)
        print(f"  {fam:30s} cap={cap}: mean={arr.mean():.4f} "
              f"frac≥0.02={frac_meet:.2f} → {'MET' if frac_meet >= WORTHWHILE_FRAC else 'NOT MET'}")

    total = len(h1_rows)
    met = sum(1 for r in h1_rows if r["threshold_met"] == "yes")
    print(f"\n  H1 result: {met}/{total} family-capacity groups met ≥0.02 on ≥2/3 traces")
    return h1_rows


# ── H2: Controller comparison vs S3-FIFO ──────────────────────────────────

def analyze_controllers(ctrl_rows, oracle_rows):
    if not ctrl_rows:
        print("No controller rows.")
        return []

    # Build per-(trace,cap_frac) S3-FIFO miss_ratio from oracle_policy
    pol_rows = load_csv("oracle_policy.csv")
    s3_key = {}
    for r in pol_rows:
        if r["policy"] == "S3-FIFO":
            s3_key[(r["trace"], r["cap_frac"])] = float(r.get("mean_miss_ratio", r.get("miss_ratio", 0)))

    print(f"\n=== H2: Controllers vs S3-FIFO ({len(ctrl_rows)} controller rows) ===")
    ctrl_groups = {}
    for r in ctrl_rows:
        key = r["controller"]
        tk = (r["trace"], r["cap_frac"])
        s3 = s3_key.get(tk)
        if s3 is None:
            continue
        delta = float(r.get("mean_miss_ratio", r.get("miss_ratio", 0))) - s3
        ctrl_groups.setdefault(key, []).append(delta)

    # Wilcoxon + Holm
    pvals_raw = {}
    for ctrl, deltas in sorted(ctrl_groups.items()):
        arr = np.array(deltas)
        if len(arr) < 10:
            continue
        # H0: delta == 0 (two-sided; positive delta means controller loses to S3-FIFO)
        try:
            stat, p = stats.wilcoxon(arr, alternative="two-sided")
        except Exception:
            p = 1.0
        pvals_raw[ctrl] = p

    names = list(pvals_raw.keys())
    raw_p = [pvals_raw[n] for n in names]
    corr_p = holm_correction(raw_p)

    h2_rows = []
    for n, rp, cp in sorted(zip(names, raw_p, corr_p), key=lambda x: x[2]):
        deltas = np.array(ctrl_groups[n])
        h2_rows.append({
            "controller": n,
            "n": len(deltas),
            "mean_delta_vs_s3fifo": f"{deltas.mean():.5f}",
            "median_delta": f"{np.median(deltas):.5f}",
            "pval_wilcoxon": f"{rp:.4f}",
            "pval_holm": f"{cp:.4f}",
            "significant_alpha05": "yes" if cp < 0.05 else "no",
        })
        sign = "SIGNIFICANT" if cp < 0.05 else "ns"
        print(f"  {n:30s} Δ={deltas.mean():.5f}  p_holm={cp:.4f}  {sign}")

    return h2_rows


# ── H3: Unseen-family predictive rule ──────────────────────────────────────

FEATURES = [
    "wss_per_ref", "top1_share", "top10_share", "entropy_bits",
    "reuse_cv", "uniq_window_cv", "window_turnover_mean",
    "window_turnover_max", "window_reuse_cv", "half_unique_diff",
    "prefix20_turnover",
]


def analyze_rule(h1_rows, feat_rows):
    if not h1_rows or not feat_rows:
        print("Missing data for H3.")
        return []

    # Join h1 label onto feature rows (by trace root → family-level label)
    # h1 is by (family, cap_frac); we merge on family (collapsed across cap)
    # label = True if ANY cap_frac group for that family was threshold_met
    fam_met = {}
    for r in h1_rows:
        prev = fam_met.get(r["family"], False)
        fam_met[r["family"]] = prev or (r["threshold_met"] == "yes")

    feat_dict = {r["trace"]: r for r in feat_rows}
    labeled = []
    for trace, feat in feat_dict.items():
        fam = feat.get("family", "")
        if fam not in fam_met:
            continue
        label = 1 if fam_met[fam] else 0
        labeled.append((trace, fam, feat.get("source", ""), label))

    if not labeled:
        print("No labeled feature rows.")
        return []

    families = sorted(set(x[1] for x in labeled))
    print(f"\n=== H3: Unseen-family LOFO rule ({len(labeled)} traces, {len(families)} families) ===")

    # Build matrix
    X_all, y_all, fam_all, src_all = [], [], [], []
    for trace, fam, src, label in labeled:
        feat = feat_dict[trace]
        try:
            row = [float(feat.get(f, 0.0)) for f in FEATURES]
        except (ValueError, TypeError):
            continue
        X_all.append(row)
        y_all.append(label)
        fam_all.append(fam)
        src_all.append(src)

    X_all = np.array(X_all, dtype=np.float64)
    y_all = np.array(y_all, dtype=np.float64)
    fam_all = np.array(fam_all)
    src_all = np.array(src_all)

    def std_fold(Xtr_raw, Xte_raw):
        m = Xtr_raw.mean(0)
        s = Xtr_raw.std(0)
        s[s < 1e-9] = 1.0
        return (np.hstack([np.ones((len(Xtr_raw), 1)), (Xtr_raw - m) / s]),
                np.hstack([np.ones((len(Xte_raw), 1)), (Xte_raw - m) / s]))

    # LOFO (leak-free: standardize inside each fold)
    lofo_preds, lofo_true = [], []
    lofo_rows = []
    for fam in families:
        test_mask = fam_all == fam
        train_mask = ~test_mask
        if train_mask.sum() < 5 or test_mask.sum() < 1:
            continue
        X_tr, X_te = std_fold(X_all[train_mask], X_all[test_mask])
        y_tr, y_te = y_all[train_mask], y_all[test_mask]
        w = fit_logreg(X_tr, y_tr, lam=0.1)
        probs = predict_logreg(w, X_te)
        preds = (probs >= 0.5).astype(float)
        acc = (preds == y_te).mean()
        lofo_preds.extend(probs.tolist())
        lofo_true.extend(y_te.tolist())
        lofo_rows.append({
            "holdout_family": fam,
            "n_test": int(test_mask.sum()),
            "n_train": int(train_mask.sum()),
            "accuracy": f"{acc:.3f}",
            "true_label": int(y_te[0]) if len(y_te) == 1 else "mixed",
        })
        print(f"  LOFO holdout={fam:25s} n_test={test_mask.sum()}  acc={acc:.2f}")

    lofo_true = np.array(lofo_true)
    lofo_preds_arr = np.array(lofo_preds)
    overall_acc = (lofo_preds_arr >= 0.5).astype(float) == lofo_true
    auc = auc_roc(lofo_true, lofo_preds_arr)
    print(f"\n  LOFO overall accuracy: {overall_acc.mean():.3f}  AUC-ROC: {auc:.3f}")

    # Cross-source holdout
    real_mask = src_all == "real_app_pageref"
    pub_mask = ~real_mask
    cs_rows = []
    if real_mask.sum() >= 5 and pub_mask.sum() >= 5:
        for hold_src, hold_mask, train_mask_cs in [
            ("real_app_pageref", real_mask, pub_mask),
            ("public", pub_mask, real_mask),
        ]:
            X_tr, X_te = std_fold(X_all[train_mask_cs], X_all[hold_mask])
            y_tr, y_te = y_all[train_mask_cs], y_all[hold_mask]
            w = fit_logreg(X_tr, y_tr, lam=0.1)
            probs = predict_logreg(w, X_te)
            acc = ((probs >= 0.5).astype(float) == y_te).mean()
            auc_cs = auc_roc(y_te, probs)
            cs_rows.append({
                "holdout_source": hold_src,
                "n_test": int(hold_mask.sum()),
                "n_train": int(train_mask_cs.sum()),
                "accuracy": f"{acc:.3f}",
                "auc": f"{auc_cs:.3f}",
            })
            print(f"  Cross-source holdout={hold_src}: acc={acc:.3f}  AUC={auc_cs:.3f}")

    # Fit global model and report feature weights
    X_global, _ = std_fold(X_all, X_all)
    w_global = fit_logreg(X_global, y_all, lam=0.1)
    feat_weights = []
    for i, fname in enumerate(FEATURES):
        feat_weights.append({"feature": fname, "weight": f"{w_global[i + 1]:.4f}"})
    feat_weights.sort(key=lambda r: abs(float(r["weight"])), reverse=True)
    print("\n  Top feature weights (global model):")
    for fw in feat_weights[:5]:
        print(f"    {fw['feature']:30s}  w={fw['weight']}")

    return lofo_rows, cs_rows, feat_weights, {"lofo_acc": float(overall_acc.mean()), "lofo_auc": float(auc)}


# ── main ───────────────────────────────────────────────────────────────────

def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    oracle_rows = load_csv("oracle_summary.csv")
    ctrl_rows = load_csv("controllers.csv")
    feat_rows = load_csv("features.csv")
    # Fix column references for actual data format
    # oracle has: net_gain_vs_best, net_gain_vs_s3fifo (not net_oracle_gain)
    for r in oracle_rows:
        r.setdefault("net_oracle_gain", r.get("net_gain_vs_best", "0"))
    # ctrl and policy have: miss_ratio (not mean_miss_ratio)
    for r in ctrl_rows:
        r.setdefault("mean_miss_ratio", r.get("miss_ratio", "0"))
    pol_data = load_csv("oracle_policy.csv")
    for r in pol_data:
        r.setdefault("mean_miss_ratio", r.get("miss_ratio", "0"))

    h1_rows = analyze_oracle(oracle_rows)
    h2_rows = analyze_controllers(ctrl_rows, oracle_rows)

    h3_result = analyze_rule(h1_rows, feat_rows)
    lofo_rows, cs_rows, feat_weights, h3_stats = (
        h3_result if h3_result else ([], [], [], {})
    )

    write_csv(RESULTS / "h1_oracle_analysis.csv", h1_rows)
    write_csv(RESULTS / "h2_controller_analysis.csv", h2_rows)
    write_csv(RESULTS / "h3_lofo_analysis.csv", lofo_rows)
    write_csv(RESULTS / "h3_crosssource_analysis.csv", cs_rows)
    write_csv(RESULTS / "h3_feature_weights.csv", feat_weights)

    # Write combined stats for paper
    summary = {
        "n_oracle_rows": len(oracle_rows),
        "n_ctrl_rows": len(ctrl_rows),
        "n_feat_rows": len(feat_rows),
        "h1_groups_met": sum(1 for r in h1_rows if r.get("threshold_met") == "yes"),
        "h1_groups_total": len(h1_rows),
        "h2_controllers_significant": sum(1 for r in h2_rows if r.get("significant_alpha05") == "yes"),
        "h2_controllers_total": len(h2_rows),
        "h3_lofo_acc": h3_stats.get("lofo_acc", ""),
        "h3_lofo_auc": h3_stats.get("lofo_auc", ""),
    }
    write_csv(RESULTS / "analysis_summary.csv", [summary])
    print(f"\n=== ANALYSIS COMPLETE ===")
    print(f"H1: {summary['h1_groups_met']}/{summary['h1_groups_total']} groups met threshold")
    print(f"H2: {summary['h2_controllers_significant']}/{summary['h2_controllers_total']} controllers beat S3-FIFO")
    print(f"H3: LOFO acc={summary['h3_lofo_acc']:.3f}  AUC={summary['h3_lofo_auc']:.3f}" if summary['h3_lofo_acc'] else "H3: insufficient data")


if __name__ == "__main__":
    main()
