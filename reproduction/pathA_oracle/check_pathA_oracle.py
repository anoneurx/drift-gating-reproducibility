#!/usr/bin/env python3
"""Read-only consistency checks for the Path A oracle raw outputs."""
import csv
import math
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def load(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default=str(RESULTS))
    args = ap.parse_args()
    rdir = Path(args.results_dir)
    manifest = load(rdir / "manifest.csv")
    summary = load(rdir / "summary.csv")
    policy = load(rdir / "policy.csv")
    windows = load(rdir / "windows.csv")

    bad = []
    expected_keys = set()
    for m in manifest:
        for cap in (int(x) for x in m["capacities"].split(";")):
            for w in (50000, 100000):
                expected_keys.add((m["trace"], cap, w))

    # Only require keys that appear in the summary; a run may select one window.
    actual_windows = {int(r["window"]) for r in summary}
    grouped = defaultdict(list)
    for r in summary:
        grouped[(r["trace"], int(r["C"]), int(r["window"]))].append(r)

    for key, rows in grouped.items():
        costs = sorted(float(r["switch_cost"]) for r in rows)
        if any(abs(a - b) > 0.05 for a, b in zip(costs, [0.0, float(key[1])])):
            bad.append((key, "costs", costs))
        for r in rows:
            bsr = float(r["best_static_miss_ratio"])
            omr = float(r["oracle_miss_ratio"])
            gain = float(r["gain_miss_abs"])
            if abs((bsr - omr) - gain) > 1e-8:
                bad.append((key, "gain", bsr, omr, gain))
            # A zero-cost oracle must never miss more than the best static
            # policy. The charged oracle may, because it refuses costly switches.
            if float(r["switch_cost"]) == 0.0 and omr > bsr + 1e-9:
                bad.append((key, "zero-cost oracle worse than best static", bsr, omr))
            if int(r["oracle_switches"]) < 0:
                bad.append((key, "negative switches"))
            if not all(math.isfinite(float(r[f])) for f in
                       ("best_static_miss_ratio", "oracle_miss_ratio",
                        "oracle_objective_ratio", "gain_miss_abs")):
                bad.append((key, "non-finite"))

    pol_group = defaultdict(list)
    for r in policy:
        pol_group[(r["trace"], int(r["C"]), int(r["window"]))].append(r)
    for key, rows in grouped.items():
        pr = pol_group.get(key, [])
        if not pr:
            bad.append((key, "missing policy rows"))
            continue
        best = min(float(r["total_miss"]) for r in pr)
        declared = min(float(r["best_static_total_miss"]) for r in rows)
        if abs(best - declared) > 1e-9:
            bad.append((key, "best static mismatch", best, declared))

    for r in windows:
        if int(r["window_idx"]) < 0:
            bad.append((r["trace"], "bad window idx"))

    traces = {m["trace"] for m in manifest}
    missing = traces - {r["trace"] for r in summary}
    if missing:
        bad.append(("missing traces in summary", sorted(missing)))

    print(f"manifest traces: {len(manifest)}")
    print(f"summary rows: {len(summary)}; groups: {len(grouped)}")
    print(f"policy rows: {len(policy)}; window rows: {len(windows)}")
    print(f"windows present: {sorted(actual_windows)}")
    print(f"FAILURES: {len(bad)}")
    for b in bad[:20]:
        print("  ", b)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
