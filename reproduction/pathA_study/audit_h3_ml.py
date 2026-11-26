#!/usr/bin/env python3
"""
reproduction/pathA_study/audit_h3_ml.py
Phase 7 audit of Exploratory H3 ML evaluation:
- Exact class counts per split
- Confusion matrices, ROC-AUC, PR-AUC, Balanced Accuracy, Precision, Recall, F1
- Majority-class baseline and single-feature LOFO baselines
"""
import csv
from pathlib import Path
import numpy as np
import scipy.optimize as opt

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "results" / "raw"

FEATS = [
    "wss_per_ref", "top1_share", "top10_share", "entropy_bits",
    "reuse_cv", "uniq_window_cv", "window_turnover_mean",
    "window_turnover_max", "window_reuse_cv", "half_unique_diff",
    "prefix20_turnover",
]


def load_csv(name):
    with open(RAW / name, newline="") as fh:
        return list(csv.DictReader(fh))


def std_fold(Xtr_raw, Xte_raw):
    m, s = Xtr_raw.mean(0), Xtr_raw.std(0)
    s[s < 1e-9] = 1.0
    return (np.hstack([np.ones((len(Xtr_raw), 1)), (Xtr_raw - m) / s]),
            np.hstack([np.ones((len(Xte_raw), 1)), (Xte_raw - m) / s]))


def sig(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -50, 50)))


def fit_lr(Xtr, ytr, lam=0.5):
    def loss(w):
        p = np.clip(sig(Xtr @ w), 1e-10, 1 - 1e-10)
        return -(ytr * np.log(p) + (1 - ytr) * np.log(1 - p)).mean() + 0.5 * lam * (w[1:] ** 2).sum()
    return opt.minimize(loss, np.zeros(Xtr.shape[1]), method="BFGS").x


def calc_roc_auc(yt, ys):
    pos, neg = ys[yt == 1], ys[yt == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    return sum(1.0 if sp > sn else 0.5 if sp == sn else 0.0 for sp in pos for sn in neg) / (len(pos) * len(neg))


def calc_pr_auc(yt, ys):
    if yt.sum() == 0:
        return float("nan")
    order = np.argsort(-ys)
    yt_ord = yt[order]
    tp = np.cumsum(yt_ord)
    prec = tp / np.arange(1, len(yt_ord) + 1)
    # Average precision (step-wise)
    return float((prec * yt_ord).sum() / yt.sum())


def metrics(yt, probs, th=0.5):
    pred = (probs >= th).astype(int)
    tp = int(((pred == 1) & (yt == 1)).sum())
    fp = int(((pred == 1) & (yt == 0)).sum())
    fn = int(((pred == 0) & (yt == 1)).sum())
    tn = int(((pred == 0) & (yt == 0)).sum())
    acc = (tp + tn) / len(yt)
    tpr = tp / max(1, tp + fn)
    tnr = tn / max(1, tn + fp)
    bacc = 0.5 * (tpr + tnr)
    prec = tp / max(1, tp + fp) if (tp + fp) > 0 else 0.0
    rec = tpr
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
    return {
        "n": len(yt), "pos": int(yt.sum()), "neg": int((1 - yt).sum()),
        "TP": tp, "FP": fp, "FN": fn, "TN": tn,
        "acc": acc, "bacc": bacc, "prec": prec, "rec": rec, "f1": f1,
        "roc_auc": calc_roc_auc(yt, probs), "pr_auc": calc_pr_auc(yt, probs),
        "max_prob": float(probs.max()), "mean_prob": float(probs.mean()),
    }


def main():
    ora = load_csv("oracle_summary.csv")
    z_rows = [r for r in ora if float(r["switch_cost"]) == 0]
    feat = {r["trace"]: r for r in load_csv("features.csv")}

    z_max = {}
    for r in z_rows:
        t = r["trace"]
        z_max[t] = max(z_max.get(t, 0.0), float(r["net_gain_vs_best"]))

    traces = sorted(feat.keys())
    X = np.array([[float(feat[t][f]) for f in FEATS] for t in traces])
    y = np.array([1.0 if z_max[t] >= 0.005 else 0.0 for t in traces])
    fams = np.array([feat[t]["family"] for t in traces])
    srcs = np.array([feat[t]["source"] for t in traces])

    # 1. LOFO
    lofo_p, lofo_y = [], []
    for fam in sorted(set(fams)):
        te = fams == fam
        Xtr, Xte = std_fold(X[~te], X[te])
        w = fit_lr(Xtr, y[~te], lam=0.5)
        lofo_p.extend(sig(Xte @ w).tolist())
        lofo_y.extend(y[te].tolist())
    lofo_p = np.array(lofo_p)
    lofo_y = np.array(lofo_y)

    print("=== 1. H3 LOFO (lam=0.5, th=0.5) ===")
    print(metrics(lofo_y, lofo_p))

    # Majority baseline
    maj_acc = max(y.mean(), 1 - y.mean())
    print(f"Majority-class baseline: acc={maj_acc:.3f}, bal_acc=0.500, pr_auc_chance={y.mean():.3f}")

    # 2. Cross-source
    print("\n=== 2. Cross-Source Holdouts ===")
    for name, te in [("Real-app holdout (train on public)", srcs == "real_app_pageref"),
                     ("Public holdout (train on real-app)", srcs != "real_app_pageref")]:
        Xtr, Xte = std_fold(X[~te], X[te])
        w = fit_lr(Xtr, y[~te], lam=0.5)
        p = sig(Xte @ w)
        print(name, "->", metrics(y[te], p))

    # 3. Single-feature LOFO baselines
    print("\n=== 3. Single-Feature LOFO Baselines ===")
    for j, fname in enumerate(FEATS):
        sp, sy = [], []
        for fam in sorted(set(fams)):
            te = fams == fam
            Xtr, Xte = std_fold(X[~te, j:j+1], X[te, j:j+1])
            w = fit_lr(Xtr, y[~te], lam=0.5)
            sp.extend(sig(Xte @ w).tolist())
            sy.extend(y[te].tolist())
        m = metrics(np.array(sy), np.array(sp))
        print(f"  {fname:24s} ROC-AUC={m['roc_auc']:.3f} PR-AUC={m['pr_auc']:.3f} BalAcc={m['bacc']:.3f} F1={m['f1']:.3f}")


if __name__ == "__main__":
    main()
