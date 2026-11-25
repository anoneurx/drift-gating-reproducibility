#!/usr/bin/env python3
"""Summarize real guest-kernel measurements from raw files only."""
import csv
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")


def kv_line(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for line in fh:
            for part in line.strip().split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    try:
                        out[k] = float(v)
                    except ValueError:
                        out[k] = v
    return out


def vmstat(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for line in fh:
            p = line.split()
            if len(p) == 2 and p[1].isdigit():
                out[p[0]] = int(p[1])
    return out


def read_text(path):
    if not os.path.exists(path):
        return ""
    with open(path) as fh:
        return fh.read().strip()


def write_csv(path, fields, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    summary = []
    fsum = []
    for cond in ("fixed_lru", "fixed_mglru", "coupled"):
        for rep in range(1, 4):
            d = os.path.join(RESULTS, cond, str(rep))
            w = kv_line(os.path.join(d, "workload.txt"))
            vb = vmstat(os.path.join(d, "vmstat_before.txt"))
            va = vmstat(os.path.join(d, "vmstat_after.txt"))
            toggles = 0
            tp = os.path.join(d, "ctl_toggles.csv")
            if os.path.exists(tp):
                with open(tp) as fh:
                    toggles = sum(1 for _ in csv.DictReader(fh))
            summary.append({
                "condition": cond, "rep": rep,
                "elapsed_ns": w.get("elapsed_ns", ""), "access_ns_sum": w.get("access_ns_sum", ""),
                "minflt": w.get("minflt", ""), "majflt": w.get("majflt", ""),
                "refault_delta": va.get("workingset_refault_anon", 0) - vb.get("workingset_refault_anon", 0),
                "pgscan_delta": va.get("pgscan_anon", 0) - vb.get("pgscan_anon", 0),
                "pgsteal_delta": va.get("pgsteal_anon", 0) - vb.get("pgsteal_anon", 0),
                "toggles": toggles,
                "lru_before": read_text(os.path.join(d, "lru_enabled_before.txt")),
                "lru_after": read_text(os.path.join(d, "lru_enabled_after.txt")),
                "min_ttl_ms": read_text(os.path.join(d, "min_ttl_ms.txt")),
                "cgroup_memory_max": read_text(os.path.join(d, "cgroup_memory_max.txt")),
                "cgroup_memory_peak": read_text(os.path.join(d, "cgroup_memory_peak.txt")),
                "guest_uname": read_text(os.path.join(d, "guest_uname.txt")),
            })
    write_csv(os.path.join(HERE, "kernel_summary.csv"),
              ["condition", "rep", "elapsed_ns", "access_ns_sum", "minflt", "majflt",
               "refault_delta", "pgscan_delta", "pgsteal_delta", "toggles", "lru_before",
               "lru_after", "min_ttl_ms", "cgroup_memory_max", "cgroup_memory_peak",
               "guest_uname"], summary)

    groups = defaultdict(list)
    fp = os.path.join(HERE, "ftrace_durations.csv")
    if os.path.exists(fp):
        with open(fp, newline="") as fh:
            for r in csv.DictReader(fh):
                groups[(r["condition"], int(r["rep"]), r["function"])].append(float(r["duration_ns"]))
    for (cond, rep, fn), vals in sorted(groups.items()):
        a = np.asarray(vals)
        fsum.append({"condition": cond, "rep": rep, "function": fn, "n": len(a),
                     "median_ns": float(np.median(a)), "p95_ns": float(np.percentile(a, 95)),
                     "max_ns": float(np.max(a))})
    write_csv(os.path.join(HERE, "ftrace_summary.csv"),
              ["condition", "rep", "function", "n", "median_ns", "p95_ns", "max_ns"], fsum)
    print(f"summarized {len(summary)} guest runs and {len(fsum)} ftrace function groups")


if __name__ == "__main__":
    main()
