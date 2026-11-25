#!/usr/bin/env python3
"""Aggregate pre-registered Phase 6 PDL runs; all numbers come from raw CSVs."""
import csv
import os
from collections import defaultdict

import numpy as np
from scipy.stats import wilcoxon

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
B = 10_000
SEED = 20261125


def read_rows():
    rows = []
    for fn in sorted(os.listdir(RAW)):
        if not fn.endswith(".csv") or fn.endswith("_det.csv") or fn == "commands.csv":
            continue
        base = fn[:-4]
        family, cstr = base.rsplit("_C", 1)
        with open(os.path.join(RAW, fn), newline="") as fh:
            for r in csv.DictReader(fh):
                rows.append({
                    "family": family,
                    "C": int(cstr),
                    "method": r["method"],
                    "miss": float(r["miss_ratio"]),
                    "switches": float(r["switches"]),
                    "evals": float(r["shadow_evals"]),
                    "ns": float(r["ns_per_ref"]),
                })
    return rows


def write_csv(path, fields, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def holm(pvals):
    names = list(pvals)
    order = sorted(names, key=lambda k: pvals[k])
    m = len(order)
    adj = {}
    running = 0.0
    for i, name in enumerate(order):
        val = (m - i) * pvals[name]
        running = max(running, val)
        adj[name] = min(1.0, running)
    return adj


def main():
    rows = read_rows()
    if not rows:
        raise SystemExit("no raw Phase 6 CSVs found")
    methods = sorted({r["method"] for r in rows})
    points = sorted({(r["family"], r["C"]) for r in rows})
    lookup = {(r["family"], r["C"], r["method"]): r for r in rows}

    summary = []
    for m in methods:
        rs = [r for r in rows if r["method"] == m]
        summary.append({
            "method": m, "n": len(rs),
            "mean_miss": float(np.mean([r["miss"] for r in rs])),
            "mean_switches": float(np.mean([r["switches"] for r in rs])),
            "mean_shadow_evals": float(np.mean([r["evals"] for r in rs])),
            "mean_ns_per_ref": float(np.mean([r["ns"] for r in rs])),
        })
    write_csv(os.path.join(HERE, "summary.csv"),
              ["method", "n", "mean_miss", "mean_switches", "mean_shadow_evals", "mean_ns_per_ref"], summary)

    per_family = []
    for fam in sorted({r["family"] for r in rows}):
        for m in methods:
            rs = [r for r in rows if r["family"] == fam and r["method"] == m]
            per_family.append({"family": fam, "method": m, "n": len(rs),
                               "mean_miss": float(np.mean([r["miss"] for r in rs]))})
    write_csv(os.path.join(HERE, "per_family.csv"),
              ["family", "method", "n", "mean_miss"], per_family)

    rng = np.random.default_rng(SEED)
    families = sorted({f for f, _ in points})
    fam_points = {f: [p for p in points if p[0] == f] for f in families}
    all_points = [p for f in families for p in fam_points[f]]
    baselines = [m for m in methods if m not in {"DA", "ContShadow"}]
    raw_p = {}
    out = []
    for base in baselines:
        diff = np.array([lookup[(f, c, "DA")]["miss"] - lookup[(f, c, base)]["miss"] for f, c in all_points])
        idx = np.arange(len(diff))
        boots = []
        for _ in range(B):
            s = rng.choice(idx, size=len(idx), replace=True)
            boots.append(diff[s].mean())
        cluster = []
        for _ in range(B):
            sf = rng.choice(len(families), size=len(families), replace=True)
            vals = [diff[all_points.index(p)] for f_i in sf for p in fam_points[families[f_i]]]
            cluster.append(float(np.mean(vals)))
        try:
            p = float(wilcoxon(diff, zero_method="wilcox", alternative="two-sided").pvalue)
        except ValueError:
            p = 1.0
        raw_p[base] = p
        out.append({
            "baseline": base, "n": len(diff), "mean_diff": float(diff.mean()),
            "boot_ci_low": float(np.percentile(boots, 2.5)),
            "boot_ci_high": float(np.percentile(boots, 97.5)),
            "cluster_ci_low": float(np.percentile(cluster, 2.5)),
            "cluster_ci_high": float(np.percentile(cluster, 97.5)),
            "wilcoxon_p": p, "n_positive": int((diff > 0).sum()),
            "n_zero": int((diff == 0).sum()), "n_negative": int((diff < 0).sum()),
        })
    adj = holm(raw_p)
    for r in out:
        r["holm_p"] = adj[r["baseline"]]
    write_csv(os.path.join(HERE, "paired_da_minus_baseline.csv"),
              ["baseline", "n", "mean_diff", "boot_ci_low", "boot_ci_high",
               "cluster_ci_low", "cluster_ci_high", "wilcoxon_p", "holm_p",
               "n_positive", "n_zero", "n_negative"], out)
    print(f"aggregated {len(rows)} method rows from {len(points)} trace-capacity points")


if __name__ == "__main__":
    main()
