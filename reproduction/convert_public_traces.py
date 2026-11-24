#!/usr/bin/env python3
"""Convert a public libCacheSim/cacheDatasets trace to the simulator format.

Input trace format (CMU PDL cacheDatasets, zstd compressed):
    packed struct { uint32 timestamp; uint64 obj_id; uint32 obj_size;
                    int64 next_access_vtime; }   // 24 bytes, little-endian

The simulator (`sim_full --trace`) reads a flat array of little-endian uint32
page/object identifiers.  Object ids are mapped to dense ids on first touch,
preserving reuse structure exactly; timestamps and sizes are ignored because
the simulator is capacity-only (one request = one reference).

Usage:
    python3 convert_public_traces.py IN.zst OUT.bin [--limit N]
    python3 convert_public_traces.py --all [--limit N]

`--all` converts every .zst in the current directory.  The default limit is
1,000,000 requests per trace so a run is tractable; the same prefix is used for
every policy, so comparisons remain paired.
"""
import argparse
import glob
import os
import struct

import zstandard

REC = struct.Struct("<IQIq")  # 24 bytes, packed


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
    ap.add_argument("src", nargs="?")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=1_000_000)
    args = ap.parse_args()

    jobs = []
    if args.all:
        for src in sorted(glob.glob("*.zst")):
            jobs.append((src, src[:-4] + ".bin"))
    else:
        if not args.src or not args.dst:
            ap.error("provide SRC and DST, or --all")
        jobs.append((args.src, args.dst))

    for src, dst in jobs:
        n, distinct = convert(src, dst, args.limit)
        print(f"{src} -> {dst}: {n} refs, {distinct} distinct objects")


if __name__ == "__main__":
    main()
