#!/usr/bin/env python3
"""Capture genuine page-level traces from real applications locally.

Two capture backends:
1. LD_PRELOAD OS page-cache tracer (pc_trace.so) on unmodified Linux binaries:
   - sqlite3 (3 workload patterns x 2 seeds = 6 traces)
   - git (repository object/pack/diff/grep sweep = 2 traces)
   - python3 (multi-pass CSV/numpy/sqlite analytics = 2 traces)
2. Compiler-instrumented VM data-page tracer (-fsanitize=thread + tsan_trace_rt.c):
   - real_cpp_apps (bwt, kv, graph, cache x 3 seeds = 12 traces)

All raw 64-bit page keys are mapped on first touch to dense uint32 page IDs
compatible with the trace-replay simulators, and a SHA256 manifest is written.
"""
import csv
import hashlib
import os
import random
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT_DIR = HERE / "bins"
MANIFEST = HERE / "manifest.csv"

PC_SO = HERE / "pc_trace.so"
APP_BIN = HERE / "real_cpp_apps_traced"


def compile_tracers():
    subprocess.run(
        ["gcc", "-shared", "-fPIC", "-O2", str(HERE / "pc_trace.c"), "-o", str(PC_SO), "-ldl", "-lpthread"],
        check=True,
    )
    subprocess.run(
        ["clang++", "-O2", "-std=c++17", "-fsanitize=thread", "-c", str(HERE / "real_cpp_apps.cpp"), "-o", str(HERE / "real_cpp_apps.o")],
        check=True,
    )
    subprocess.run(
        ["gcc", "-O2", str(HERE / "real_cpp_apps.o"), str(HERE / "tsan_trace_rt.c"), "-lstdc++", "-lm", "-o", str(APP_BIN)],
        check=True,
    )


def convert_u64_to_u32(raw_path: Path, bin_path: Path):
    raw = np.fromfile(raw_path, dtype="<u8")
    if raw.size == 0:
        raise RuntimeError(f"empty raw trace: {raw_path}")
    # Map 64-bit page keys to dense uint32 IDs in first-touch order
    _, first_idx, inv = np.unique(raw, return_index=True, return_inverse=True)
    order = np.argsort(first_idx)
    remap = np.empty_like(order, dtype=np.uint32)
    remap[order] = np.arange(order.size, dtype=np.uint32)
    dense = remap[inv].astype("<u4")
    dense.tofile(bin_path)
    return int(dense.size), int(order.size)


