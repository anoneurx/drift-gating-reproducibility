#!/usr/bin/env python3
"""Generate all LaTeX tables, figures, and exploratory H3 stats directly from Path A CSVs."""
import csv
from collections import Counter
from pathlib import Path
import numpy as np
import scipy.optimize as opt
import scipy.stats as stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
ROOT = HERE.parent.parent
TEX_DIR = ROOT / "drift_gating_latex_source"
FIG_DIR = TEX_DIR / "figs"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def load_csv(name):
    with open(RESULTS / name, newline="") as fh:
        return list(csv.DictReader(fh))


def holm_correction(pvals):
    n = len(pvals)
    indexed = sorted(enumerate(pvals), key=lambda x: x[1])
    corrected = [0.0] * n
    for rank, (orig_i, p) in enumerate(indexed):
        corrected[orig_i] = min(1.0, p * (n - rank))
    order = [i for i, _ in sorted(enumerate(pvals), key=lambda x: x[1])]
    mx = 0.0
    for i in order:
        corrected[i] = max(corrected[i], mx)
        mx = corrected[i]
    return corrected


def tex_esc(s):
    return s.replace("_", r"\_")


def main():
    manifest = load_csv("manifest.csv")
    ora = load_csv("oracle_summary.csv")
    w100 = load_csv("oracle_summary_w100000.csv")
    pol = load_csv("oracle_policy.csv")
    ctrl = load_csv("controllers.csv")
    feat = {r["trace"]: r for r in load_csv("features.csv")}
    csweep = load_csv("cost_sweep.csv")
    cdiag = load_csv("ctrl_diag.csv")

    c_rows = [r for r in ora if float(r["switch_cost"]) > 0]
    z_rows = [r for r in ora if float(r["switch_cost"]) == 0]
    w100_c = [r for r in w100 if float(r["switch_cost"]) > 0]
    w100_z = [r for r in w100 if float(r["switch_cost"]) == 0]

    # ── 1. Table: Corpus Summary ───────────────────────────────────────────
    src_labels = {
        "real_app_pageref": "Real-app page traces (SQLite, git, Python)",
        "instrumented_program": "Instrumented programs (15 kernels)",
        "fiu_public": "Public FIU block-I/O traces",
        "pdl_public": "Public PDL cache/storage traces",
    }
    lines = [
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Source & Families & Traces & Refs (mean) & WSS (median) \\",
        r"\midrule",
    ]
    for src in ("real_app_pageref", "instrumented_program", "fiu_public", "pdl_public"):
        sub = [m for m in manifest if m["source"] == src]
        fams = len(set(m["family"] for m in sub))
        refs_m = np.mean([int(m["refs"]) for m in sub]) / 1e6
        wss_med = np.median([int(m["wss"]) for m in sub])
        lines.append(f"{src_labels[src]} & {fams} & {len(sub)} & {refs_m:.2f}M & {wss_med:,.0f} \\\\")
    lines += [
        r"\midrule",
        f"Total & {len(set(m['family'] for m in manifest))} & {len(manifest)} & "
        f"{np.mean([int(m['refs']) for m in manifest])/1e6:.2f}M & "
        f"{np.median([int(m['wss']) for m in manifest]):,.0f} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
    ]
    (TEX_DIR / "table_sources.tex").write_text("\n".join(lines) + "\n")

    # ── 2. Table: H1 Oracle Ceiling by Source & Window ─────────────────────
    lines = [
        r"\begin{tabular}{llrrrrr}",
        r"\toprule",
        r"Source & Cost & $n$ & Mean $g$ & $p_{90}$ $g$ & Max $g$ & $\ge 0.02$ \\",
        r"\midrule",
    ]
    for src, sname in [
        ("real_app_pageref", "Real-app"),
        ("instrumented_program", "Prog."),
        ("fiu_public", "FIU"),
        ("pdl_public", "PDL"),
    ]:
        for tag, pool in [("$c=C$", c_rows), ("$c=0$", z_rows)]:
            vals = np.array([float(r["net_gain_vs_best"]) for r in pool if r["source"] == src])
            cnt = int((vals >= 0.02).sum())
            lines.append(
                f"{sname} & {tag} & {len(vals)} & {vals.mean():.4f} & "
                f"{np.quantile(vals, 0.9):.4f} & {vals.max():.4f} & {cnt}/{len(vals)} \\\\"
            )
    lines.append(r"\midrule")
    for label, pool in [("All ($W=50$k, $c=C$)", c_rows),
                        ("All ($W=100$k, $c=C$)", w100_c),
                        ("All ($W=50$k, $c=0$)", z_rows),
                        ("All ($W=100$k, $c=0$)", w100_z)]:
        vals = np.array([float(r["net_gain_vs_best"]) for r in pool])
        cnt = int((vals >= 0.02).sum())
        lines.append(
            f"\\multicolumn{{2}}{{l}}{{{label}}} & {len(vals)} & {vals.mean():.4f} & "
            f"{np.quantile(vals, 0.9):.4f} & {vals.max():.4f} & {cnt}/{len(vals)} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TEX_DIR / "table_h1.tex").write_text("\n".join(lines) + "\n")

    # ── 3. Table: Static Policies Summary ──────────────────────────────────
    best_counts = Counter(r["best_static"] for r in c_rows)
    pol_mr, pol_ns = {}, {}
    for r in pol:
        pol_mr.setdefault(r["policy"], []).append(float(r["miss_ratio"]))
        pol_ns.setdefault(r["policy"], []).append(float(r["ns_per_ref"]))
    ranked_pols = sorted(pol_mr.keys(), key=lambda p: np.mean(pol_mr[p]))

    lines = [
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Policy & Mean MR & Med. MR & Best (\#/264) & ns/ref \\",
        r"\midrule",
    ]
    for p in ranked_pols:
        mr = np.array(pol_mr[p])
        ns = np.mean(pol_ns[p])
        lines.append(f"{tex_esc(p)} & {mr.mean():.4f} & {np.median(mr):.4f} & {best_counts[p]} & {ns:.1f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TEX_DIR / "table_policies.tex").write_text("\n".join(lines) + "\n")

    # ── 4. Table: H2 Controllers vs S3-FIFO (2-sided Wilcoxon + Cluster CI) ──
    s3_mr = {(r["trace"], r["cap_frac"]): float(r["miss_ratio"]) for r in pol if r["policy"] == "S3-FIFO"}
    s3_ns_mean = np.mean([float(r["ns_per_ref"]) for r in pol if r["policy"] == "S3-FIFO"])
    s3_mr_mean = np.mean(list(s3_mr.values()))

    rng = np.random.default_rng(42)
    fams_list = sorted(set(r["family"] for r in ctrl))

    ctrl_names = sorted(set(r["controller"] for r in ctrl) - {"S3-FIFO"})
    raw_p = []
    ctrl_stats = []
    for cname in ctrl_names:
        sub = [r for r in ctrl if r["controller"] == cname]
        deltas = np.array([float(r["miss_ratio"]) - s3_mr[(r["trace"], r["cap_frac"])] for r in sub])
        fam_arrs = [np.array([float(r["miss_ratio"]) - s3_mr[(r["trace"], r["cap_frac"])] for r in sub if r["family"] == f]) for f in fams_list]
        boots = [np.concatenate([fam_arrs[i] for i in rng.integers(0, len(fams_list), size=len(fams_list))]).mean() for _ in range(3000)]
        ci_lo, ci_hi = np.quantile(boots, 0.025), np.quantile(boots, 0.975)
        sw = np.mean([float(r["switches"]) for r in sub])
        ev = np.mean([float(r["shadow_evals"]) for r in sub])
        ns = np.mean([float(r["ns_per_ref"]) for r in sub])
        try:
            _, p = stats.wilcoxon(deltas, alternative="two-sided")
            if np.isnan(p):
                p = 1.0
        except Exception:
            p = 1.0
        raw_p.append(p)
        ctrl_stats.append((cname, len(deltas), deltas.mean(), ci_lo, ci_hi, sw, ev, ns))
    holm_p = holm_correction(raw_p)

    lines = [
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Controller & $\Delta$ MR [95\% Cluster CI] & $p_{\text{Holm}}$ & Sw. & Evals & ns/ref \\",
        r"\midrule",
        f"S3-FIFO (static) & 0.0000 [---] & --- & 0.00 & 0.0 & {s3_ns_mean:.1f} \\\\",
        r"\midrule",
    ]
    for (cname, n, dmean, clo, chi, sw, ev, ns), cp in sorted(zip(ctrl_stats, holm_p), key=lambda x: x[0][2]):
        pstr = "$<10^{-15}$" if cp < 1e-15 else f"{cp:.3f}"
        lines.append(f"{tex_esc(cname)} & {dmean:+.4f} [{clo:+.3f}, {chi:+.3f}] & {pstr} & {sw:.2f} & {ev:.1f} & {ns:.1f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TEX_DIR / "table_h2.tex").write_text("\n".join(lines) + "\n")

    # ── 5. Exploratory H3 LOFO & Cross-Source Rule ─────────────────────────
    z_max = {}
    for r in z_rows:
        t = r["trace"]
        z_max[t] = max(z_max.get(t, 0.0), float(r["net_gain_vs_best"]))

    FEATS = [
        "wss_per_ref", "top1_share", "top10_share", "entropy_bits",
        "reuse_cv", "uniq_window_cv", "window_turnover_mean",
        "window_turnover_max", "window_reuse_cv", "half_unique_diff",
        "prefix20_turnover",
    ]
    traces = sorted(feat.keys())
    X = np.array([[float(feat[t][f]) for f in FEATS] for t in traces])
    y_bin = np.array([1.0 if z_max[t] >= 0.005 else 0.0 for t in traces])
    fams = np.array([feat[t]["family"] for t in traces])
    srcs = np.array([feat[t]["source"] for t in traces])

    mu, sd = X.mean(0), X.std(0)
    sd[sd < 1e-9] = 1.0
    Xn = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])

    def sig(z):
        return 1.0 / (1.0 + np.exp(-np.clip(z, -50, 50)))

    def fit_lr(Xtr, ytr, lam=0.5):
        def loss(w):
            p = np.clip(sig(Xtr @ w), 1e-10, 1 - 1e-10)
            return -(ytr * np.log(p) + (1 - ytr) * np.log(1 - p)).mean() + 0.5 * lam * (w[1:] ** 2).sum()
        return opt.minimize(loss, np.zeros(Xtr.shape[1]), method="BFGS").x

    lofo_preds, lofo_true = [], []
    for fam in sorted(set(fams)):
        te = fams == fam
        w = fit_lr(Xn[~te], y_bin[~te], lam=0.5)
        lofo_preds.extend(sig(Xn[te] @ w).tolist())
        lofo_true.extend(y_bin[te].tolist())
    lofo_preds = np.array(lofo_preds)
    lofo_true = np.array(lofo_true)
    lofo_acc = ((lofo_preds >= 0.5) == lofo_true).mean()
    tp = ((lofo_preds >= 0.5) & (lofo_true == 1)).sum()
    tn = ((lofo_preds < 0.5) & (lofo_true == 0)).sum()
    fp = ((lofo_preds >= 0.5) & (lofo_true == 0)).sum()
    fn = ((lofo_preds < 0.5) & (lofo_true == 1)).sum()
    lofo_bacc = 0.5 * (tp / max(1, tp + fn) + tn / max(1, tn + fp))
    lofo_f1 = (2 * tp) / max(1, 2 * tp + fp + fn)

    def calc_auc(yt, ys):
        pos, neg = ys[yt == 1], ys[yt == 0]
        return sum(1.0 if sp > sn else 0.5 if sp == sn else 0.0 for sp in pos for sn in neg) / (len(pos) * len(neg))

    lofo_auc = calc_auc(lofo_true, lofo_preds)

    cs_rows = []
    for name, te in [("Real-app holdout (train on public)", srcs == "real_app_pageref"),
                     ("Public holdout (train on real-app)", srcs != "real_app_pageref")]:
        w = fit_lr(Xn[~te], y_bin[~te], lam=0.5)
        p = sig(Xn[te] @ w)
        yt = y_bin[te]
        tp_c = ((p >= 0.5) & (yt == 1)).sum(); tn_c = ((p < 0.5) & (yt == 0)).sum()
        fp_c = ((p >= 0.5) & (yt == 0)).sum(); fn_c = ((p < 0.5) & (yt == 1)).sum()
        bacc_c = 0.5 * (tp_c / max(1, tp_c + fn_c) + tn_c / max(1, tn_c + fp_c))
        cs_rows.append((name, int(te.sum()), int((~te).sum()), bacc_c, calc_auc(yt, p)))

    wg = fit_lr(Xn, y_bin, lam=0.5)
    weights = sorted(zip(FEATS, wg[1:]), key=lambda x: abs(x[1]), reverse=True)

    # Save exploratory CSVs
    with open(RESULTS / "h3_exploratory_weights.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["feature", "weight"])
        for f, val in weights:
            w.writerow([f, f"{val:.4f}"])

    lines = [
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Evaluation split & $n_{\text{test}}$ & $n_{\text{train}}$ & Bal.\ Acc. & AUC \\",
        r"\midrule",
        r"Primary ($c=C, g \ge 0.02$) & 88 & --- & 0.500 & --- \\",
        f"Expl.\\ LOFO ($c=0, g \\ge 0.005$) & 88 & --- & {lofo_bacc:.3f} & {lofo_auc:.3f} \\\\",
    ]
    for name, nte, ntr, bacc, auc in cs_rows:
        lines.append(f"{name} & {nte} & {ntr} & {bacc:.3f} & {auc:.3f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TEX_DIR / "table_h3.tex").write_text("\n".join(lines) + "\n")
    print(f"H3 LOFO raw_acc={lofo_acc:.3f}, bal_acc={lofo_bacc:.3f}, f1={lofo_f1:.3f}, auc={lofo_auc:.3f}")

    lines = [
        r"\begin{tabular}{lr}",
        r"\toprule",
        r"Standardized feature & Weight \\",
        r"\midrule",
    ]
    for f, val in weights:
        lines.append(f"{tex_esc(f)} & {val:+.4f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TEX_DIR / "table_feat_weights.tex").write_text("\n".join(lines) + "\n")

    # ── 6. Supplement Full 30-Family Table ─────────────────────────────────
    fam_groups = {}
    for r in c_rows:
        fam_groups.setdefault((r["family"], r["cap_frac"]), []).append(float(r["net_gain_vs_best"]))
    fam_z = {}
    for r in z_rows:
        fam_z.setdefault((r["family"], r["cap_frac"]), []).append(float(r["net_gain_vs_best"]))

    lines = [
        r"\begin{tabular}{lcrrrr}",
        r"\toprule",
        r"Family & Cap & $n$ & Mean $g$ ($c=C$) & Mean $g$ ($c=0$) & Frac$\ge 0.02$ ($c=C$) \\",
        r"\midrule",
    ]
    for (fam, cap), vals in sorted(fam_groups.items()):
        arr = np.array(vals)
        zarr = np.array(fam_z[(fam, cap)])
        frac = (arr >= 0.02).mean()
        lines.append(f"{tex_esc(fam)} & {cap} & {len(arr)} & {arr.mean():.4f} & {zarr.mean():.4f} & {frac:.2f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TEX_DIR / "table_all_families.tex").write_text("\n".join(lines) + "\n")

    # ── 7. Figures ─────────────────────────────────────────────────────────
    plt.rcParams.update({"font.size": 8, "axes.labelsize": 8, "axes.titlesize": 9})

    # Fig 1: Oracle gain distribution (cost=C vs cost=0)
    fig, ax = plt.subplots(figsize=(4.4, 2.4))
    srcs_order = ["real_app_pageref", "fiu_public", "pdl_public", "instrumented_program"]
    short = ["Real-app", "FIU", "PDL", "Prog."]
    pos = np.arange(len(srcs_order))
    c_means = [np.max([float(r["net_gain_vs_best"]) for r in c_rows if r["source"] == s]) for s in srcs_order]
    z_means = [np.max([float(r["net_gain_vs_best"]) for r in z_rows if r["source"] == s]) for s in srcs_order]
    c_avg = [np.mean([float(r["net_gain_vs_best"]) for r in c_rows if r["source"] == s]) for s in srcs_order]
    z_avg = [np.mean([float(r["net_gain_vs_best"]) for r in z_rows if r["source"] == s]) for s in srcs_order]
    w_bar = 0.35
    ax.bar(pos - w_bar/2, c_avg, w_bar, label="Mean (c=C)", color="#2b5c8f")
    ax.bar(pos + w_bar/2, z_avg, w_bar, label="Mean (c=0)", color="#7aa6d6")
    ax.scatter(pos - w_bar/2, c_means, marker="^", s=28, color="#b22222", zorder=5, label="Max (c=C)")
    ax.scatter(pos + w_bar/2, z_means, marker="o", s=24, color="#d97706", zorder=5, label="Max (c=0)")
    ax.axhline(0.02, color="#b22222", linestyle="--", linewidth=1.0, label="Worthwhile threshold (0.02)")
    ax.set_xticks(pos)
    ax.set_xticklabels(short)
    ax.set_ylabel("Net oracle gain vs. best static")
    ax.set_ylim(-0.002, 0.088)
    ax.legend(fontsize=6.5, ncol=2, frameon=False, loc="upper right")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_oracle_ceiling.pdf")
    plt.close(fig)

    # Fig 2: Pareto frontier (Miss ratio vs CPU ns/ref)
    fig, ax = plt.subplots(figsize=(4.4, 2.5))
    key_pols = ["S3-FIFO", "CAR", "ARC", "2Q", "W-TinyLFU", "LRU", "CLOCK", "SIEVE"]
    px = [np.mean(pol_ns[p]) for p in key_pols]
    py = [np.mean(pol_mr[p]) for p in key_pols]
    ax.scatter(px, py, s=40, color="#1f77b4", marker="s", label="Static policies", zorder=4)
    for p, x, y in zip(key_pols, px, py):
        dy = -0.0035 if p in ("S3-FIFO", "CAR", "LRU") else 0.002
        ax.annotate(p, (x, y), xytext=(x + 2, y + dy), fontsize=6.5)

    cx = [s[7] for s in ctrl_stats]
    cy = [s3_mr_mean + s[2] for s in ctrl_stats]
    ax.scatter(cx, cy, s=26, color="#d62728", marker="o", alpha=0.85, label="Switching controllers (17)", zorder=3)
    ax.annotate("ContShadow", (cx[ctrl_names.index("ContShadow")], cy[ctrl_names.index("ContShadow")]),
                xytext=(142, 0.534), arrowprops=dict(arrowstyle="-", color="#d62728", lw=0.6), fontsize=6.5, color="#d62728")
    ax.annotate("CUSUM-high", (cx[ctrl_names.index("CUSUM-high")], cy[ctrl_names.index("CUSUM-high")]),
                xytext=(114, 0.525), fontsize=6.5, color="#d62728")
    ax.set_xlabel("Simulator CPU cost (ns / reference)")
    ax.set_ylabel("Mean miss ratio (264 trace-cap pairs)")
    ax.set_xlim(20, 240)
    ax.set_ylim(0.480, 0.542)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_controllers_vs_s3fifo.pdf")
    plt.close(fig)

    # Fig 3: Exploratory LOFO ROC curve
    ths = np.linspace(0, 1, 200)
    tprs, fprs = [], []
    for th in ths:
        tp = ((lofo_preds >= th) & (lofo_true == 1)).sum()
        fp = ((lofo_preds >= th) & (lofo_true == 0)).sum()
        fn = ((lofo_preds < th) & (lofo_true == 1)).sum()
        tn = ((lofo_preds < th) & (lofo_true == 0)).sum()
        tprs.append(tp / max(1, tp + fn))
        fprs.append(fp / max(1, fp + tn))
    fig, ax = plt.subplots(figsize=(4.0, 2.5))
    ax.plot(fprs, tprs, color="#2b5c8f", linewidth=1.8, label=f"LOFO logistic (AUC = {lofo_auc:.3f})")
    ax.plot([0, 1], [0, 1], "k--", linewidth=0.9, label="Chance (AUC = 0.500)")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("Exploratory LOFO ROC (g(0) >= 0.005)", fontsize=8)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_lofo_roc.pdf")
    plt.close(fig)

    print("Generated all tables and figures successfully.")
    print(f"LOFO exploratory: acc={lofo_acc:.3f}, auc={lofo_auc:.3f}")


    # ── 8. Table: Fine Switch-Cost x Window Sensitivity (from finesweep.csv) ──
    fsw = load_csv("finesweep.csv")
    fsw_low = [r for r in fsw if float(r["cap_frac"]) <= 0.10]
    lines = [
        r"\begin{tabular}{llrrrrrrr}",
        r"\toprule",
        r"$W$ & $c_{\text{sw}}$ & Mean $g$ & Max $g$ & $\ge .005$ & $\ge .01$ & $\ge .02$ & Sw. \\",
        r"\midrule",
    ]
    for w in (5000, 10000, 25000, 50000):
        for cf in ("0.00", "0.02", "0.05", "0.10", "0.25", "0.50", "1.00"):
            sub = [r for r in fsw_low if int(r["window"]) == w and r["cost_frac"] == cf]
            g = np.array([float(r["net_gain_vs_best"]) for r in sub])
            sw = np.mean([float(r["oracle_switches"]) for r in sub])
            clabel = "$0$" if cf == "0.00" else (f"${cf}C$" if cf != "1.00" else "$C$")
            lines.append(
                f"{w//1000}k & {clabel} & {g.mean():.4f} & {g.max():.5f} & "
                f"{int((g>=0.005).sum())} & {int((g>=0.01).sum())} & {int((g>=0.02).sum())} & {sw:.2f} \\\\"
            )
        if w != 50000:
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TEX_DIR / "table_cost_sweep.tex").write_text("\n".join(lines) + "\n")

    # ── 9. Table: Controller Failure-Mode Time-Shares ──────────────────────
    lines = [
        r"\begin{tabular}{lrrrrrrr}",
        r"\toprule",
        r"Controller / Source & $\Delta$ MR & S3-FIFO & LRU & 2Q & ARC & LFU-A & MRU \\",
        r"\midrule",
    ]
    for cname in ("ContShadow", "CUSUM-med", "OracleTrig"):
        sub = [r for r in cdiag if r["controller"] == cname]
        dm = np.mean([float(r["miss_ratio"]) - float(r["s3fifo_miss_ratio"]) for r in sub])
        sh = [np.mean([float(r[k]) for r in sub]) for k in ("s3fifo_frac","lru_frac","q2_frac","arc_frac","lfua_frac","mru_frac")]
        lines.append(f"{cname} (all) & {dm:+.4f} & " + " & ".join(f"{x:.3f}" for x in sh) + r" \\")
    lines.append(r"\midrule")
    for src, sname in [("real_app_pageref", "Real-app"), ("fiu_public", "FIU"),
                       ("pdl_public", "PDL"), ("instrumented_program", "Prog.")]:
        sub = [r for r in cdiag if r["controller"] == "ContShadow" and r["source"] == src]
        dm = np.mean([float(r["miss_ratio"]) - float(r["s3fifo_miss_ratio"]) for r in sub])
        sh = [np.mean([float(r[k]) for r in sub]) for k in ("s3fifo_frac","lru_frac","q2_frac","arc_frac","lfua_frac","mru_frac")]
        lines.append(f"ContShadow ({sname}) & {dm:+.4f} & " + " & ".join(f"{x:.3f}" for x in sh) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TEX_DIR / "table_ctrl_diag.tex").write_text("\n".join(lines) + "\n")

    # ── 10. Fig 4: Fine Switch-Cost x Window Sensitivity Curve ─────────────
    fig, ax = plt.subplots(figsize=(4.6, 2.5))
    cfs = [0.00, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50, 1.00]
    for w, col, mk in [(5000, "#9467bd", "D"), (10000, "#d62728", "o"), (25000, "#1f77b4", "s"), (50000, "#2ca02c", "^")]:
        pcts = []
        for cf in cfs:
            sub = [r for r in fsw_low if int(r["window"]) == w and abs(float(r["cost_frac"]) - cf) < 1e-4]
            pcts.append(100.0 * np.mean([float(r["net_gain_vs_best"]) >= 0.02 for r in sub]))
        ax.plot(cfs, pcts, marker=mk, ms=3.8, linewidth=1.5, color=col, label=f"W = {w//1000}k refs")
    ax.axvline(0.50, color="#555555", linestyle="--", linewidth=1.0, label="0.50C zero-clearing point")
    ax.set_xlabel("Switch penalty fraction (c_switch / C)")
    ax.set_ylabel("Pairs clearing >= 0.02 (%)")
    ax.set_xticks([0.00, 0.10, 0.20, 0.25, 0.50, 1.00])
    ax.set_xticklabels(["0", "0.10C", "0.20C", "0.25C", "0.50C", "1.00C"], fontsize=7)
    ax.set_ylim(-0.3, 8.6)
    ax.legend(fontsize=6.5, frameon=False, loc="upper right")
    ax.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_cost_sweep.pdf")
    plt.close(fig)

    # ── 11. Fig 5b: Shadow Ranking Accuracy (from shadow_ranking.csv) ──────
    sr = load_csv("shadow_ranking.csv")
    modes = ["ContShadow-0.2C", "FullShadow-1.0C"]
    metrics = []
    for m in modes:
        sub = [r for r in sr if r["mode"] == m]
        tot_ev = sum(int(r["evals"]) for r in sub)
        top1 = 100.0 * sum(int(r["top1_agree"]) for r in sub) / tot_ev
        sh_s3 = 100.0 * sum(int(r["shadow_picks_s3"]) for r in sub) / tot_ev
        tr_s3 = 100.0 * sum(int(r["true_best_s3"]) for r in sub) / tot_ev
        metrics.append((top1, sh_s3, tr_s3))

    fig, ax = plt.subplots(figsize=(4.2, 2.3))
    x = np.arange(3)
    w_b = 0.32
    ax.bar(x - w_b/2, metrics[0], w_b, label="ContShadow-0.2C (sampled)", color="#d62728")
    ax.bar(x + w_b/2, metrics[1], w_b, label="FullShadow-1.0C (cold 20k)", color="#1f77b4")
    for i, (v0, v1) in enumerate(zip(metrics[0], metrics[1])):
        ax.text(i - w_b/2, v0 + 1.5, f"{v0:.1f}%", ha="center", fontsize=6.5)
        ax.text(i + w_b/2, v1 + 1.5, f"{v1:.1f}%", ha="center", fontsize=6.5)
    ax.set_xticks(x)
    ax.set_xticklabels(["Top-1 policy\nagreement", "Shadow picks\nS3-FIFO", "True window\nbest is S3-FIFO"], fontsize=7)
    ax.set_ylabel("Share of eval windows (%)")
    ax.set_ylim(0, 84)
    ax.legend(fontsize=6.5, frameon=False, loc="upper right")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_shadow_ranking.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main()
