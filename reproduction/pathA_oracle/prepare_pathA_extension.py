#!/usr/bin/env python3
"""Convert the pre-specified Path A extension traces and write their manifest.

This script is additive. It reads only the public .zst files named in
PATH_A_EXTENSION_PROTOCOL.md, writes converted .bin files to a caller-supplied
cache directory outside the repository, and records hashes/metadata in
results_extension/manifest.csv. Raw traces are not copied into the repository.
"""
import argparse
import csv
import hashlib
import struct
from pathlib import Path

import numpy as np
import zstandard

HERE = Path(__file__).resolve().parent
DEFAULT_CACHE = Path("/home/kashie/Tmp/research/fiu_ext")
RESULTS = HERE / "results_extension"
BASE = "https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/fiu"
REC = struct.Struct("<IQIq")
LIMIT = 2_000_000

SOURCES = {
    "online": "fiu_online.cs.fiu.edu-110108-113008.oracleGeneral.zst",
    "combined": "fiu_webmail+online.cs.fiu.edu-110108-113008.oracleGeneral.zst",
    "casa": "fiu_casa-110108-112108.oracleGeneral.zst",
    "webmail": "fiu_webmail.cs.fiu.edu-110108-113008.oracleGeneral.zst",
    "webresearch": "fiu_webresearch-030409-033109.oracleGeneral.zst",
    "homes": "fiu_homes-110108-112108.oracleGeneral.zst",
    "ikki": "fiu_ikki-110108-112108.oracleGeneral.zst",
    "madmax": "fiu_madmax-110108-112108.oracleGeneral.zst",
}

# label, source key, family, role, ref range [start, stop) in the converted trace
JOBS = [
    ("fiu_online_full2m", "online", "fiu_online", "more FIU-online evidence", 0, LIMIT),
    ("fiu_online_seg1m_1p5m", "online", "fiu_online", "non-overlapping FIU-online segment", 1_000_000, 1_500_000),
    ("fiu_online_seg1p5m_2m", "online", "fiu_online", "non-overlapping FIU-online segment", 1_500_000, 2_000_000),
    ("fiu_webmail_online_combined_2m", "combined", "fiu_webmail_online_combined", "unseen mixed family", 0, LIMIT),
    ("fiu_casa_2m", "casa", "fiu_casa", "unseen family", 0, LIMIT),
    ("fiu_webmail_2m", "webmail", "fiu_webmail", "extend existing family", 0, LIMIT),
    ("fiu_webresearch_2m", "webresearch", "fiu_webresearch", "extend existing family", 0, LIMIT),
    ("fiu_homes_2m", "homes", "fiu_homes", "extend existing family", 0, LIMIT),
    ("fiu_ikki_2m", "ikki", "fiu_ikki", "extend existing family", 0, LIMIT),
    ("fiu_madmax_2m", "madmax", "fiu_madmax", "extend existing family", 0, LIMIT),
]

FIELDS = [
    "trace", "family", "source", "role", "path", "source_url", "source_file",
    "source_sha256", "bin_sha256", "ref_start", "ref_stop", "refs", "wss",
    "max_id", "np", "capacities",
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def convert(src, dst, limit):
    ids = {}
    out = bytearray()
    n = 0
    with open(src, "rb") as fh:
        reader = zstandard.ZstdDecompressor().stream_reader(fh)
        buf = b""
        while n < limit:
            chunk = reader.read(REC.size * 65536)
            if not chunk:
                break
            buf += chunk
            upto = len(buf) - (len(buf) % REC.size)
            for off in range(0, upto, REC.size):
                _ts, oid, _sz, _nxt = REC.unpack_from(buf, off)
                idx = ids.get(oid)
                if idx is None:
                    idx = len(ids)
                    ids[oid] = idx
                out += struct.pack("<I", idx)
                n += 1
                if n >= limit:
                    break
            buf = buf[upto:]
    with open(dst, "wb") as fh:
        fh.write(out)
    return n, len(ids)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_CACHE / "src",
                    help="directory containing the public .zst source files")
    ap.add_argument("--bin", type=Path, default=DEFAULT_CACHE / "bin",
                    help="directory for converted .bin traces (outside the repo)")
    args = ap.parse_args()
    src_dir, bin_dir = args.src, args.bin

    bin_dir.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    converted = {}
    rows = []
    for key, fname in SOURCES.items():
        src = src_dir / fname
        if not src.exists():
            raise SystemExit(f"missing source: {src}")
        dst = bin_dir / (key + "_2m.bin")
        n, distinct = convert(src, dst, LIMIT)
        print(f"converted {fname}: {n} refs, {distinct} distinct objects", flush=True)
        converted[key] = (dst, n, distinct, sha256(src))

    for label, key, family, role, start, stop in JOBS:
        dst, n, _distinct, src_hash = converted[key]
        # Amendment 1: the madmax source has fewer than 2M records. Use all
        # available records and record the actual stop in the manifest.
        stop_eff = min(stop, n)
        ids = np.fromfile(dst, dtype="<u4", count=stop_eff)[start:stop_eff]
        if ids.size != stop_eff - start:
            raise SystemExit(f"{label}: expected {stop_eff - start} refs, got {ids.size}")
        out = bin_dir / (label + ".bin")
        ids.tofile(out)
        wss = int(np.unique(ids).size)
        max_id = int(ids.max())
        caps = [max(1, round(wss * f)) for f in (0.01, 0.05, 0.10)]
        rows.append({
            "trace": label, "family": family, "source": "fiu_public_extension",
            "role": role, "path": str(out), "source_url": BASE + "/" + SOURCES[key],
            "source_file": SOURCES[key], "source_sha256": src_hash,
            "bin_sha256": sha256(out), "ref_start": start, "ref_stop": stop_eff,
            "refs": int(ids.size), "wss": wss, "max_id": max_id,
            "np": max_id + 1, "capacities": ";".join(map(str, caps)),
        })
        print(f"prepared {label}: {ids.size} refs, WSS {wss}", flush=True)

    manifest = RESULTS / "manifest.csv"
    with open(manifest, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {manifest} with {len(rows)} traces")


if __name__ == "__main__":
    main()
