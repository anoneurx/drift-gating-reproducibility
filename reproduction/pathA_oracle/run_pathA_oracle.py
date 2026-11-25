#!/usr/bin/env python3
"""Run the pre-specified Path A policy-switching oracle on all local real traces.

This script is additive. It never modifies frozen artifacts or the authoritative
simulator. It builds the oracle binary if needed, enumerates every replayable
real/public trace, runs all capacities and window lengths in parallel, and writes
raw CSVs under reproduction/pathA_oracle/results/.
"""
import argparse
import csv
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BIN = HERE / "oracle_switching"
RESULTS = HERE / "results"
TMP_ROOT = Path("/tmp/opencode/pathA_tmp")

SUMMARY_FIELDS = [
    "trace", "family", "source", "C", "wss", "refs", "warm", "window", "nwin",
    "switch_cost", "best_static", "best_static_total_miss",
    "best_static_miss_ratio", "oracle_total_miss", "oracle_miss_ratio",
    "oracle_switches", "oracle_objective_ratio", "gain_miss_abs", "gain_miss_rel",
    "gain_objective_abs", "gain_objective_rel",
]
POLICY_FIELDS = ["trace", "family", "source", "C", "window", "policy", "total_miss", "miss_ratio"]
WINDOW_FIELDS = [
    "trace", "family", "source", "C", "window", "window_idx", "chosen_policy",
    "chosen_misses", "did_switch", "best_window_policy", "best_window_misses",
]
MANIFEST_FIELDS = ["trace", "family", "source", "path", "refs", "wss", "max_id", "np", "capacities"]


def trace_info(path):
    ids = np.fromfile(path, dtype="<u4")
    if ids.size == 0:
        raise ValueError(f"empty trace: {path}")
    max_id = int(ids.max())
    wss = int(np.unique(ids).size)
    caps = [max(1, round(wss * f)) for f in (0.01, 0.05, 0.10)]
    return {
        "refs": int(ids.size), "wss": wss, "max_id": max_id,
        "np": max_id + 1, "capacities": ";".join(map(str, caps)),
    }


def discover():
    out = []
    for p in sorted((ROOT / "traces_real").glob("*.bin")):
        stem = p.stem
        family = stem.split("_")[0]
        out.append(("prog_" + stem, family, "instrumented_program", p))
    for p in sorted((ROOT / "reproduction" / "public_split").glob("*.bin")):
        stem = p.stem
        body = stem[len("fiu_"):] if stem.startswith("fiu_") else stem
        family = "fiu_" + body.split("-")[0]
        suffix = "test" if stem.endswith(".test") else "train"
        out.append(("fiu_" + body.split("-")[0] + "_" + suffix, family, "fiu_public", p))
    for p in sorted((ROOT / "reproduction" / "phase6_pdl").glob("*.bin")):
        family = "pdl_" + p.stem
        out.append((family, family, "pdl_public", p))
    # Exclude the phase-10 capacity-pilot trace: capacity was selected on it.
    return out


def run_one(job):
    label, family, source, path, cap, window, info = job
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TMP_ROOT) as td:
        s = Path(td) / "summary.csv"
        q = Path(td) / "policy.csv"
        w = Path(td) / "windows.csv"
        cmd = [
            str(BIN),
            "--trace", str(path), "--label", label, "--family", family,
            "--source", source, "--C", str(cap), "--np", str(info["np"]),
            "--window", str(window), "--out-summary", str(s),
            "--out-policy", str(q), "--out-windows", str(w),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"{label} C={cap} window={window} failed: {proc.stderr.strip()}")
        def read(p):
            with open(p, newline="") as fh:
                rdr = csv.DictReader(fh)
                return list(rdr)
        return read(s), read(q), read(w)


def write_csv(path, fields, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="50000", help="comma-separated window lengths")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0, help="debug: run first N traces")
    ap.add_argument("--results-dir", default=str(RESULTS), help="output directory")
    args = ap.parse_args()
    out_dir = Path(args.results_dir)
    windows = [int(x) for x in args.windows.split(",") if x]

    if not BIN.exists():
        raise SystemExit(f"missing oracle binary: {BIN}; build it first")

    traces = discover()
    if args.limit:
        traces = traces[:args.limit]
    print(f"discovered {len(traces)} traces; windows={windows}")

    jobs, manifest = [], []
    for label, family, source, path in traces:
        info = trace_info(path)
        row = {"trace": label, "family": family, "source": source, "path": str(path)}
        row.update(info)
        manifest.append(row)
        for cap in [int(x) for x in info["capacities"].split(";")]:
            for window in windows:
                jobs.append((label, family, source, path, cap, window, info))
    print(f"jobs: {len(jobs)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    summaries, policies, window_rows = [], [], []
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_one, j): j for j in jobs}
        for fut in as_completed(futs):
            s, q, w = fut.result()
            summaries.extend(s)
            policies.extend(q)
            window_rows.extend(w)
            done += 1
            if done % 50 == 0:
                print(f"completed {done}/{len(jobs)}")

    summaries.sort(key=lambda r: (r["trace"], int(r["C"]), int(r["window"]), float(r["switch_cost"])))
    policies.sort(key=lambda r: (r["trace"], int(r["C"]), int(r["window"]), r["policy"]))
    window_rows.sort(key=lambda r: (r["trace"], int(r["C"]), int(r["window"]), int(r["window_idx"])))
    manifest.sort(key=lambda r: r["trace"])

    write_csv(out_dir / "summary.csv", SUMMARY_FIELDS, summaries)
    write_csv(out_dir / "policy.csv", POLICY_FIELDS, policies)
    write_csv(out_dir / "windows.csv", WINDOW_FIELDS, window_rows)
    write_csv(out_dir / "manifest.csv", MANIFEST_FIELDS, manifest)
    print(f"wrote {len(summaries)} summary rows, {len(policies)} policy rows, "
          f"{len(window_rows)} window rows")


if __name__ == "__main__":
    sys.exit(main())
