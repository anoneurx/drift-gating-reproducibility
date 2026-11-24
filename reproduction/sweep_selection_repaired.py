#!/usr/bin/env python3
"""Post-hoc repaired controller-selection sweep.

Same grid/rule as sweep_selection.py (Section V-B), but enables the
pre-specified capacity-sampling repair: --cs-cap-f 1.0, where
Cs = min(round(p*C), round(f * D_w)), D_w = distinct sampled pages in the
evaluation window, f=1.0 fixed a priori. Run only on training traces
(seed 100). Test traces (seed 5001) are not touched.

Selection rule: among configurations with zero false confirmations on stable
training traces after reference 100,000, choose the lowest mean non-stable
training miss ratio.  Ties broken by smaller candidate set, then smaller K,
then smaller evaluation delay.
"""
import argparse
import concurrent.futures as cf
import csv
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(HERE, "sim_full")
RAW = os.path.join(HERE, "sweep_repaired_raw")
NONSTABLE = ("abrupt", "gradual", "recurring", "composite")
NCAND = (4, 5, 6)
KFRAC = (0.0, 0.05, 0.1, 0.2)
EDELAY = (2, 5, 10, 20)
SEED = 100
Z = 1.28
CS_CAP_F = 1.0


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def run_one(cfg):
    ncand, kfrac, edelay = cfg
    tag = f"nc{ncand}_k{kfrac:g}_e{edelay}"
    out = os.path.join(RAW, tag + ".csv")
    det = os.path.join(RAW, tag + "_det.csv")
    cmd = [
        SIM,
        "--seed", str(SEED),
        "--stable-per-prim", "3",
        "--per-scenario", "8",
        "--da-only",
        "--ncand", str(ncand),
        "--kfrac", str(kfrac),
        "--z", str(Z),
        "--edelay", str(edelay),
        "--cs-cap-f", str(CS_CAP_F),
        "--out", out,
        "--det", det,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    rows = list(csv.DictReader(open(out)))
    da = [r for r in rows if r["method"] == "DA"]
    ns = [float(r["miss_ratio"]) for r in da if r["scenario"] in NONSTABLE]
    st = [float(r["miss_ratio"]) for r in da if r["scenario"] == "stable"]
    drows = list(csv.DictReader(open(det)))
    stable_false = sum(int(r["false_after_100k"]) for r in drows
                       if r["scenario"] == "stable")
    spur = sum(int(r["spurious"]) for r in drows
               if r["scenario"] in NONSTABLE)
    nb = sum(int(r["n_bounds"]) for r in drows
             if r["scenario"] in NONSTABLE)
    detn = sum(int(r["detected"]) for r in drows
               if r["scenario"] in NONSTABLE)
    return {
        "ncand": ncand,
        "kfrac": kfrac,
        "edelay": edelay,
        "train_miss_nonstable": mean(ns),
        "train_miss_stable": mean(st),
        "stable_false_after_100k": stable_false,
        "spurious": spur,
        "detected": detn,
        "boundaries": nb,
        "detection_rate": (100.0 * detn / nb) if nb else 0.0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)
    cfgs = [(n, k, e) for n in NCAND for k in KFRAC for e in EDELAY]
    print(f"Running {len(cfgs)} repaired configurations with {args.jobs} workers (cs-cap-f={CS_CAP_F}) ...", file=sys.stderr)
    results = []
    with cf.ProcessPoolExecutor(max_workers=args.jobs) as ex:
        for r in ex.map(run_one, cfgs):
            print(f"  ncand={r['ncand']} K={r['kfrac']:g} delay={r['edelay']}: train={r['train_miss_nonstable']:.4f} stable_false={r['stable_false_after_100k']} spurious={r['spurious']}", file=sys.stderr)
            results.append(r)
    out = os.path.join(HERE, "sweep_repaired_results.csv")
    fields = ["ncand", "kfrac", "edelay", "train_miss_nonstable", "train_miss_stable", "stable_false_after_100k", "spurious", "detected", "boundaries", "detection_rate"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow({k: (f"{r[k]:.5f}" if isinstance(r[k], float) else r[k]) for k in fields})
    eligible = [r for r in results if r["stable_false_after_100k"] == 0]
    if not eligible:
        print("No eligible configuration.", file=sys.stderr)
        sys.exit(1)
    best = min(eligible, key=lambda r: (r["train_miss_nonstable"], r["ncand"], r["kfrac"], r["edelay"]))
    print(f"\nSelected: ncand={best['ncand']} K={best['kfrac']:g} edelay={best['edelay']} train={best['train_miss_nonstable']:.4f}")
    with open(os.path.join(HERE, "sweep_repaired_selected.txt"), "w") as f:
        f.write(f"ncand={best['ncand']}\n")
        f.write(f"kfrac={best['kfrac']:g}\n")
        f.write(f"edelay={best['edelay']}\n")
        f.write(f"z={Z}\n")
        f.write(f"csCapF={CS_CAP_F}\n")
        f.write(f"train_miss_nonstable={best['train_miss_nonstable']:.5f}\n")
        f.write(f"stable_false_after_100k={best['stable_false_after_100k']}\n")
    print(f"Wrote {out} and sweep_repaired_selected.txt")


if __name__ == "__main__":
    main()
