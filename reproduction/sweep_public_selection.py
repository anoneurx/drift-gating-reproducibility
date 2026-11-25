#!/usr/bin/env python3
"""Re-select DA controller parameters on training PREFIXES of the six public
FIU traces, using the released simulator.  The 48-configuration grid is the
same as Section V-B (ncand x Kfrac x evaluation delay); z = 1.28 and C = 20000
(the pilot-chosen capacity) are held fixed.  Because the public traces have no
labelled phase boundaries, the selection rule is simply the lowest mean miss
ratio across the six training prefixes, with the same tie-breaking order as
sweep_selection.py (smaller ncand, then smaller K, then smaller delay).

The frozen configuration is ncand=5, Kfrac=0, edelay=10.
Both the frozen and the re-selected configurations are then evaluated on the
held-out suffixes (see run_public_reselect.sh).
"""
import concurrent.futures as cf
import csv
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(HERE, "sim_full")
SPLIT = os.path.join(HERE, "public_split")
RAW = os.path.join(HERE, "public_sweep_raw")
TRAIN = sorted(f for f in os.listdir(SPLIT) if f.endswith(".train.bin"))
TRACES = [os.path.join(SPLIT, f) for f in TRAIN]
NCAND = (4, 5, 6)
KFRAC = (0.0, 0.05, 0.1, 0.2)
EDELAY = (2, 5, 10, 20)
Z = 1.28
C = 20000


def run_one(cfg):
    ncand, kfrac, edelay = cfg
    tag = f"nc{ncand}_k{kfrac:g}_e{edelay}"
    out = os.path.join(RAW, tag + ".csv")
    det = os.path.join(RAW, tag + "_det.csv")
    cmd = [SIM, "--np", "1048576", "--C", str(C), "--warm", "50000",
           "--ncand", str(ncand), "--kfrac", str(kfrac), "--z", str(Z),
           "--edelay", str(edelay), "--da-only",
           "--s3frac", "0.05", "--twoqkin", "125", "--lprthr", "0.1",
           "--lecarlr", "0.6", "--lirsfrac", "0.05",
           "--out", out, "--det", det]
    for t in TRACES:
        cmd += ["--trace", t]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    rows = [r for r in csv.DictReader(open(out)) if r["method"] == "DA"]
    miss = [float(r["miss_ratio"]) for r in rows]
    sw = [int(r["switches"]) for r in rows]
    return {"ncand": ncand, "kfrac": kfrac, "edelay": edelay,
            "train_miss": sum(miss) / len(miss),
            "train_switches": sum(sw)}


def main():
    if not os.path.exists(SIM):
        print("sim_full not found", file=sys.stderr)
        sys.exit(1)
    os.makedirs(RAW, exist_ok=True)
    cfgs = [(n, k, e) for n in NCAND for k in KFRAC for e in EDELAY]
    print(f"Running {len(cfgs)} configurations on {len(TRACES)} "
          f"public training prefixes ...", file=sys.stderr)
    results = []
    with cf.ProcessPoolExecutor(max_workers=4) as ex:
        for r in ex.map(run_one, cfgs):
            results.append(r)
            print(f"  ncand={r['ncand']} K={r['kfrac']:g} "
                  f"delay={r['edelay']}: train_miss={r['train_miss']:.5f} "
                  f"switches={r['train_switches']}", file=sys.stderr)
    out = os.path.join(HERE, "public_sweep_results.csv")
    fields = ["ncand", "kfrac", "edelay", "train_miss", "train_switches"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow({k: (f"{r[k]:.5f}" if isinstance(r[k], float) else r[k])
                        for k in fields})
    best = min(results, key=lambda r: (r["train_miss"], r["ncand"],
                                       r["kfrac"], r["edelay"]))
    print(f"\nRe-selected: ncand={best['ncand']} K={best['kfrac']:g} "
          f"edelay={best['edelay']} train_miss={best['train_miss']:.5f}")
    with open(os.path.join(HERE, "public_sweep_selected.txt"), "w") as f:
        f.write(f"ncand={best['ncand']}\n")
        f.write(f"kfrac={best['kfrac']:g}\n")
        f.write(f"edelay={best['edelay']}\n")
        f.write(f"z={Z}\n")
        f.write(f"C={C}\n")
        f.write(f"train_miss={best['train_miss']:.5f}\n")


if __name__ == "__main__":
    main()
