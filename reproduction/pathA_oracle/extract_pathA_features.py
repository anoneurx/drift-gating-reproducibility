#!/usr/bin/env python3
"""Auxiliary trace features for the Path A predictive-rule gate.

This script is not used to select the oracle endpoint. It is prepared so that,
if the pre-specified oracle gate opens, a trace-feature rule can be tested on
unseen families without inventing new data.
"""
import argparse
import csv
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
FIELDS = [
    "trace", "family", "source", "refs", "wss", "wss_per_ref", "top1_share",
    "top10_share", "entropy_bits", "reuse_mean", "reuse_median", "reuse_p90",
    "reuse_cv", "uniq_window_mean", "uniq_window_cv", "half_unique_diff",
]


def features(path):
    ids = np.fromfile(path, dtype="<u4")
    n = ids.size
    uniq, inv, counts = np.unique(ids, return_inverse=True, return_counts=True)
    wss = uniq.size
    p = counts / n
    entropy = float(-(p * np.log2(p)).sum())
    top = np.sort(counts)[::-1]
    top1 = float(top[0] / n)
    top10 = float(top[:10].sum() / n)

    last = np.full(int(ids.max()) + 1, -1, dtype=np.int64)
    dists = np.empty(n, dtype=np.int64)
    k = 0
    for i, v in enumerate(ids):
        lv = last[v]
        if lv >= 0:
            dists[k] = i - lv
            k += 1
        last[v] = i
    d = dists[:k].astype(np.float64)
    if d.size == 0:
        d = np.array([float(n)])

    step = 100000
    uniq_windows = [len(np.unique(ids[i:i + step])) for i in range(0, n, step)]
    uw = np.array(uniq_windows, dtype=np.float64)
    half = n // 2
    hdiff = abs(len(np.unique(ids[:half])) - len(np.unique(ids[half:]))) / wss

    return {
        "refs": n, "wss": wss, "wss_per_ref": wss / n,
        "top1_share": top1, "top10_share": top10, "entropy_bits": entropy,
        "reuse_mean": float(d.mean()), "reuse_median": float(np.median(d)),
        "reuse_p90": float(np.quantile(d, 0.90)),
        "reuse_cv": float(d.std() / d.mean()) if d.mean() else 0.0,
        "uniq_window_mean": float(uw.mean()),
        "uniq_window_cv": float(uw.std() / uw.mean()) if uw.mean() else 0.0,
        "half_unique_diff": float(hdiff),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(RESULTS / "manifest.csv"))
    ap.add_argument("--out", default=str(RESULTS / "features.csv"))
    args = ap.parse_args()
    with open(args.manifest, newline="") as fh:
        manifest = list(csv.DictReader(fh))
    rows = []
    for i, m in enumerate(manifest, 1):
        r = {"trace": m["trace"], "family": m["family"], "source": m["source"]}
        r.update(features(Path(m["path"])))
        rows.append(r)
        print(f"{i}/{len(manifest)} {m['trace']}")
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


if __name__ == "__main__":
    main()
