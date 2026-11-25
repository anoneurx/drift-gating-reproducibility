#!/usr/bin/env python3
"""Read-only verification of the published Path A evidence package.

Checks the frozen primary, sensitivity, and extension CSVs against the values
reported in the Path A result memos and short paper. It creates no data.
"""
import argparse
import csv
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parents[1]
BASE_URL = "https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/fiu"
DIRS = {
    "primary": HERE / "results",
    "sensitivity": HERE / "results_w100000",
    "extension": HERE / "results_extension",
}


class Report:
    def __init__(self):
        self.rows = []

    def check(self, ok, label, detail=""):
        self.rows.append((bool(ok), label, detail))
        print(f"  {'PASS' if ok else 'FAIL'} {label}" + (f": {detail}" if detail else ""))

    def equal(self, actual, expected, label):
        self.check(actual == expected, label, f"actual={actual!r} expected={expected!r}")

    def rounded(self, actual, expected, label, digits=5):
        got = round(float(actual), digits)
        self.check(got == expected, label, f"actual={got} expected={expected}")

    @property
    def ok(self):
        return all(ok for ok, _, _ in self.rows)

    @property
    def passed(self):
        return sum(ok for ok, _, _ in self.rows)


def load(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def truth(value):
    return str(value).strip().lower() in {"true", "1", "yes"}


def charged(rows):
    return [r for r in rows if float(r["switch_cost"]) > 0]


def zero(rows):
    return [r for r in rows if float(r["switch_cost"]) == 0]


def verify_primary(rep):
    d = DIRS["primary"]
    summary, policies, windows = load(d / "summary.csv"), load(d / "policy.csv"), load(d / "windows.csv")
    agg, zagg = load(d / "aggregate_family.csv"), load(d / "aggregate_zero_cost_bound.csv")
    decision = load(d / "decision.csv")[0]
    crows = charged(summary)

    rep.equal(len(summary), 468, "primary summary rows")
    rep.equal(len(policies), 4680, "primary policy rows")
    rep.equal(len(windows), 1542, "primary window rows")
    rep.equal(len(agg), 117, "primary charged groups")
    rep.equal(len(zagg), 117, "primary zero-cost groups")
    rep.equal(len(crows), 234, "primary charged trace-capacity rows")
    rep.equal(decision["decision"], "PATH_A_DECISIVE_NEGATIVE", "primary decision")
    rep.equal(int(decision["n_groups_threshold_met"]), 0, "primary charged groups meeting bar")
    rep.equal(int(decision["n_zero_cost_groups_threshold_met"]), 3, "primary zero-cost groups meeting bar")
    rep.equal(sum(truth(r["threshold_met"]) for r in agg), 0, "primary aggregate threshold flags")
    rep.rounded(max(float(r["mean_gain_miss_abs"]) for r in agg), 0.01355, "primary max charged mean gain")
    rep.rounded(statistics.mean(float(r["gain_miss_abs"]) for r in crows), -0.00130, "primary mean charged row gain")
    rep.rounded(max(float(r["mean_gain_miss_abs"]) for r in zagg), 0.05616, "primary max zero-cost mean gain")
    rep.equal(sum(r["best_static"] == "S3-FIFO" for r in crows), 101, "primary S3-FIFO best rows")


def verify_sensitivity(rep):
    d = DIRS["sensitivity"]
    summary, policies, windows = load(d / "summary.csv"), load(d / "policy.csv"), load(d / "windows.csv")
    agg, zagg = load(d / "aggregate_family.csv"), load(d / "aggregate_zero_cost_bound.csv")
    decision = load(d / "decision.csv")[0]

    rep.equal(len(summary), 468, "sensitivity summary rows")
    rep.equal(len(policies), 4680, "sensitivity policy rows")
    rep.equal(len(windows), 663, "sensitivity window rows")
    rep.equal(len(agg), 117, "sensitivity charged groups")
    rep.equal(decision["decision"], "PATH_B_GATE", "sensitivity decision")
    rep.equal(decision["threshold_groups"], "fiu_online.cs.fiu.edu|C=15539|W=100000", "sensitivity gate group")
    rep.equal(int(decision["n_groups_threshold_met"]), 1, "sensitivity charged groups meeting bar")
    rep.equal(int(decision["n_zero_cost_groups_threshold_met"]), 1, "sensitivity zero-cost groups meeting bar")
    rep.equal(sum(truth(r["threshold_met"]) for r in zagg), 1, "sensitivity zero-cost threshold flags")

    gate = [r for r in charged(summary) if float(r["gain_miss_abs"]) >= 0.02]
    rep.equal(len(gate), 1, "sensitivity charged rows above 0.02")
    if gate:
        row = gate[0]
        rep.equal(row["trace"], "fiu_online.cs.fiu.edu_test", "sensitivity gate trace")
        rep.equal(row["family"], "fiu_online.cs.fiu.edu", "sensitivity gate family")
        rep.equal(int(row["C"]), 15539, "sensitivity gate capacity")
        rep.equal(int(row["window"]), 100000, "sensitivity gate window")
        rep.equal(int(row["oracle_switches"]), 2, "sensitivity gate switches")
        rep.rounded(row["gain_miss_abs"], 0.04449, "sensitivity gate gain")


def verify_extension(rep):
    d = DIRS["extension"]
    manifest = load(d / "manifest.csv")
    summary, policies, windows = load(d / "summary.csv"), load(d / "policy.csv"), load(d / "windows.csv")
    agg, zagg = load(d / "aggregate_family.csv"), load(d / "aggregate_zero_cost_bound.csv")
    decision = load(d / "extension_decision.csv")[0]
    crows, zrows = charged(summary), zero(summary)

    rep.equal(len(manifest), 10, "extension traces")
    rep.equal(len(summary), 120, "extension summary rows")
    rep.equal(len(policies), 1200, "extension policy rows")
    rep.equal(len(windows), 1347, "extension window rows")
    rep.equal(len(agg), 60, "extension charged groups")
    rep.equal(len(zagg), 60, "extension zero-cost groups")
    rep.equal(len(crows), 60, "extension charged trace-capacity-window rows")
    rep.equal(len(zrows), 60, "extension zero-cost trace-capacity-window rows")

    rep.equal(decision["decision"], "PATH_A_STANDS", "extension decision")
    rep.equal(int(decision["online_replicas_required"]), 2, "extension online replicas required")
    rep.equal(int(decision["online_replicas_found"]), 1, "extension online replicas found")
    rep.equal(decision["online_replica_traces"], "fiu_online_seg1p5m_2m", "extension replica trace")
    rep.equal(int(decision["unseen_group_required"]), 1, "extension unseen groups required")
    rep.equal(int(decision["unseen_groups_found"]), 0, "extension unseen groups found")
    rep.equal(int(decision["charged_50k_groups_met"]), 2, "extension charged 50k groups meeting bar")
    rep.equal(int(decision["charged_100k_groups_met"]), 1, "extension charged 100k groups meeting bar")
    rep.equal(int(decision["n_groups"]), 60, "extension decision group count")

    rep.equal(sum(truth(r["threshold_met"]) for r in agg if r["window"] == "50000"), 2, "extension aggregate 50k flags")
    rep.equal(sum(truth(r["threshold_met"]) for r in agg if r["window"] == "100000"), 1, "extension aggregate 100k flags")
    rep.equal(sum(truth(r["threshold_met"]) for r in zagg if r["window"] == "50000"), 9, "extension zero-cost 50k flags")
    rep.equal(sum(truth(r["threshold_met"]) for r in zagg if r["window"] == "100000"), 4, "extension zero-cost 100k flags")

    met_traces = {r["trace"] for r in crows if float(r["gain_miss_abs"]) >= 0.02}
    rep.equal(met_traces, {"fiu_online_seg1p5m_2m"}, "extension charged-gain trace set")
    rep.rounded(statistics.mean(float(r["gain_miss_abs"]) for r in crows), -0.00595, "extension mean charged row gain")
    rep.rounded(statistics.mean(float(r["gain_miss_abs"]) for r in zrows), 0.01085, "extension mean zero-cost row gain")
    rep.equal(sum(r["best_static"] == "S3-FIFO" for r in crows), 30, "extension S3-FIFO best rows")
    rep.equal(len({r["best_static"] for r in crows}), 6, "extension distinct best policies")

    madmax = [r for r in manifest if r["trace"] == "fiu_madmax_2m"]
    rep.equal(len(madmax), 1, "extension madmax manifest row")
    if madmax:
        rep.equal(int(madmax[0]["ref_stop"]), 918010, "extension madmax amended ref_stop")
    rep.check(
        all(len(r["source_sha256"]) == 64 and len(r["bin_sha256"]) == 64 and
            r["source_url"].startswith(BASE_URL + "/") for r in manifest),
        "extension manifest hashes and source URLs",
    )


def verify_documents(rep, root):
    protocol = (root / "PATH_A_PROTOCOL.md").read_text(errors="replace")
    ext_protocol = (root / "PATH_A_EXTENSION_PROTOCOL.md").read_text(errors="replace")
    ext_results = (root / "PATH_A_EXTENSION_RESULTS.md").read_text(errors="replace")
    paper = (root / "PATH_A_SHORT_PAPER.md").read_text(errors="replace")
    rep.check("2026-11-25T09:25:44Z" in protocol and "d54b0d959480062d3948a2b9ac70b42341894238" in protocol,
              "primary protocol timestamp and HEAD")
    rep.check("2026-11-25T10:08:54Z" in ext_protocol and
              "ffc9f3768ef9a1e066d8077d80f67be26779faa7" in ext_protocol and
              "2026-11-25T16:36:57Z" in ext_protocol,
              "extension protocol timestamps and HEAD")
    rep.check("Use is non-commercial research with citation; raw traces are not redistributed." in ext_protocol,
              "PDL use wording is exact")
    rep.check("PATH_A_STANDS" in ext_results and "PATH_A_STANDS" in paper,
              "result memo and short paper report extension decision")


SHARED = [
    "PATH_A_RESULTS.md",
    "PATH_A_EXTENSION_PROTOCOL.md",
    "PATH_A_EXTENSION_RESULTS.md",
    "reproduction/pathA_oracle/README.md",
    "reproduction/pathA_oracle/prepare_pathA_extension.py",
    "reproduction/pathA_oracle/run_pathA_extension.py",
    "reproduction/pathA_oracle/analyze_pathA_extension.py",
    "reproduction/pathA_oracle/verify_pathA_evidence.py",
]
SHARED += [f"reproduction/pathA_oracle/results_extension/{name}" for name in (
    "manifest.csv", "summary.csv", "policy.csv", "windows.csv",
    "aggregate_family.csv", "aggregate_zero_cost_bound.csv",
    "decision.csv", "extension_decision.csv",
)]


def verify_public(rep, public_root):
    for rel in SHARED:
        left, right = HERE.parents[1] / rel, public_root / rel
        ok = right.exists() and left.read_bytes() == right.read_bytes()
        rep.check(ok, f"public copy matches: {rel}")
    forbidden = [p for p in public_root.rglob("*")
                 if ".git" not in p.parts and p.is_file() and p.suffix.lower() in {".zst", ".bin", ".pdf", ".docx"}]
    rep.check(not forbidden, "public repo has no raw traces, PDFs, or DOCX files",
              ",".join(str(p.relative_to(public_root)) for p in forbidden[:5]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="research tree root")
    ap.add_argument("--public-root", type=Path, help="optional public repository root to compare")
    args = ap.parse_args()

    rep = Report()
    print("Primary run")
    verify_primary(rep)
    print("\nSensitivity run")
    verify_sensitivity(rep)
    print("\nExtension run")
    verify_extension(rep)
    print("\nDocuments")
    verify_documents(rep, args.root)
    if args.public_root:
        print("\nPublic sync")
        verify_public(rep, args.public_root)
    print(f"\nRESULT: {'PASS' if rep.ok else 'FAIL'} ({rep.passed} checks passed)")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
