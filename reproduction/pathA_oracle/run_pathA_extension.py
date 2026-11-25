#!/usr/bin/env python3
"""Run the pre-specified Path A extension on the new FIU traces.

Uses the same oracle binary and settings as the primary experiment. Input is the
manifest written by prepare_pathA_extension.py; output is results_extension/.
"""
import argparse
import csv
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from run_pathA_oracle import BIN, RESULTS, SUMMARY_FIELDS, POLICY_FIELDS, WINDOW_FIELDS, run_one, write_csv

HERE = Path(__file__).resolve().parent
EXT = HERE / "results_extension"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="50000,100000")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    windows = [int(x) for x in args.windows.split(",") if x]
    if not BIN.exists():
        raise SystemExit(f"missing oracle binary: {BIN}")

    with open(EXT / "manifest.csv", newline="") as fh:
        manifest = list(csv.DictReader(fh))
    jobs = []
    for m in manifest:
        info = {"np": int(m["np"])}
        for cap in (int(x) for x in m["capacities"].split(";")):
            for window in windows:
                jobs.append((m["trace"], m["family"], m["source"], m["path"],
                             cap, window, info))
    print(f"extension traces: {len(manifest)}; jobs: {len(jobs)}; windows={windows}")

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
            if done % 20 == 0:
                print(f"completed {done}/{len(jobs)}", flush=True)

    summaries.sort(key=lambda r: (r["trace"], int(r["C"]), int(r["window"]), float(r["switch_cost"])))
    policies.sort(key=lambda r: (r["trace"], int(r["C"]), int(r["window"]), r["policy"]))
    window_rows.sort(key=lambda r: (r["trace"], int(r["C"]), int(r["window"]), int(r["window_idx"])))
    write_csv(EXT / "summary.csv", SUMMARY_FIELDS, summaries)
    write_csv(EXT / "policy.csv", POLICY_FIELDS, policies)
    write_csv(EXT / "windows.csv", WINDOW_FIELDS, window_rows)
    print(f"wrote {len(summaries)} summary rows, {len(policies)} policy rows, "
          f"{len(window_rows)} window rows")


if __name__ == "__main__":
    sys.exit(main())
