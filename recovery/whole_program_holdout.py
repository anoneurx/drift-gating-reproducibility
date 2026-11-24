#!/usr/bin/env python3
"""Leave-one-program-out evaluation on the instrumented real-program traces.

Protocol (fixes the seed-level leakage noted in the review):
  * Ten programs x four seeds = 40 traces.
  * For each fold, one *whole program* is held out. All tunable baselines and
    the DA controller are tuned on the other nine programs only (36 traces).
  * The selected configuration is evaluated once on the four traces of the
    held-out program. No tuning trace from the held-out program is used.
  * The program, not the seed, is the independent unit; ten folds give
    limited inferential power, so per-program values are reported directly.

Run: python3 whole_program_holdout.py (from recovery/ or from the
standalone reproduction/ package). Requires a compiled sim_full binary and
traces_real/*.bin in the same directory; generate the latter with real_traces.
"""
import csv, itertools, os, subprocess, tempfile
from collections import defaultdict
from statistics import mean

HERE = os.path.dirname(os.path.abspath(__file__))
# Works both from recovery/ (one level below the simulator) and from a
# standalone reproduction/ package (next to the simulator).
ROOT = HERE if os.path.exists(os.path.join(HERE, "sim_full.cpp")) else os.path.dirname(HERE)
SIM = os.path.join(ROOT, "sim_full")
if not os.path.exists(SIM):
    SIM = os.path.join(HERE, "sim_full")
PROGRAMS = ["btree", "hashjoin", "bfs", "sort", "stencil", "sparse", "heap", "radix", "pagerank", "hashmap"]
SEEDS = ["", "_s101", "_s202", "_s303"]
TMP = tempfile.mkdtemp(prefix="opo_")


def trace(p, sd):
    return os.path.join(ROOT, "traces_real", p + sd + ".bin")


def run(files, extra, out):
    cmd = [SIM]
    for f in files:
        cmd += ["--trace", f]
    # Defaults first: the simulator uses last-wins parsing, so tuned values in
    # `extra` must come after them (otherwise DA's candidate-set tuning is lost).
    cmd += ["--warm", "100000", "--ncand", "5", "--kfrac", "0"] + extra + \
           ["--out", out, "--det", out + ".det"]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    d = defaultdict(list)
    for r in csv.DictReader(open(out)):
        d[r["method"]].append(float(r["miss_ratio"]))
    return {m: mean(v) for m, v in d.items()}


GRIDS = {
    "S3-FIFO": ("--s3frac", [0.05, 0.1]),
    "2Q": ("--twoqkin", [125, 500]),
    "LPR-style": ("--lprthr", [0.05, 0.1]),
    "LeCaR": ("--lecarlr", [0.45, 0.6]),
    "LIRS": ("--lirsfrac", [0.05, 0.1]),
}
BASE = ["--s3frac", "0.05", "--twoqkin", "125", "--lprthr", "0.1",
        "--lecarlr", "0.6", "--lirsfrac", "0.05"]


def main():
    folds = {}
    for held in PROGRAMS:
        train = [trace(p, sd) for p in PROGRAMS if p != held for sd in SEEDS]
        test = [trace(held, sd) for sd in SEEDS]
        chosen = dict(zip(BASE[::2], BASE[1::2]))
        for method, (flag, vals) in GRIDS.items():
            opts = []
            for v in vals:
                extra = dict(chosen)
                extra[flag] = v
                a = []
                for k, val in extra.items():
                    a += [k, str(val)]
                res = run(train, a, f"{TMP}/t_{held}_{method}_{v}.csv")
                opts.append((res[method], v))
            opts.sort()
            chosen[flag] = opts[0][1]
        # DA hyper-parameters on training only
        daopts = []
        for nc, kf in itertools.product([4, 5], [0, 0.05]):
            a = []
            for k, val in chosen.items():
                a += [k, str(val)]
            a += ["--ncand", str(nc), "--kfrac", str(kf)]
            res = run(train, a, f"{TMP}/t_{held}_da_{nc}_{kf}.csv")
            daopts.append((res["DA"], nc, kf))
        daopts.sort()
        _, nc, kf = daopts[0]
        final_args = []
        for k, val in chosen.items():
            final_args += [k, str(val)]
        final_args += ["--ncand", str(nc), "--kfrac", str(kf)]
        res = run(test, final_args, f"{TMP}/test_{held}.csv")
        folds[held] = res
        print(f"{held:10} train-DA={daopts[0][0]:.4f} cfg ncand={nc} K={kf}  "
              f"held-out DA={res['DA']:.4f} LRU={res['LRU']:.4f} "
              f"S3={res['S3-FIFO']:.4f} DIP={res['DIP-set-duel']:.4f} "
              f"MGLRU={res['MGLRU-style']:.4f}", flush=True)
    out = os.path.join(HERE, "whole_program_holdout_results.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["held_out_program"] + sorted(next(iter(folds.values()))))
        for p, r in folds.items():
            w.writerow([p] + [f"{r[m]:.5f}" for m in sorted(r)])
    print("\n=== mean over ten whole-program folds ===")
    for m in ["OPT", "S3-FIFO", "DA", "ContShadow", "DIP-set-duel",
              "MGLRU-style", "2Q", "CAR", "LIRS", "CLOCK-Pro", "CACHEUS",
              "3L-style", "ARC", "LPR-style", "LRU"]:
        if m in next(iter(folds.values())):
            vals = [r[m] for r in folds.values()]
            print(f"  {m:14} {mean(vals):.4f}  per-program: " +
                  " ".join(f"{v:.3f}" for v in vals))
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
