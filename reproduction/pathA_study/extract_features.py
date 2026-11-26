#!/usr/bin/env python3
"""Extract purely observable trace features (no oracle labels) for unseen-family prediction."""
import csv
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RESULTS = HERE / "results"


def extract_one(path: Path):
    ids = np.fromfile(path, dtype="<u4")
    n = int(ids.size)
    uniq, counts = np.unique(ids, return_counts=True)
    wss = int(uniq.size)
    p = counts / n
    entropy = float(-(p * np.log2(p)).sum())
    top = np.sort(counts)[::-1]
    top1 = float(top[0] / n)
    top10 = float(top[:10].sum() / n)

    # Vectorized reuse distance via last-seen index array
    last = np.full(int(ids.max()) + 1, -1, dtype=np.int64)
    dists = np.empty(n, dtype=np.int64)
    k = 0
    for i, v in enumerate(ids):
        lv = last[v]
        if lv >= 0:
            dists[k] = i - lv
            k += 1
        last[v] = i
    d = dists[:k].astype(np.float64) if k > 0 else np.array([float(n)])
    reuse_mean = float(d.mean())
    reuse_median = float(np.median(d))
    reuse_p90 = float(np.quantile(d, 0.90))
    reuse_cv = float(d.std() / reuse_mean) if reuse_mean > 0 else 0.0

    # Window-level temporal non-stationarity features (50k-ref windows)
    step = 50000
    win_sets = []
    win_wss = []
    win_med_reuse = []
    for start in range(0, n, step):
        seg = ids[start:start + step]
        if seg.size < 10000:
            continue
        u = np.unique(seg)
        win_sets.append(set(u.tolist()))
        win_wss.append(float(u.size))
        # local reuse within window
        l_map = {}
        ld = []
        for idx, val in enumerate(seg.tolist()):
            if val in l_map:
                ld.append(idx - l_map[val])
            l_map[val] = idx
        win_med_reuse.append(float(np.median(ld)) if ld else float(seg.size))

    uw = np.array(win_wss, dtype=np.float64) if win_wss else np.array([float(wss)])
    uniq_win_cv = float(uw.std() / uw.mean()) if uw.mean() > 0 else 0.0

    turnovers = []
    for a, b in zip(win_sets, win_sets[1:]):
        union = len(a | b)
        inter = len(a & b)
        turnovers.append(1.0 - (inter / union) if union > 0 else 0.0)
    turnover_mean = float(np.mean(turnovers)) if turnovers else 0.0
    turnover_max = float(np.max(turnovers)) if turnovers else 0.0

    wr = np.array(win_med_reuse, dtype=np.float64) if win_med_reuse else np.array([reuse_median])
    win_reuse_cv = float(wr.std() / wr.mean()) if wr.mean() > 0 else 0.0

    half = n // 2
    half_diff = abs(len(np.unique(ids[:half])) - len(np.unique(ids[half:]))) / max(1, wss)

    # First-20% early-prefix features (for deployment-time prediction)
    p20 = ids[:max(20000, n // 5)]
    mid = len(p20) // 2
    s1, s2 = set(np.unique(p20[:mid]).tolist()), set(np.unique(p20[mid:]).tolist())
    u20 = len(s1 | s2)
    prefix20_turnover = 1.0 - (len(s1 & s2) / u20) if u20 > 0 else 0.0

    return {
        "refs": n,
        "wss": wss,
        "wss_per_ref": wss / n,
        "top1_share": top1,
        "top10_share": top10,
        "entropy_bits": entropy,
        "reuse_mean": reuse_mean,
        "reuse_median": reuse_median,
        "reuse_p90": reuse_p90,
        "reuse_cv": reuse_cv,
        "uniq_window_mean": float(uw.mean()),
        "uniq_window_cv": uniq_win_cv,
        "window_turnover_mean": turnover_mean,
        "window_turnover_max": turnover_max,
        "window_reuse_cv": win_reuse_cv,
        "half_unique_diff": float(half_diff),
        "prefix20_turnover": float(prefix20_turnover),
    }


def main():
    man_path = RESULTS / "manifest.csv"
    with open(man_path, newline="") as fh:
        manifest = list(csv.DictReader(fh))
    rows = []
    for i, m in enumerate(manifest, 1):
        p = ROOT / m["path"]
        row = {"trace": m["trace"], "family": m["family"], "source": m["source"]}
        row.update(extract_one(p))
        rows.append(row)
        if i % 20 == 0 or i == len(manifest):
            print(f"features {i}/{len(manifest)}")
    out_path = RESULTS / "features.csv"
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
