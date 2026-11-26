#!/usr/bin/env python3
"""Run the unified Path A study across all local real-application and public traces."""
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
BIN = HERE / "pathA_sim"
RESULTS = HERE / "results"
TMP_ROOT = Path("/tmp/opencode/pathA_study_tmp")


def trace_info(path: Path):
    ids = np.fromfile(path, dtype="<u4")
    if ids.size == 0:
        raise ValueError(f"empty trace: {path}")
    max_id = int(ids.max())
    wss = int(np.unique(ids).size)
    caps = [(f"{f:.2f}", max(1, round(wss * f))) for f in (0.01, 0.05, 0.10)]
    return {"refs": int(ids.size), "wss": wss, "max_id": max_id, "np": max_id + 1, "caps": caps}


def discover():
    out = []
    # 1. Newly captured real-application page-level traces
    app_manifest = ROOT / "reproduction" / "app_traces" / "manifest.csv"
    if app_manifest.exists():
        with open(app_manifest, newline="") as fh:
            for r in csv.DictReader(fh):
                p = Path(r["path"])
                if not p.is_absolute():
                    p = ROOT / p
                if p.exists():
                    out.append((r["trace"], r["family"], r["source"], p))
    # 2. Instrumented-program page traces
    for p in sorted((ROOT / "traces_real").glob("*.bin")):
        stem = p.stem
        family = stem.split("_")[0]
        out.append(("prog_" + stem, family, "instrumented_program", p))
    # 3. Public FIU held-out prefixes (webusers excluded as capacity pilot)
    for p in sorted((ROOT / "reproduction" / "public_split").glob("*.bin")):
        stem = p.stem
        body = stem[len("fiu_"):] if stem.startswith("fiu_") else stem
        fam = "fiu_" + body.split("-")[0]
        suf = "test" if stem.endswith(".test") else "train"
        out.append((f"{fam}_{suf}", fam, "fiu_public", p))
    # 4. Public PDL 1M prefixes
    for p in sorted((ROOT / "reproduction" / "phase6_pdl").glob("*.bin")):
        fam = "pdl_" + p.stem
        out.append((fam, fam, "pdl_public", p))
    return out


def run_job(job):
    label, family, source, path, cap_frac, cap, np_sz, window, mode = job
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TMP_ROOT) as td:
        pref = Path(td) / "out"
        cmd = [
            str(BIN),
            "--mode", mode,
            "--trace", str(path),
            "--label", label,
            "--family", family,
            "--source", source,
            "--cap-frac", cap_frac,
            "--C", str(cap),
            "--np", str(np_sz),
            "--window", str(window),
            "--out-prefix", str(pref),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"{label} C={cap} w={window} failed: {proc.stderr.strip()}")
        res = {}
        for tag in ("oracle_summary", "policy", "controllers"):
            fp = Path(str(pref) + f"_{tag}.csv")
            if fp.exists():
                with open(fp, newline="") as fh:
                    res[tag] = list(csv.DictReader(fh))
        return res


def write_csv(path: Path, rows):
    if not rows:
        return
    fields = list(rows[0].keys())
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--results-dir", default=str(RESULTS))
    args = ap.parse_args()
    out_dir = Path(args.results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    traces = discover()
    print(f"discovered {len(traces)} traces")
    manifest = []
    jobs_w50, jobs_w100 = [], []
    for label, family, source, path in traces:
        info = trace_info(path)
        manifest.append({
            "trace": label, "family": family, "source": source,
            "path": str(path.relative_to(ROOT)),
            "refs": info["refs"], "wss": info["wss"],
            "max_id": info["max_id"], "np": info["np"],
            "capacities": ";".join(f"{cf}:{c}" for cf, c in info["caps"]),
        })
        for cf, cap in info["caps"]:
            jobs_w50.append((label, family, source, path, cf, cap, info["np"], 50000, "all"))
            # Check trace is long enough for w=100000 after warmup
            warm = min(100000, info["refs"] // 10)
            if info["refs"] - warm >= 100000:
                jobs_w100.append((label, family, source, path, cf, cap, info["np"], 100000, "oracle"))

    write_csv(out_dir / "manifest.csv", sorted(manifest, key=lambda r: r["trace"]))

    oracle_rows, pol_rows, ctrl_rows = [], [], []
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(run_job, j) for j in jobs_w50]
        for fut in as_completed(futs):
            res = fut.result()
            oracle_rows.extend(res.get("oracle_summary", []))
            pol_rows.extend(res.get("policy", []))
            ctrl_rows.extend(res.get("controllers", []))
            done += 1
            if done % 40 == 0 or done == len(jobs_w50):
                print(f"w=50000: {done}/{len(jobs_w50)}")

    oracle_w100 = []
    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(run_job, j) for j in jobs_w100]
        for fut in as_completed(futs):
            res = fut.result()
            oracle_w100.extend(res.get("oracle_summary", []))
            done += 1
            if done % 40 == 0 or done == len(jobs_w100):
                print(f"w=100000: {done}/{len(jobs_w100)}")

    oracle_rows.sort(key=lambda r: (r["trace"], float(r["cap_frac"]), float(r["switch_cost"])))
    pol_rows.sort(key=lambda r: (r["trace"], float(r["cap_frac"]), r["policy"]))
    ctrl_rows.sort(key=lambda r: (r["trace"], float(r["cap_frac"]), r["controller"]))
    oracle_w100.sort(key=lambda r: (r["trace"], float(r["cap_frac"]), float(r["switch_cost"])))

    write_csv(out_dir / "oracle_summary.csv", oracle_rows)
    write_csv(out_dir / "oracle_policy.csv", pol_rows)
    write_csv(out_dir / "controllers.csv", ctrl_rows)
    write_csv(out_dir / "oracle_summary_w100000.csv", oracle_w100)
    print(f"done: oracle={len(oracle_rows)}, policy={len(pol_rows)}, ctrl={len(ctrl_rows)}, w100={len(oracle_w100)}")


if __name__ == "__main__":
    sys.exit(main())
