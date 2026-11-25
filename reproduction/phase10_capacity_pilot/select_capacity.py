#!/usr/bin/env python3
"""Apply the pre-registered Phase 10 capacity-selection rule exactly once."""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CAPS = [1000, 5000, 10000, 15000, 20000, 25000, 50000]
SAT_FLOOR = 0.01
SEP_MIN = 0.10
FROZEN_C = 20000


def miss(cap, method):
    with open(os.path.join(HERE, f"C{cap}.csv")) as fh:
        for row in csv.DictReader(fh):
            if row["method"] == method:
                return float(row["miss_ratio"])
    raise RuntimeError(f"C={cap}: no {method} row")


def main():
    rows = []
    for c in CAPS:
        lru, s3 = miss(c, "LRU"), miss(c, "S3-FIFO")
        nonsat = lru >= SAT_FLOOR and s3 >= SAT_FLOOR
        sep = lru - s3
        rows.append({"C": c, "lru_miss": lru, "s3_miss": s3,
                     "separation": sep, "both_nonsaturated": nonsat,
                     "primary_ok": nonsat and sep >= SEP_MIN, "selected": 0})
    primary = [r for r in rows if r["primary_ok"]]
    if primary:
        chosen = primary[0]["C"]
        rule = "primary"
    else:
        fallback = [r for r in rows if r["both_nonsaturated"]]
        if not fallback:
            raise RuntimeError("no non-saturated capacity: pilot unusable")
        chosen = fallback[-1]["C"]
        rule = "fallback"
    for r in rows:
        r["selected"] = int(r["C"] == chosen)
    with open(os.path.join(HERE, "selection.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["C", "lru_miss", "s3_miss", "separation",
                                           "both_nonsaturated", "primary_ok", "selected"])
        w.writeheader()
        w.writerows(rows)
    print(f"selected C={chosen} by {rule} rule; matches frozen C={FROZEN_C}: "
          f"{chosen == FROZEN_C}")


if __name__ == "__main__":
    main()
