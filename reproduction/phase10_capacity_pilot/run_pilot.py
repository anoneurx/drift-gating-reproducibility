#!/usr/bin/env python3
"""Run the pre-registered Phase 10 capacity grid with the released simulator."""
import csv
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPRO = os.path.dirname(HERE)
SIM = os.path.join(REPRO, "sim_full")
TRACE = os.path.join(HERE, "webusers.bin")
CAPS = [1000, 5000, 10000, 15000, 20000, 25000, 50000]
METHODS = "LRU,S3-FIFO,DA"


def main():
    results = []
    for c in CAPS:
        out = os.path.join(HERE, f"C{c}.csv")
        det = os.path.join(HERE, f"C{c}_det.csv")
        err = os.path.join(HERE, f"C{c}.stderr")
        cmd = [SIM, "--seed", "0", "--np", "1048576", "--C", str(c),
               "--W", "2000", "--warm", "100000", "--p", "0.2",
               "--ncand", "5", "--kfrac", "0", "--z", "1.28", "--edelay", "10",
               "--methods", METHODS, "--trace", TRACE,
               "--out", out, "--det", det]
        with open(err, "w") as ef:
            p = subprocess.run(cmd, cwd=REPRO, stdout=subprocess.DEVNULL, stderr=ef)
        if p.returncode != 0:
            raise RuntimeError(f"C={c}: simulator exit {p.returncode}; see {err}")
        results.append({"C": c, "command": " ".join(cmd),
                        "out": out, "det": det, "stderr": err})
    with open(os.path.join(HERE, "commands.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["C", "command", "out", "det", "stderr"])
        w.writeheader()
        w.writerows(results)
    print(f"ran {len(results)} simulator invocations", file=sys.stderr)


if __name__ == "__main__":
    main()
