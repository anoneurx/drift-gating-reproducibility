#!/usr/bin/env python3
"""Aggregate the Path A oracle results and apply the pre-specified decision rule."""
import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
THRESHOLD = 0.02
FRACTION_REQUIRED = 2.0 / 3.0
BOOT_SEED = 20261125
BOOT_B = 10000

FIELDS = [
    "family", "source", "C", "window", "n_traces", "mean_best_static_miss",
    "mean_oracle_miss", "mean_gain_miss_abs", "median_gain_miss_abs",
    "max_gain_miss_abs", "ci_low", "ci_high", "frac_gain_ge_0.02",
    "mean_gain_objective_abs", "mean_oracle_switches", "frac_best_s3_fifo",
    "threshold_met",
]


def load(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def bootstrap_ci(vals, rng):
    if len(vals) < 2:
        return (vals[0] if vals else 0.0, vals[0] if vals else 0.0)
    means = np.empty(BOOT_B)
    n = len(vals)
    for i in range(BOOT_B):
        means[i] = vals[rng.integers(0, n, n)].mean()
    return (float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975)))


def aggregate(rows, charged_only=True):
    groups = defaultdict(list)
    for r in rows:
        cost = float(r["switch_cost"])
        if charged_only and cost <= 0:
            continue
        if not charged_only and cost > 0:
            continue
        key = (r["family"], r["source"], int(r["C"]), int(r["window"]))
        groups[key].append(r)
    rng = np.random.default_rng(BOOT_SEED)
    out = []
    for key, rs in sorted(groups.items()):
        family, source, cap, window = key
        gains = np.array([float(r["gain_miss_abs"]) for r in rs])
        obj = np.array([float(r["gain_objective_abs"]) for r in rs])
        lo, hi = bootstrap_ci(gains, rng)
        frac = float(np.mean(gains >= THRESHOLD))
        out.append({
            "family": family, "source": source, "C": cap, "window": window,
            "n_traces": len(rs),
            "mean_best_static_miss": float(np.mean([float(r["best_static_miss_ratio"]) for r in rs])),
            "mean_oracle_miss": float(np.mean([float(r["oracle_miss_ratio"]) for r in rs])),
            "mean_gain_miss_abs": float(gains.mean()),
            "median_gain_miss_abs": float(np.median(gains)),
            "max_gain_miss_abs": float(gains.max()),
            "ci_low": lo, "ci_high": hi,
            "frac_gain_ge_0.02": frac,
            "mean_gain_objective_abs": float(obj.mean()),
            "mean_oracle_switches": float(np.mean([float(r["oracle_switches"]) for r in rs])),
            "frac_best_s3_fifo": float(np.mean([r["best_static"] == "S3-FIFO" for r in rs])),
            "threshold_met": bool(frac >= FRACTION_REQUIRED and gains.mean() >= THRESHOLD),
        })
    return out


def write(path, fields, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default=str(RESULTS / "summary.csv"))
    ap.add_argument("--results-dir", default=str(RESULTS))
    args = ap.parse_args()
    rdir = Path(args.results_dir)
    rows = load(args.summary if args.summary != str(RESULTS / "summary.csv")
                else str(rdir / "summary.csv"))
    charged = aggregate(rows, True)
    bound = aggregate(rows, False)
    write(rdir / "aggregate_family.csv", FIELDS, charged)
    write(rdir / "aggregate_zero_cost_bound.csv", FIELDS, bound)

    met = [r for r in charged if r["threshold_met"]]
    zero_met = [r for r in bound if r["threshold_met"]]
    decision = {
        "n_groups": len(charged),
        "n_groups_threshold_met": len(met),
        "n_zero_cost_groups_threshold_met": len(zero_met),
        "decision": "PATH_B_GATE" if met else "PATH_A_DECISIVE_NEGATIVE",
        "threshold": THRESHOLD,
        "fraction_required": FRACTION_REQUIRED,
        "bootstrap_seed": BOOT_SEED,
        "bootstrap_B": BOOT_B,
    }
    if met:
        decision["threshold_groups"] = ";".join(
            f"{r['family']}|C={r['C']}|W={r['window']}" for r in met
        )
    with open(rdir / "decision.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(decision.keys()))
        w.writeheader()
        w.writerow(decision)
    print(f"groups={len(charged)} threshold_met={len(met)} decision={decision['decision']}")
    for r in charged[:12]:
        print(f"  {r['family']:<22} C={r['C']:<7} gain={r['mean_gain_miss_abs']:.5f} "
              f"frac>={THRESHOLD}={r['frac_gain_ge_0.02']:.3f} switches={r['mean_oracle_switches']:.2f}")


if __name__ == "__main__":
    main()
