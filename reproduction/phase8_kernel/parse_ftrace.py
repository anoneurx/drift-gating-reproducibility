#!/usr/bin/env python3
"""Parse guest function_graph traces into measured per-function durations."""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
OUT = os.path.join(HERE, "ftrace_durations.csv")
FUNCS = set()
with open(os.path.join(HERE, "results", "ftrace_functions.txt")) as fh:
    FUNCS = {ln.strip() for ln in fh if ln.strip()}

LINE = re.compile(r"^\s*\d+\)\s+([+!*+-]?\s*[0-9]+(?:\.[0-9]+)?)\s*(ns|us|ms)\s+\|\s+([A-Za-z_][A-Za-z0-9_.]*)\(\);")
MUL = {"ns": 1.0, "us": 1000.0, "ms": 1000000.0}


def main():
    n = 0
    with open(OUT, "w", newline="") as out:
        w = csv.writer(out)
        w.writerow(["condition", "rep", "function", "duration_ns"])
        for cond in ("fixed_lru", "fixed_mglru", "coupled"):
            for rep in range(1, 4):
                path = os.path.join(RESULTS, cond, str(rep), "ftrace.txt")
                if not os.path.exists(path):
                    continue
                with open(path, errors="replace") as fh:
                    for line in fh:
                        m = LINE.match(line)
                        if not m:
                            continue
                        fn = m.group(3)
                        if fn not in FUNCS:
                            continue
                        raw = m.group(1)
                        val = float(re.sub(r"[+!*\s]", "", raw))
                        w.writerow([cond, rep, fn, val * MUL[m.group(2)]])
                        n += 1
    print(f"parsed {n} ftrace duration samples into {OUT}")


if __name__ == "__main__":
    main()
