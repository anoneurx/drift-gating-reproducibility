#!/usr/bin/env python3
"""Percentile bootstrap intervals for the exploratory real-program appendix.

Reads `whole_program_holdout_results.csv` (fifteen whole-program folds) and
writes `appendix_intervals.csv`.  The program (fold), not the individual seed
trace, is the resampling unit: each row is the mean over the four traces of one
held-out program.  With fifteen programs the intervals are still coarse and are
reported as exploratory, not as confirmatory evidence.

A paired percentile interval is computed for DA minus each baseline, together
with win/loss/tie counts and a two-sided Wilcoxon signed-rank p-value using the
normal approximation (the same procedure as `analyze_main_study.py`).  Holm
adjustment is applied across the ten comparisons that appear in the main
appendix table.

Usage: python3 appendix_intervals.py
"""
import csv
import math
import os
import random
from collections import defaultdict
from statistics import mean

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "whole_program_holdout_results.csv")
OUT = os.path.join(HERE, "appendix_intervals.csv")
NBOOT = 10000
SEED = 7
BASELINES = ["S3-FIFO", "ContShadow", "2Q", "ARC", "DIP-set-duel", "LRU",
             "LPR-style", "CAR", "CLOCK-Pro", "MGLRU-style"]
random.seed(SEED)


def boot_ci(xs):
    bs = sorted(mean(random.choices(xs, k=len(xs))) for _ in range(NBOOT))
    return bs[int(0.025 * NBOOT)], bs[int(0.975 * NBOOT) - 1]


def wilcoxon(xs):
    nz = [x for x in xs if x != 0]
    if not nz:
        return 1.0
    ranks = sorted(range(len(nz)), key=lambda i: abs(nz[i]))
    wp = wm = 0.0
    for r, i in enumerate(ranks, 1):
        if nz[i] > 0:
            wp += r
        else:
            wm += r
    w = min(wp, wm)
    mu = len(nz) * (len(nz) + 1) / 4
    sd = math.sqrt(len(nz) * (len(nz) + 1) * (2 * len(nz) + 1) / 24)
    z = (w - mu) / sd if sd else 0.0
    return max(0.0, min(1.0, math.erfc(abs(z) / math.sqrt(2))))


def holm(pairs):
    order = sorted(pairs, key=lambda x: x[1])
    m = len(order)
    adj = {}
    for i, (k, p) in enumerate(order):
        adj[k] = min(1.0, max(0.0, (m - i) * p))
    return [(k, adj[k]) for k, _ in pairs]


def main():
    rows = list(csv.DictReader(open(SRC)))
    methods = [c for c in rows[0] if c != "held_out_program"]
    means = {m: mean(float(r[m]) for r in rows) for m in methods}
    da = [float(r["DA"]) for r in rows]

    raw = []
    records = []
    for m in BASELINES:
        other = [float(r[m]) for r in rows]
        diffs = [a - b for a, b in zip(da, other)]
        lo, hi = boot_ci(diffs)
        w = sum(d < 0 for d in diffs)
        l = sum(d > 0 for d in diffs)
        t = sum(d == 0 for d in diffs)
        raw.append((m, wilcoxon(diffs)))
        records.append({
            "comparison": f"DA-{m}",
            "mean_DA_minus_method": mean(diffs),
            "ci_lo": lo,
            "ci_hi": hi,
            "wins": w,
            "losses": l,
            "ties": t,
            "p": raw[-1][1],
        })
    adj = dict(holm(raw))
    for r in records:
        r["holm_p"] = adj[r["comparison"].split("DA-", 1)[1]]

    with open(OUT, "w", newline="") as f:
        fields = ["comparison", "mean_DA_minus_method", "ci_lo", "ci_hi",
                  "wins", "losses", "ties", "p", "holm_p"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in records:
            w.writerow({k: (f"{r[k]:.5f}" if isinstance(r[k], float) else r[k])
                        for k in fields})

    print("Mean miss ratio over fifteen whole-program folds:")
    for m in sorted(means, key=means.get):
        print(f"  {m:14} {means[m]:.4f}")
    print("\nDA minus baseline (negative favours DA):")
    for r in records:
        print(f"  {r['comparison']:20} {r['mean_DA_minus_method']:+.4f} "
              f"[{r['ci_lo']:+.4f}, {r['ci_hi']:+.4f}]  "
              f"W/L/T={r['wins']}/{r['losses']}/{r['ties']}  "
              f"p={r['p']:.4g}  Holm={r['holm_p']:.4g}")
    print(f"\nWrote {OUT} (bootstrap seed {SEED}, {NBOOT} resamples)")


if __name__ == "__main__":
    main()
