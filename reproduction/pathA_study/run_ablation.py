#!/usr/bin/env python3
"""Run FullShadow (p=1.0, Cs=C) and FullShadow-CostAware (K=C) ablation across all 264 pairs."""
import csv
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BIN = HERE / "pathA_sim"
RESULTS = HERE / "results"
TMP_ROOT = Path("/tmp/opencode/pathA_ablation_tmp")


def run_one(row):
    p = Path(row["path"])
    if not p.is_absolute():
        p = ROOT / p
    jobs = []
    for tok in row["capacities"].split(";"):
        cf, cap = tok.split(":")
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as td:
            pref = Path(td) / "out"
            cmd = [
                str(BIN), "--mode", "ablation",
                "--trace", str(p), "--label", row["trace"],
                "--family", row["family"], "--source", row["source"],
                "--cap-frac", cf, "--C", cap, "--np", row["np"],
                "--window", "50000", "--out-prefix", str(pref),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            with open(str(pref) + "_ablation.csv", newline="") as fh:
                jobs.extend(list(csv.DictReader(fh)))
    return jobs


def main():
    with open(RESULTS / "manifest.csv", newline="") as fh:
        manifest = list(csv.DictReader(fh))
    rows = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(run_one, m) for m in manifest]
        for f in as_completed(futs):
            rows.extend(f.result())
    rows.sort(key=lambda r: (r["trace"], r["cap_frac"], r["controller"]))
    out_path = RESULTS / "shadow_ablation.csv"
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
