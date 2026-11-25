#!/usr/bin/env python3
"""Apply the pre-specified Path A extension decision rule."""
import csv
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXT = HERE / "results_extension"
ONLINE_FAMILY = "fiu_online"
UNSEEN = {"fiu_casa", "fiu_webmail_online_combined"}


def load(name):
    with open(EXT / name, newline="") as fh:
        return list(csv.DictReader(fh))


def truth(v):
    return str(v).strip().lower() in {"true", "1", "yes"}


def main():
    summary = load("summary.csv")
    aggregate = load("aggregate_family.csv")

    charged = [r for r in summary if float(r["switch_cost"]) > 0]
    by_window = defaultdict(list)
    for r in charged:
        by_window[int(r["window"])].append(r)

    online_replicas = sorted({
        r["trace"] for r in by_window[100000]
        if r["family"] == ONLINE_FAMILY and float(r["gain_miss_abs"]) >= 0.02
    })
    unseen_groups = [
        r for r in aggregate
        if int(r["window"]) == 100000 and r["family"] in UNSEEN and truth(r["threshold_met"])
    ]

    cond1 = len(online_replicas) >= 2
    cond2 = bool(unseen_groups)
    decision = "PATH_B_GATE_SURVIVES_EXTENSION" if cond1 and cond2 else "PATH_A_STANDS"

    out = {
        "decision": decision,
        "online_replicas_required": 2,
        "online_replicas_found": len(online_replicas),
        "online_replica_traces": ";".join(online_replicas),
        "unseen_group_required": 1,
        "unseen_groups_found": len(unseen_groups),
        "unseen_groups": ";".join(
            f"{r['family']}|C={r['C']}" for r in unseen_groups
        ),
        "charged_50k_groups_met": sum(
            truth(r["threshold_met"]) for r in aggregate if int(r["window"]) == 50000
        ),
        "charged_100k_groups_met": sum(
            truth(r["threshold_met"]) for r in aggregate if int(r["window"]) == 100000
        ),
        "n_groups": len(aggregate),
    }
    with open(EXT / "extension_decision.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out))
        w.writeheader()
        w.writerow(out)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
