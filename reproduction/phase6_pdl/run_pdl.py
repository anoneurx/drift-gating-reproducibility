#!/usr/bin/env python3
"""Run frozen simulator methods on the pre-registered PDL prefixes."""
import csv
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPRO = os.path.dirname(HERE)
SIM = os.path.join(REPRO, "sim_full")
MANIFEST = os.path.join(HERE, "manifest.csv")
RAW = os.path.join(HERE, "raw")
METHODS = "LRU,CLOCK,S3-FIFO,ARC,SIEVE,W-TinyLFU,LHD,ContShadow"


def caps(wss):
    return [max(1, round(0.01 * wss)), max(1, round(0.05 * wss)), max(1, round(0.10 * wss))]


def job(row, c):
    family = row["family"]
    wss = int(row["wss"])
    npv = int(row["max_id"]) + 1
    tag = f"{family}_C{c}"
    out = os.path.join(RAW, tag + ".csv")
    det = os.path.join(RAW, tag + "_det.csv")
    err = os.path.join(RAW, tag + ".stderr")
    cmd = [SIM, "--trace", os.path.join(HERE, family + ".bin"),
           "--C", str(c), "--W", str(2 * c), "--warm", "100000",
           "--np", str(npv), "--ncand", "5", "--kfrac", "0", "--z", "1.28",
           "--edelay", "10", "--methods", METHODS, "--out", out, "--det", det]
    with open(err, "w") as ef:
        p = subprocess.run(cmd, cwd=REPRO, stdout=subprocess.DEVNULL, stderr=ef)
    if p.returncode != 0:
        raise RuntimeError(f"{tag}: simulator exit {p.returncode}; see {err}")
    return {
        "family": family, "C": c, "W": 2 * c, "wss": wss, "np": npv,
        "command": " ".join(cmd), "out": out, "det": det, "stderr": err,
    }


def main():
    jobs = []
    with open(MANIFEST, newline="") as fh:
        for row in csv.DictReader(fh):
            if int(row["records"]) != 1_000_000:
                raise SystemExit(f"{row['family']}: manifest record count is not 1000000")
            for c in caps(int(row["wss"])):
                jobs.append((row, c))
    os.makedirs(RAW, exist_ok=True)
    maxjobs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    results = []
    with ThreadPoolExecutor(max_workers=maxjobs) as ex:
        futs = [ex.submit(job, row, c) for row, c in jobs]
        for fut in futs:
            results.append(fut.result())
    cmdlog = os.path.join(HERE, "commands.csv")
    with open(cmdlog, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["family", "C", "W", "wss", "np", "command", "out", "det", "stderr"])
        w.writeheader()
        w.writerows(results)
    print(f"ran {len(results)} simulator invocations; commands in {cmdlog}")


if __name__ == "__main__":
    main()
