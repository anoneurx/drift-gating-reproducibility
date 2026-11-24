#!/usr/bin/env python3
"""Trace-level bootstrap for the total-time envelope.

Reads the frozen seed-5001 main-study results and resamples the 80
non-stable traces (paired across methods).  For each replicate it recomputes
the mean per-reference time and miss ratio of CLOCK, S3-FIFO, ContShadow and
DA, the pairwise total-time crossings, and the minimum excess of DA over the
lower envelope of the other three policies.

Output: total_time_bootstrap.csv (point estimate and 95% percentile CI).

Run: python3 bootstrap_total_time.py
"""
import csv
import os
import random
import statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "main_study_results.csv")
OUT = os.path.join(HERE, "total_time_bootstrap.csv")
NONSTABLE = {"abrupt", "gradual", "recurring", "composite"}
METHODS = ["CLOCK", "S3-FIFO", "ContShadow", "DA"]
B = 10000
SEED = 20261124


def load_paired():
    by = defaultdict(dict)
    for r in csv.DictReader(open(SRC)):
        if r["scenario"] not in NONSTABLE:
            continue
        by[(r["scenario"], r["seed"])][r["method"]] = (
            float(r["ns_per_ref"]), float(r["miss_ratio"])
        )
    keys = sorted(k for k, v in by.items() if all(m in v for m in METHODS))
    return keys, by


def means(keys, by, idx):
    out = {}
    for m in METHODS:
        out[m] = (
            st.mean(by[keys[i]][m][0] for i in idx),
            st.mean(by[keys[i]][m][1] for i in idx),
        )
    return out


def crossing(M, a, b):
    """Miss cost (ns) where total time of a and b is equal."""
    ta, ma = M[a]
    tb, mb = M[b]
    den = ma - mb
    if abs(den) < 1e-12:
        return float("nan")
    return (tb - ta) / den


def min_gap(M):
    """Minimum of T_DA - min(T_CLOCK,T_S3,T_CS) over c_m >= 0.

    The difference is piecewise linear; its minimum on [0, inf) is at 0 or at
    a positive crossing among the three non-DA policies.
    """
    pts = [0.0]
    for a, b in (("CLOCK", "S3-FIFO"), ("CLOCK", "ContShadow"),
                 ("S3-FIFO", "ContShadow")):
        x = crossing(M, a, b)
        if x == x and x > 0:
            pts.append(x)
    best = float("inf")
    best_x = None
    for x in pts:
        da = M["DA"][0] + M["DA"][1] * x
        other = min(M[m][0] + M[m][1] * x for m in
                    ("CLOCK", "S3-FIFO", "ContShadow"))
        if da - other < best:
            best = da - other
            best_x = x
    return best, best_x


def ci(xs):
    xs = sorted(xs)
    return xs[int(0.025 * len(xs))], xs[int(0.975 * len(xs)) - 1]


def main():
    keys, by = load_paired()
    n = len(keys)
    assert n == 80, n
    idx_all = list(range(n))
    point = means(keys, by, idx_all)
    point_cross = {
        "crossing_clock_s3": crossing(point, "CLOCK", "S3-FIFO"),
        "crossing_s3_cs": crossing(point, "S3-FIFO", "ContShadow"),
        "crossing_da_cs": crossing(point, "DA", "ContShadow"),
        "crossing_da_s3": crossing(point, "DA", "S3-FIFO"),
        "crossing_clock_cs": crossing(point, "CLOCK", "ContShadow"),
        "crossing_clock_da": crossing(point, "CLOCK", "DA"),
    }
    point_gap, point_gap_x = min_gap(point)

    rng = random.Random(SEED)
    samples = defaultdict(list)
    gap_samples = []
    gap_x_samples = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        M = means(keys, by, idx)
        for name, (a, b) in {
            "crossing_clock_s3": ("CLOCK", "S3-FIFO"),
            "crossing_s3_cs": ("S3-FIFO", "ContShadow"),
            "crossing_da_cs": ("DA", "ContShadow"),
            "crossing_da_s3": ("DA", "S3-FIFO"),
            "crossing_clock_cs": ("CLOCK", "ContShadow"),
            "crossing_clock_da": ("CLOCK", "DA"),
        }.items():
            x = crossing(M, a, b)
            if x == x and x > 0:
                samples[name].append(x)
        g, gx = min_gap(M)
        if g == g:
            gap_samples.append(g)
            gap_x_samples.append(gx)

    rows = []
    for name, val in point_cross.items():
        xs = samples[name]
        lo, hi = ci(xs)
        rows.append([name, f"{val/1000:.6f}", f"{lo/1000:.6f}", f"{hi/1000:.6f}",
                     "us", n, B, SEED, len(xs)])
    lo, hi = ci(gap_samples)
    rows.append(["min_da_gap_ns", f"{point_gap:.6f}", f"{lo:.6f}", f"{hi:.6f}",
                 "ns", n, B, SEED, len(gap_samples)])
    lo, hi = ci(gap_x_samples)
    rows.append(["min_da_gap_cm_us", f"{point_gap_x/1000:.6f}",
                 f"{lo/1000:.6f}", f"{hi/1000:.6f}",
                 "us", n, B, SEED, len(gap_x_samples)])

    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quantity", "point", "ci95_low", "ci95_high", "unit",
                    "n_traces", "bootstrap_reps", "seed", "valid_reps"])
        w.writerows(rows)

    print(f"n={n}, B={B}, seed={SEED}")
    for row in rows:
        print(f"{row[0]:22s} {row[1]:>10s}  [{row[2]}, {row[3]}] {row[4]}"
              f"  valid={row[8]}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
