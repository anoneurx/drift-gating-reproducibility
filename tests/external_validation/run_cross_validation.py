#!/usr/bin/env python3
"""
tests/external_validation/run_cross_validation.py
Compare pathA_sim.cpp policies (LRU, FIFO, ARC, S3-FIFO, SIEVE) against
independent reference implementations in ref_policies.py.
"""
import struct
import subprocess
from pathlib import Path
import numpy as np

from ref_policies import RefLRU, RefFIFO, RefARC, RefS3FIFO, RefSIEVE

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BIN = Path("/tmp/dump_policies")

REFS_MAP = {
    "LRU": RefLRU,
    "FIFO": RefFIFO,
    "ARC": RefARC,
    "S3-FIFO": RefS3FIFO,
    "SIEVE": RefSIEVE,
}


def compile_driver():
    subprocess.run(
        ["g++", "-O2", "-std=c++17", "-o", str(BIN), str(HERE / "dump_policies.cpp")],
        check=True,
    )


def load_trace(path: Path):
    data = path.read_bytes()
    n = len(data) // 4
    return list(struct.unpack(f"<{n}I", data[: n * 4]))


def run_cpp(trace_path: Path, C: int, policies):
    out = subprocess.check_output(
        [str(BIN), str(trace_path), str(C), ",".join(policies)], text=True
    )
    res = {}
    for line in out.strip().splitlines():
        p, c, n, warm, tot_m, eval_m, eval_mr = line.split(",")
        res[p] = (int(tot_m), int(eval_m), float(eval_mr))
    return res


def run_py(refs, C: int, policies):
    warm = min(100000, len(refs) // 10)
    n_eval = len(refs) - warm
    res = {}
    for pname in policies:
        pol = REFS_MAP[pname](C)
        tot_m = 0
        eval_m = 0
        for i, x in enumerate(refs):
            if not pol.access(x):
                tot_m += 1
                if i >= warm:
                    eval_m += 1
        res[pname] = (tot_m, eval_m, eval_m / n_eval)
    return res


def main():
    compile_driver()
    policies = ["LRU", "FIFO", "ARC", "S3-FIFO", "SIEVE"]

    # Create synthetic Zipfian trace in /tmp
    rng = np.random.default_rng(123)
    zipf_refs = (rng.zipf(1.8, size=20000) % 500).astype(np.uint32).tolist()
    zipf_path = Path("/tmp/synth_zipf.bin")
    zipf_path.write_bytes(struct.pack(f"<{len(zipf_refs)}I", *zipf_refs))

    traces = [
        ("synth_zipf", zipf_path, [10, 50]),
        ("btree_s101", ROOT / "traces_real" / "btree_s101.bin", None),
        ("hashjoin_s101", ROOT / "traces_real" / "hashjoin_s101.bin", None),
        ("bfs_s101", ROOT / "traces_real" / "bfs_s101.bin", None),
    ]

    print(f"{'Trace':14s} {'C':>5s} {'Policy':8s} {'C++ evalM':>10s} {'Ref evalM':>10s} {'Diff':>7s} {'C++ MR':>9s} {'Ref MR':>9s}")
    print("-" * 80)
    for tname, tpath, caps in traces:
        refs = load_trace(tpath)
        if caps is None:
            wss = len(set(refs))
            caps = [max(1, round(f * wss)) for f in (0.01, 0.05, 0.10)]
        for C in caps:
            cpp_res = run_cpp(tpath, C, policies)
            py_res = run_py(refs, C, policies)
            for p in policies:
                cm, cem, cmr = cpp_res[p]
                pm, pem, pmr = py_res[p]
                diff = cem - pem
                print(f"{tname:14s} {C:5d} {p:8s} {cem:10d} {pem:10d} {diff:+7d} {cmr:9.6f} {pmr:9.6f}")


if __name__ == "__main__":
    main()
