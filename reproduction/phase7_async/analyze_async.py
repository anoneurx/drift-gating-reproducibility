#!/usr/bin/env python3
"""Aggregate real Phase 7 async-shadow prototype runs against frozen sync DA."""
import csv
import os
from statistics import mean, median

import numpy as np
from scipy.stats import wilcoxon

HERE = os.path.dirname(os.path.abspath(__file__))
REPRO = os.path.dirname(HERE)
SYNC = os.path.join(REPRO, "main_study_results.csv")
B = 10_000
SEED = 20261126


def read_miss(path):
    out = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["scenario"] == "stable" or r["method"] != "DA":
                continue
            out.append((r["scenario"], int(r["seed"]), float(r["miss_ratio"]),
                        float(r["switches"]), float(r["shadow_evals"])))
    return out


def write_csv(path, fields, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    sync = read_miss(SYNC)
    if len(sync) != 80:
        raise SystemExit(f"expected 80 non-stable sync rows, got {len(sync)}")
    sync_by = {(s, seed): v for s, seed, v, _sw, _ev in sync}

    reps = sorted(fn for fn in os.listdir(HERE) if fn.startswith("async_results") and fn.endswith(".csv"))
    if not reps:
        raise SystemExit("no async_results*.csv files found")
    summary = []
    paired = []
    for fn in reps:
        rep = fn[len("async_results"):-4] or "0"
        a = read_miss(os.path.join(HERE, fn))
        if len(a) != 80:
            raise SystemExit(f"{fn}: expected 80 non-stable rows, got {len(a)}")
        a_by = {(s, seed): v for s, seed, v, _sw, _ev in a}
        if set(a_by) != set(sync_by):
            raise SystemExit(f"{fn}: trace keys differ from frozen sync DA")
        keys = sorted(sync_by)
        diff = np.array([a_by[k] - sync_by[k] for k in keys])
        rng = np.random.default_rng(SEED)
        boots = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(B)]
        try:
            p = float(wilcoxon(diff, zero_method="wilcox", alternative="two-sided").pvalue)
        except ValueError:
            p = 1.0
        summary.append({
            "repetition": rep, "n": len(a), "mean_miss": mean([x[2] for x in a]),
            "mean_switches": mean([x[3] for x in a]), "mean_shadow_evals": mean([x[4] for x in a]),
        })
        paired.append({
            "repetition": rep, "mean_async_minus_sync": float(diff.mean()),
            "ci_low": float(np.percentile(boots, 2.5)), "ci_high": float(np.percentile(boots, 97.5)),
            "wilcoxon_p": p, "holm_p": p, "n_positive": int((diff > 0).sum()),
            "n_zero": int((diff == 0).sum()), "n_negative": int((diff < 0).sum()),
        })
    write_csv(os.path.join(HERE, "summary.csv"),
              ["repetition", "n", "mean_miss", "mean_switches", "mean_shadow_evals"], summary)
    write_csv(os.path.join(HERE, "paired.csv"),
              ["repetition", "mean_async_minus_sync", "ci_low", "ci_high", "wilcoxon_p", "holm_p",
               "n_positive", "n_zero", "n_negative"], paired)

    timing = []
    with open(os.path.join(HERE, "timing.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            if r["scenario"] == "stable":
                continue
            timing.append({k: r[k] for k in r})
    sum_enqueued = sum(int(r["enqueued"]) for r in timing)
    sum_completed = sum(int(r["completed"]) for r in timing)
    sum_wall = sum(float(r["worker_wall_ns"]) for r in timing)
    sum_cpu = sum(float(r["worker_cpu_ns"]) for r in timing)
    sum_submit = sum(float(r["submit_ns"]) for r in timing)
    sum_check = sum(float(r["check_ns"]) for r in timing)
    per_eval_wall = [float(r["worker_wall_ns"]) / int(r["completed"]) for r in timing
                     if int(r["completed"])]
    tsum = {
        "n_traces": len(timing),
        "sum_enqueued": sum_enqueued,
        "sum_dropped": sum(int(r["dropped"]) for r in timing),
        "sum_completed": sum_completed,
        "sum_applied": sum(int(r["applied"]) for r in timing),
        "sum_superseded": sum(int(r["superseded"]) for r in timing),
        "sum_stale": sum(int(r["stale"]) for r in timing),
        "sum_submit_ns": sum_submit,
        "sum_check_ns": sum_check,
        "sum_worker_wall_ns": sum_wall,
        "sum_worker_cpu_ns": sum_cpu,
        "mean_submit_ns_per_trace": mean(float(r["submit_ns"]) for r in timing),
        "mean_check_ns_per_trace": mean(float(r["check_ns"]) for r in timing),
        "mean_worker_wall_ns_per_trace": mean(float(r["worker_wall_ns"]) for r in timing),
        "mean_worker_cpu_ns_per_trace": mean(float(r["worker_cpu_ns"]) for r in timing),
        "mean_submit_ns_per_enqueued_eval": sum_submit / sum_enqueued,
        "mean_wall_ns_per_completed_eval": sum_wall / sum_completed,
        "mean_cpu_ns_per_completed_eval": sum_cpu / sum_completed,
        "median_wall_ns_per_completed_eval": median(per_eval_wall),
    }
    write_csv(os.path.join(HERE, "timing_summary.csv"), list(tsum), [tsum])
    print(f"aggregated {len(reps)} async repetitions over {len(sync)} non-stable traces")


if __name__ == "__main__":
    main()
