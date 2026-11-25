#!/usr/bin/env python3
"""Trace-level bootstrap confidence intervals for the cost-model break-even
quantities.  Resamples the 80 non-stable test traces (paired across methods)
10,000 times and recomputes:

  cm*  = (mean t_ContShadow - mean t_DA) / (mean m_DA - mean m_ContShadow)
  R    = N_avg * (mean m_DA - mean m_ContShadow) /
         (mean E_ContShadow - mean E_DA)

N_avg is the fixed average non-stable trace length from cost_model.py.  The
point estimates reproduce cost_model.csv exactly.  The CSV output records the
point estimate and the 2.5/97.5 percentiles (95% percentile CI).
"""
import csv
import os
import random
from collections import defaultdict
from statistics import mean

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "main_study_results.csv")
OUT = os.path.join(HERE, "cost_model_bootstrap.csv")
NONSTABLE = ("abrupt", "gradual", "recurring", "composite")
N_AVG = 545000.0  # mean of 600k, 600k, 480k, 500k (cost_model.py)
B = 10000
SEED = 20261123


def load():
    d = defaultdict(dict)
    for r in csv.DictReader(open(SRC)):
        if r["scenario"] in NONSTABLE:
            key = (r["scenario"], r["seed"])
            d[key][r["method"]] = {
                "miss": float(r["miss_ratio"]),
                "ns": float(r["ns_per_ref"]),
                "evals": float(r["shadow_evals"]),
            }
    keys = sorted(k for k, v in d.items() if "DA" in v and "ContShadow" in v)
    arrays = {m: [] for m in ("DA", "ContShadow")}
    for k in keys:
        for m in arrays:
            arrays[m].append(d[k][m])
    return arrays


def compute(arrays, idx):
    da = [arrays["DA"][i] for i in idx]
    cs = [arrays["ContShadow"][i] for i in idx]
    md = mean(x["miss"] for x in da)
    mc = mean(x["miss"] for x in cs)
    td = mean(x["ns"] for x in da)
    tc = mean(x["ns"] for x in cs)
    ed = mean(x["evals"] for x in da)
    ec = mean(x["evals"] for x in cs)
    dm = md - mc
    cstar = (tc - td) / dm if dm else float("nan")
    R = N_AVG * dm / (ec - ed) if ec != ed else float("nan")
    return cstar, R


def main():
    arrays = load()
    n = len(arrays["DA"])
    assert n == 80, n
    idx_all = list(range(n))
    point = compute(arrays, idx_all)
    rng = random.Random(SEED)
    boots = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        boots.append(compute(arrays, idx))
    cstars = sorted(x[0] for x in boots if x[0] == x[0])
    Rs = sorted(x[1] for x in boots if x[1] == x[1])
    def ci(xs):
        return xs[int(0.025 * len(xs))], xs[int(0.975 * len(xs)) - 1]
    c_lo, c_hi = ci(cstars)
    R_lo, R_hi = ci(Rs)
    print(f"n traces = {n}, B = {B}, seed = {SEED}")
    print(f"direct break-even miss cost cm* = {point[0]:.1f} ns "
          f"({point[0]/1000:.3f} us), 95% CI "
          f"[{c_lo:.1f}, {c_hi:.1f}] ns "
          f"([{c_lo/1000:.3f}, {c_hi/1000:.3f}] us)")
    print(f"break-even ratio R = {point[1]:.1f}, "
          f"95% CI [{R_lo:.1f}, {R_hi:.1f}]")
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quantity", "point", "ci95_low", "ci95_high", "unit",
                    "n_traces", "bootstrap_reps", "seed"])
        w.writerow(["direct_break_even_miss_cost", f"{point[0]:.3f}",
                    f"{c_lo:.3f}", f"{c_hi:.3f}", "ns", n, B, SEED])
        w.writerow(["direct_break_even_miss_cost_us", f"{point[0]/1000:.4f}",
                    f"{c_lo/1000:.4f}", f"{c_hi/1000:.4f}", "us", n, B, SEED])
        w.writerow(["break_even_ratio_R", f"{point[1]:.3f}",
                    f"{R_lo:.3f}", f"{R_hi:.3f}", "c_e/c_m", n, B, SEED])
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
