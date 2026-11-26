#!/usr/bin/env python3
"""Run c_switch sensitivity sweep (W=10k, 25k, 50k) and controller failure-mode diagnostics."""
import csv
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BIN = HERE / "pathA_sim"
RESULTS = HERE / "results"


def run_job(args):
    label, family, source, path, cap_frac, cap, np_sz, window, mode = args
    with tempfile.TemporaryDirectory(prefix="pA_sens_") as td:
        pref = Path(td) / "out"
        cmd = [
            str(BIN),
            "--trace", str(path),
            "--label", label,
            "--family", family,
            "--source", source,
            "--cap-frac", cap_frac,
            "--C", str(cap),
            "--np", str(np_sz),
            "--window", str(window),
            "--mode", mode,
            "--out-prefix", str(pref),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"{label} C={cap} w={window} {mode} failed: {proc.stderr.strip()}")
        out = {}
        for tag in ("cost_sweep", "ctrl_diag"):
            fp = Path(str(pref) + f"_{tag}.csv")
            if fp.exists():
                with open(fp, newline="") as fh:
                    out[tag] = list(csv.DictReader(fh))
        return out


def write_csv(path: Path, rows):
    if not rows:
        return
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    manifest = list(csv.DictReader(open(RESULTS / "manifest.csv")))
    jobs_oracle = []
    jobs_diag = []
    for m in manifest:
        path = ROOT / m["path"]
        np_sz = int(m["np"])
        for item in m["capacities"].split(";"):
            cf, cap = item.split(":")
            cap = int(cap)
            for w in (10000, 25000, 50000):
                jobs_oracle.append((m["trace"], m["family"], m["source"], path, cf, cap, np_sz, w, "oracle"))
            jobs_diag.append((m["trace"], m["family"], m["source"], path, cf, cap, np_sz, 50000, "diag"))

    sweep_rows = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(run_job, j) for j in jobs_oracle]
        for i, fut in enumerate(as_completed(futs), 1):
            sweep_rows.extend(fut.result().get("cost_sweep", []))
            if i % 150 == 0 or i == len(jobs_oracle):
                print(f"cost_sweep: {i}/{len(jobs_oracle)}")

    diag_rows = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(run_job, j) for j in jobs_diag]
        for i, fut in enumerate(as_completed(futs), 1):
            diag_rows.extend(fut.result().get("ctrl_diag", []))
            if i % 100 == 0 or i == len(jobs_diag):
                print(f"ctrl_diag: {i}/{len(jobs_diag)}")

    sweep_rows.sort(key=lambda r: (r["trace"], float(r["cap_frac"]), int(r["window"]), float(r["cost_frac"])))
    diag_rows.sort(key=lambda r: (r["trace"], float(r["cap_frac"]), r["controller"]))
    write_csv(RESULTS / "cost_sweep.csv", sweep_rows)
    write_csv(RESULTS / "ctrl_diag.csv", diag_rows)
    print(f"wrote cost_sweep={len(sweep_rows)}, ctrl_diag={len(diag_rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
