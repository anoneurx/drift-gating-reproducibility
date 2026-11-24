#!/usr/bin/env python3
"""Scenario-clustered bootstrap for the independent synthetic pilot.

The main tables (VI-XI) of the paper were produced by a simulator whose raw
per-trace output was not retained, so a clustered analysis cannot be applied
to them. This script applies it to the independent re-implementation's
held-out synthetic traces (recovery/fresh_train_test_results.csv), where the
raw rows do exist. The scenario, not the trace, is the independent unit:
four non-stable scenarios (abrupt, gradual, recurring, composite) and one
stable scenario. A naive trace-level bootstrap is reported alongside to show
how much too narrow it is when traces share a generator.
"""
import csv, os, random
from collections import defaultdict
from statistics import mean

HERE = os.path.dirname(os.path.abspath(__file__))
# Locate the CSV both in recovery/ and in a standalone reproduction/ package.
SRC = os.path.join(HERE, "fresh_train_test_results.csv")
if not os.path.exists(SRC):
    SRC = os.path.join(HERE, "..", "recovery", "fresh_train_test_results.csv")
random.seed(11)
NONSTABLE = ["abrupt", "gradual", "recurring", "composite"]


def load():
    d = defaultdict(dict)
    for r in csv.DictReader(open(SRC)):
        d[r["scenario"]][(r["scenario"], r["seed"], r["method"])] = float(r["miss_ratio"])
    # restructure: method -> scenario -> list of trace values
    out = defaultdict(lambda: defaultdict(list))
    for r in csv.DictReader(open(SRC)):
        out[r["method"]][r["scenario"]].append(float(r["miss_ratio"]))
    return out


def ci(vals, n=20000):
    s = sorted(mean(random.choices(vals, k=len(vals))) for _ in range(n))
    return s[int(0.025 * n)], s[int(0.975 * n)]


def main():
    d = load()
    methods = [m for m in d if m not in ("DA", "OPT")]
    print("=== NON-STABLE SYNTHETIC TRACES (independent simulator) ===")
    print("cluster = scenario (4 clusters); trace-level CI shown for contrast\n")
    print(f"{'method':14} {'mean diff':>10} {'cluster 95% CI':>24} {'trace 95% CI':>24}")
    rows = []
    for m in sorted(methods):
        cdiff = [mean(d["DA"][s]) - mean(d[m][s]) for s in NONSTABLE]
        tdiff = [d["DA"][s][i] - d[m][s][i] for s in NONSTABLE
                 for i in range(len(d["DA"][s]))]
        c_lo, c_hi = ci(cdiff)
        t_lo, t_hi = ci(tdiff)
        print(f"{m:14} {mean(cdiff):+10.4f} [{c_lo:+.4f}, {c_hi:+.4f}]".ljust(52) +
              f"[{t_lo:+.4f}, {t_hi:+.4f}]")
        rows.append((m, mean(cdiff), c_lo, c_hi, t_lo, t_hi))
    out = os.path.join(HERE, "scenario_clustered_bootstrap_results.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["comparison", "mean_DA_minus_method", "cluster_lo", "cluster_hi",
                    "trace_lo", "trace_hi"])
        for r in rows:
            w.writerow([f"DA-{r[0]}"] + [f"{x:.5f}" for x in r[1:]])
    print("\n=== per-scenario DA vs key baselines ===")
    for s in NONSTABLE:
        print(f"  {s:11} DA {mean(d['DA'][s]):.4f}  LRU {mean(d['LRU'][s]):.4f}  "
              f"S3-FIFO {mean(d['S3-FIFO'][s]):.4f}  LPR-style {mean(d['LPR-style'][s]):.4f}")
    with open(out, "a") as f:
        f.write("# The original paper's Tables VI-XI cannot receive this analysis: "
                "raw per-trace output was not retained.\n")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
