#!/usr/bin/env python3
"""Run fine cost sweep (0..1.0C x W=5k..50k), 25%/50% WSS oracle, shadow ranking accuracy, and ContShadow-21."""
import csv
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BIN = HERE / "pathA_sim"
RESULTS = HERE / "results"
TMP_ROOT = Path("/tmp/opencode/pathA_rev_tmp")


def run_cmd(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def run_trace_finesweep(row):
    p = Path(row["path"])
    if not p.is_absolute():
        p = ROOT / p
    wss = int(row["wss"])
    out = []
    # 1. Existing 1%, 5%, 10% WSS across W in {5000, 10000, 25000, 50000}
    for tok in row["capacities"].split(";"):
        cf, cap = tok.split(":")
        for w in (5000, 10000, 25000, 50000):
            TMP_ROOT.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=TMP_ROOT) as td:
                pref = Path(td) / "out"
                run_cmd([str(BIN), "--mode", "finesweep", "--trace", str(p), "--label", row["trace"],
                         "--family", row["family"], "--source", row["source"], "--cap-frac", cf,
                         "--C", cap, "--np", row["np"], "--window", str(w), "--out-prefix", str(pref)])
                with open(str(pref) + "_finesweep.csv", newline="") as fh:
                    out.extend(list(csv.DictReader(fh)))
    # 2. High capacities 25%, 50% WSS at W=50000
    for f in (0.25, 0.50):
        cap = max(1, round(wss * f))
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as td:
            pref = Path(td) / "out"
            run_cmd([str(BIN), "--mode", "finesweep", "--trace", str(p), "--label", row["trace"],
                     "--family", row["family"], "--source", row["source"], "--cap-frac", f"{f:.2f}",
                     "--C", str(cap), "--np", row["np"], "--window", "50000", "--out-prefix", str(pref)])
            with open(str(pref) + "_finesweep.csv", newline="") as fh:
                out.extend(list(csv.DictReader(fh)))
    return out


def run_trace_ranking(row):
    p = Path(row["path"])
    if not p.is_absolute():
        p = ROOT / p
    ranks, p21 = [], []
    for tok in row["capacities"].split(";"):
        cf, cap = tok.split(":")
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as td:
            pref = Path(td) / "out"
            run_cmd([str(BIN), "--mode", "ranking", "--trace", str(p), "--label", row["trace"],
                     "--family", row["family"], "--source", row["source"], "--cap-frac", cf,
                     "--C", cap, "--np", row["np"], "--window", "50000", "--out-prefix", str(pref)])
            with open(str(pref) + "_ranking.csv", newline="") as fh:
                ranks.extend(list(csv.DictReader(fh)))
            with open(str(pref) + "_pool21.csv", newline="") as fh:
                p21.extend(list(csv.DictReader(fh)))
    return ranks, p21


def main():
    with open(RESULTS / "manifest.csv", newline="") as fh:
        manifest = list(csv.DictReader(fh))

    fs_rows = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(run_trace_finesweep, m) for m in manifest]
        for f in as_completed(futs):
            fs_rows.extend(f.result())
    fs_rows.sort(key=lambda r: (r["trace"], r["cap_frac"], int(r["window"]), float(r["cost_frac"])))
    with open(RESULTS / "finesweep.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fs_rows[0].keys()))
        w.writeheader()
        w.writerows(fs_rows)
    print(f"Wrote {len(fs_rows)} rows to finesweep.csv")

    rk_rows, p21_rows = [], []
    with ProcessPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(run_trace_ranking, m) for m in manifest]
        for f in as_completed(futs):
            rk, p21 = f.result()
            rk_rows.extend(rk)
            p21_rows.extend(p21)
    rk_rows.sort(key=lambda r: (r["trace"], r["cap_frac"], r["mode"]))
    p21_rows.sort(key=lambda r: (r["trace"], r["cap_frac"]))
    with open(RESULTS / "shadow_ranking.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rk_rows[0].keys()))
        w.writeheader()
        w.writerows(rk_rows)
    with open(RESULTS / "pool21.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(p21_rows[0].keys()))
        w.writeheader()
        w.writerows(p21_rows)
    print(f"Wrote {len(rk_rows)} rows to shadow_ranking.csv and {len(p21_rows)} rows to pool21.csv")


if __name__ == "__main__":
    main()
