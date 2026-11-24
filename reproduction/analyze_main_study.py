#!/usr/bin/env python3
"""Build the primary paper tables from the reproducible main-study CSVs.

Reads the outputs of run_main_study.sh (all produced by the released
sim_full.cpp) and prints every number used in the revised Section V.
No manual transcription is involved.
"""
import csv, math, random
from collections import defaultdict
from statistics import mean, median

random.seed(7)
NBOOT = 10000

NONSTABLE = ["abrupt", "gradual", "recurring", "composite"]
METHOD_ORDER = ["LRU", "FIFO", "CLOCK", "LFU-A", "MRU", "2Q", "ARC", "S3-FIFO",
                "LeCaR", "LPR-style", "ContShadow", "DA", "OPT"]
ABLATIONS = ["DA", "ContShadow", "DA-noPurge", "DA-noS2", "DA-noShadow", "DA-noCost", "DA-noDwell"]


def load(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def by_method(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["method"]].append(r)
    return d


def nonstable(rows):
    return [r for r in rows if r["scenario"] in NONSTABLE]


def boot_ci(xs, n=NBOOT):
    if not xs:
        return (0.0, 0.0)
    bs = sorted(mean(random.choices(xs, k=len(xs))) for _ in range(n))
    return bs[int(0.025 * n)], bs[int(0.975 * n) - 1]


def wilcoxon(xs):
    """Approximate two-sided Wilcoxon signed-rank p via normal approximation."""
    nz = [x for x in xs if x != 0]
    if not nz:
        return 1.0
    ranks = sorted(range(len(nz)), key=lambda i: abs(nz[i]))
    Wp = Wm = 0.0
    for r, i in enumerate(ranks, 1):
        if nz[i] > 0:
            Wp += r
        else:
            Wm += r
    W = min(Wp, Wm)
    mu = len(nz) * (len(nz) + 1) / 4
    sd = math.sqrt(len(nz) * (len(nz) + 1) * (2 * len(nz) + 1) / 24)
    z = (W - mu) / sd if sd else 0.0
    return max(0.0, min(1.0, math.erfc(abs(z) / math.sqrt(2))))


def holm(pairs):
    out, m = [], len(pairs)
    for i, (k, p) in enumerate(sorted(pairs, key=lambda x: x[1])):
        out.append((k, min(1.0, max(0.0, (m - i) * p))))
    d = dict(out)
    return [(k, d[k]) for k, _ in pairs]


def table_quality(rows):
    ns = nonstable(rows)
    d = by_method(ns)
    lru = mean(float(r["miss_ratio"]) for r in d["LRU"])
    print("=== TABLE VI: mean miss ratio by scenario (non-stable) ===")
    print(f"{'Method':12} {'abrupt':>7} {'gradual':>7} {'recurring':>9} {'composite':>9} {'overall':>18} {'vs LRU%':>8}")
    for m in METHOD_ORDER:
        cells = []
        for s in ["abrupt", "gradual", "recurring", "composite"]:
            cells.append(mean(float(r["miss_ratio"]) for r in d[m] if r["scenario"] == s))
        allv = [float(r["miss_ratio"]) for r in d[m]]
        lo, hi = boot_ci(allv)
        pct = 100 * (1 - mean(allv) / lru)
        print(f"{m:12} " + " ".join(f"{v:7.3f}" if i < 2 else f"{v:9.3f}" for i, v in enumerate(cells))
              + f"  {mean(allv):.3f} [{lo:.3f}, {hi:.3f}]" + f" {pct:8.1f}")
    print()


def table_paired(rows):
    ns = nonstable(rows)
    d = by_method(ns)
    da = {r["seed"]: float(r["miss_ratio"]) for r in d["DA"]}
    base = ["LRU", "FIFO", "CLOCK", "LFU-A", "2Q", "ARC", "S3-FIFO", "LeCaR", "LPR-style", "ContShadow"]
    print("=== TABLE VII: paired DA minus baseline (negative favours DA) ===")
    raw = []
    for m in base:
        other = {r["seed"]: float(r["miss_ratio"]) for r in d[m]}
        diffs = [da[s] - other[s] for s in da if s in other]
        lo, hi = boot_ci(diffs)
        w, l, t = sum(x < 0 for x in diffs), sum(x > 0 for x in diffs), sum(x == 0 for x in diffs)
        p = wilcoxon(diffs)
        raw.append((m, p))
        print(f"{m:12} {mean(diffs):+.4f} [{lo:+.4f}, {hi:+.4f}]  W/L/T={w}/{l}/{t}  p={p:.4g}")
    print("\nHolm-adjusted:")
    for m, p in holm(raw):
        print(f"  {m:12} {p:.4g}")
    print()


def table_ablation(rows):
    ns = nonstable(rows)
    d = by_method(ns)
    print("=== ABLATION: mean miss ratio, switches, shadow evals, ns/ref ===")
    for m in ABLATIONS:
        if m not in d:
            continue
        r = d[m]
        print(f"{m:12} miss={mean(float(x['miss_ratio']) for x in r):.3f} "
              f"sw={mean(float(x['switches']) for x in r):.2f} "
              f"ev={mean(float(x['shadow_evals']) for x in r):.2f} "
              f"ns={mean(float(x['ns_per_ref']) for x in r):.1f}")
    print()


def table_cost(rows):
    ns = nonstable(rows)
    d = by_method(ns)
    print("=== COST: mean switches / shadow evals / ns per ref (non-stable) ===")
    for m in ["LRU", "S3-FIFO", "LPR-style", "ContShadow", "DA"]:
        r = d[m]
        print(f"{m:12} sw={mean(float(x['switches']) for x in r):.2f} "
              f"ev={mean(float(x['shadow_evals']) for x in r):.2f} "
              f"ns={mean(float(x['ns_per_ref']) for x in r):.1f}")
    print()


def table_detection(det):
    print("=== DETECTION ===")
    ns = [r for r in det if r["scenario"] in NONSTABLE]
    nb = sum(int(r["n_bounds"]) for r in ns)
    detn = sum(int(r["detected"]) for r in ns)
    delays = [int(x) for r in ns for x in r["delays"].split(";") if x]
    spur = sum(int(r["spurious"]) for r in ns)
    stable = [r for r in det if r["scenario"] == "stable"]
    f100 = sum(int(r["false_after_100k"]) for r in stable)
    print(f"boundaries={nb} detected={detn} rate={100*detn/nb:.1f}% "
          f"median_delay={median(delays):.0f} spurious={spur} "
          f"stable_false_after_100k={f100}")
    print()


def capacity_tables():
    print("=== CAPACITY / SAMPLING SENSITIVITY (DA only) ===")
    for label, path in [("C=500", "main_study_C500.csv"), ("C=1000", "main_study_results.csv"),
                        ("C=2000", "main_study_C2000.csv"), ("p=0.05", "main_study_p005.csv"),
                        ("p=0.1", "main_study_p01.csv"), ("p=0.2", "main_study_results.csv")]:
        try:
            rows = nonstable(load(path))
        except FileNotFoundError:
            continue
        d = by_method(rows)
        da = mean(float(r["miss_ratio"]) for r in d["DA"])
        lru = mean(float(r["miss_ratio"]) for r in d["LRU"])
        print(f"{label:8} DA={da:.3f} LRU={lru:.3f} S3={mean(float(r['miss_ratio']) for r in d['S3-FIFO']):.3f} "
              f"ContShadow={mean(float(r['miss_ratio']) for r in d['ContShadow']):.3f}")
    print()


if __name__ == "__main__":
    rows = load("main_study_results.csv")
    det = load("main_study_detection.csv")
    table_quality(rows)
    table_paired(rows)
    table_ablation(rows)
    table_cost(rows)
    table_detection(det)
    capacity_tables()