def sha256_file(path: Path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_sqlite_db(db_path: Path, seed: int):
    if db_path.exists():
        db_path.unlink()
    rng = random.Random(seed)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=OFF;")
    conn.execute("CREATE TABLE kv (id INTEGER PRIMARY KEY, k INTEGER, grp INTEGER, v TEXT);")
    conn.execute("CREATE TABLE tags (grp INTEGER PRIMARY KEY, label TEXT, weight INTEGER);")
    rows = [(i, rng.randint(0, 60000), i % 500, f"val_{i}_" + ("x" * 180)) for i in range(110000)]
    conn.executemany("INSERT INTO kv VALUES (?, ?, ?, ?)", rows)
    conn.executemany("INSERT INTO tags VALUES (?, ?, ?)", [(g, f"grp_{g}", rng.randint(1, 100)) for g in range(500)])
    conn.execute("CREATE INDEX idx_k ON kv(k);")
    conn.execute("CREATE INDEX idx_grp ON kv(grp);")
    conn.commit()
    conn.close()


def capture_sqlite(name: str, family: str, mode: str, seed: int, max_refs: int = 550000):
    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        db = td_p / "work.db"
        sql = td_p / "queries.sql"
        raw = td_p / "trace.raw"
        build_sqlite_db(db, seed)
        rng = random.Random(seed + 999)
        lines = ["PRAGMA cache_size=2;", "PRAGMA temp_store=FILE;"]
        if mode == "oltp_scan":
            for _ in range(14000):
                k = int(rng.paretovariate(1.25)) % 60000
                lines.append(f"SELECT id, LENGTH(v) FROM kv WHERE k={k};")
            for _ in range(1800):
                k0 = rng.randint(0, 59400)
                lines.append(f"SELECT COUNT(*), SUM(LENGTH(v)) FROM kv WHERE k BETWEEN {k0} AND {k0+250};")
            for _ in range(7000):
                idv = rng.randint(0, 109999)
                lines.append(f"SELECT k, grp FROM kv WHERE id={idv};")
        elif mode == "join_agg":
            for _ in range(150):
                g0 = rng.randint(0, 440)
                lines.append(
                    f"SELECT t.label, COUNT(*), SUM(k.k) FROM kv k JOIN tags t ON k.grp=t.grp "
                    f"WHERE t.grp BETWEEN {g0} AND {g0+40} GROUP BY t.label;"
                )
            for _ in range(12000):
                k = rng.randint(0, 60000)
                lines.append(f"SELECT id FROM kv WHERE k={k};")
            for _ in range(1200):
                k0 = rng.randint(0, 59500)
                lines.append(f"SELECT SUM(grp) FROM kv WHERE k BETWEEN {k0} AND {k0+200};")
        else:  # mixed_rw
            for i in range(6000):
                idv = rng.randint(0, 109999)
                nk = rng.randint(0, 60000)
                lines.append(f"UPDATE kv SET k={nk} WHERE id={idv};")
            for _ in range(12000):
                k = int(rng.paretovariate(1.3)) % 60000
                lines.append(f"SELECT LENGTH(v) FROM kv WHERE k={k};")
            for _ in range(1200):
                k0 = rng.randint(0, 59500)
                lines.append(f"SELECT COUNT(*) FROM kv WHERE k BETWEEN {k0} AND {k0+250};")
        sql.write_text("\n".join(lines) + "\n")
        so_tmp = td_p / "pc_trace.so"
        shutil.copy2(PC_SO, so_tmp)
        env = dict(os.environ, LD_PRELOAD=str(so_tmp), PC_TRACE_OUT=str(raw), PC_TRACE_MAX=str(max_refs))
        with open(sql, "rb") as fin:
            subprocess.run(["sqlite3", str(db)], stdin=fin, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, check=True)
        out_bin = OUT_DIR / f"{name}.bin"
        refs, wss = convert_u64_to_u32(raw, out_bin)
        return {"trace": name, "family": family, "source": "app_pagecache_sqlite", "backend": "LD_PRELOAD_pagecache",
                "binary": "/usr/bin/sqlite3", "seed": seed, "path": str(out_bin), "refs": refs, "wss": wss,
                "sha256": sha256_file(out_bin)}


def capture_git(name: str, family: str, seed: int, max_refs: int = 500000):
    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        raw = td_p / "git.raw"
        so_tmp = td_p / "pc_trace.so"
        shutil.copy2(PC_SO, so_tmp)
        env = dict(os.environ, LD_PRELOAD=str(so_tmp), PC_TRACE_OUT=str(raw), PC_TRACE_MAX=str(max_refs))
        cmds = [
            ["git", "log", "-p", "-n", "25"],
            ["git", "grep", "-n", "S3-FIFO", "--", "reproduction/", "drift_gating_latex_source/"],
            ["git", "diff", "HEAD~10..HEAD"],
            ["git", "log", "--stat", "-n", "30"],
        ]
        cycles = 45 if seed == 101 else 55
        for c in range(cycles):
            cmd = cmds[(c + seed) % len(cmds)]
            subprocess.run(cmd, cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        out_bin = OUT_DIR / f"{name}.bin"
        refs, wss = convert_u64_to_u32(raw, out_bin)
        return {"trace": name, "family": family, "source": "app_pagecache_git", "backend": "LD_PRELOAD_pagecache",
                "binary": "/usr/bin/git", "seed": seed, "path": str(out_bin), "refs": refs, "wss": wss,
                "sha256": sha256_file(out_bin)}


def capture_python(name: str, family: str, seed: int, max_refs: int = 500000):
    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        raw = td_p / "py.raw"
        data_files = []
        rng = np.random.default_rng(seed)
        for idx in range(8):
            f = td_p / f"shard_{idx}.bin"
            arr = rng.integers(0, 50000, size=1000000, dtype=np.uint32)  # 4 MB = 1000 pages each
            arr.tofile(f)
            data_files.append(str(f))
        script = td_p / "etl.py"
        script.write_text(f"""
import os, random
files = {data_files!r}
rng = random.Random({seed})
fhs = [open(p, 'rb', buffering=0) for p in files]
# Phase 1: skewed random 4 KiB block reads across 8 data files
for _ in range(160000):
    fh = fhs[int(rng.paretovariate(1.5)) % len(fhs)]
    off = (int(rng.paretovariate(1.25)) % 950) * 4096
    fh.seek(off)
    fh.read(4096)
# Phase 2: sequential multi-file scan
for fh in fhs * 25:
    fh.seek(0)
    while fh.read(4096):
        pass
# Phase 3: uniform random seeks
for _ in range(140000):
    fh = fhs[rng.randint(0, len(fhs)-1)]
    off = rng.randint(0, 950) * 4096
    fh.seek(off)
    fh.read(4096)
for fh in fhs:
    fh.close()
""")
        so_tmp = td_p / "pc_trace.so"
        shutil.copy2(PC_SO, so_tmp)
        env = dict(os.environ, LD_PRELOAD=str(so_tmp), PC_TRACE_OUT=str(raw), PC_TRACE_MAX=str(max_refs))
        subprocess.run(["python3", str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, check=True)
        out_bin = OUT_DIR / f"{name}.bin"
        refs, wss = convert_u64_to_u32(raw, out_bin)
        return {"trace": name, "family": family, "source": "app_pagecache_python", "backend": "LD_PRELOAD_pagecache",
                "binary": "/usr/bin/python3", "seed": seed, "path": str(out_bin), "refs": refs, "wss": wss,
                "sha256": sha256_file(out_bin)}


def capture_vm_cpp(app: str, seed: int, max_refs: int = 550000):
    name = f"vm_{app}_s{seed}"
    family = f"vm_{app}"
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "vm.raw"
        env = dict(os.environ, VM_TRACE_OUT=str(raw), VM_TRACE_MAX=str(max_refs), VM_TRACE_STRIDE="3")
        subprocess.run([str(APP_BIN), app, str(seed)], env=env, check=True)
        out_bin = OUT_DIR / f"{name}.bin"
        refs, wss = convert_u64_to_u32(raw, out_bin)
        return {"trace": name, "family": family, "source": "app_vm_tsan", "backend": "clang_tsan_load_store",
                "binary": str(APP_BIN), "seed": seed, "path": str(out_bin), "refs": refs, "wss": wss,
                "sha256": sha256_file(out_bin)}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    compile_tracers()
    rows = []
    for mode in ("oltp_scan", "join_agg", "mixed_rw"):
        for seed in (101, 202):
            r = capture_sqlite(f"sqlite_{mode}_s{seed}", f"sqlite_{mode}", mode, seed)
            print(f"captured {r['trace']}: refs={r['refs']} wss={r['wss']}")
            rows.append(r)
    for seed in (101, 202):
        r = capture_git(f"git_repo_s{seed}", "git_repo", seed)
        print(f"captured {r['trace']}: refs={r['refs']} wss={r['wss']}")
        rows.append(r)
    for seed in (101, 202):
        r = capture_python(f"python_etl_s{seed}", "python_etl", seed)
        print(f"captured {r['trace']}: refs={r['refs']} wss={r['wss']}")
        rows.append(r)
    for app in ("bwt", "kv", "graph", "cache"):
        for seed in (101, 202, 303):
            r = capture_vm_cpp(app, seed)
            print(f"captured {r['trace']}: refs={r['refs']} wss={r['wss']}")
            rows.append(r)

    fields = ["trace", "family", "source", "backend", "binary", "seed", "path", "refs", "wss", "sha256"]
    with open(MANIFEST, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} real-application traces to {MANIFEST}")


if __name__ == "__main__":
    main()
