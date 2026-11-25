#!/usr/bin/env python3
"""Stream a bounded prefix from a CMU PDL .zst URL into sim_full format."""
import argparse
import csv
import datetime as dt
import hashlib
import os
import struct
import sys
import urllib.request

import zstandard

REC = struct.Struct("<IQIq")  # packed 24-byte libCacheSim oracleGeneral record
N_REFS = 1_000_000

SOURCES = {
    "msr": "https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/msr/msr_hm_0.oracleGeneral.zst",
    "alibaba": "https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/alibabaBlock/old/io_traces.ns42.oracleGeneral.zst",
    "tencent": "https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/tencentBlock/old/tencentBlock.ns1089.oracleGeneral.zst",
    "cloudphysics": "https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/cloudphysics/w64.oracleGeneral.bin.zst",
    "twitter": "https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/twitter/sample10/cluster10.oracleGeneral.sample10.zst",
    "metakv": "https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/metaKV/202206_kv_traces_all.csv.oracleGeneral.zst",
}


class CountingReader:
    def __init__(self, raw):
        self.raw = raw
        self.bytes_read = 0

    def read(self, n=-1):
        b = self.raw.read(n)
        self.bytes_read += len(b)
        return b

    def readable(self):
        return True


def convert(family, url, outdir):
    os.makedirs(outdir, exist_ok=True)
    dst = os.path.join(outdir, family + ".bin")
    ids = {}
    out = bytearray()
    n = 0
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    with urllib.request.urlopen(url, timeout=120) as resp:
        status = getattr(resp, "status", None)
        counted = CountingReader(resp)
        reader = zstandard.ZstdDecompressor().stream_reader(counted)
        buf = b""
        while n < N_REFS:
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
                if n >= N_REFS:
                    break
            buf = buf[upto:]
        reader.close()
    if n != N_REFS:
        raise RuntimeError(f"{family}: expected {N_REFS} records, got {n}")
    with open(dst, "wb") as fh:
        fh.write(out)
    sha = hashlib.sha256(out).hexdigest()
    return {
        "family": family,
        "url": url,
        "http_status": status,
        "utc_start": started,
        "compressed_bytes_consumed": counted.bytes_read,
        "records": n,
        "wss": len(ids),
        "max_id": max(ids.values()) if ids else 0,
        "sha256_bin": sha,
        "output": dst,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--families", default=",".join(SOURCES))
    args = ap.parse_args()
    families = [f.strip() for f in args.families.split(",") if f.strip()]
    manifest = os.path.join(args.outdir, "manifest.csv")
    rows = []
    for fam in families:
        if fam not in SOURCES:
            raise SystemExit(f"unknown family: {fam}")
        print(f"converting {fam} ...", file=sys.stderr, flush=True)
        rows.append(convert(fam, SOURCES[fam], args.outdir))
    fields = ["family", "url", "http_status", "utc_start", "compressed_bytes_consumed",
              "records", "wss", "max_id", "sha256_bin", "output"]
    mode = "a" if os.path.exists(manifest) else "w"
    with open(manifest, mode, newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if mode == "w":
            w.writeheader()
        for r in rows:
            w.writerow(r)
    for r in rows:
        print(f"{r['family']}: {r['records']} refs, WSS={r['wss']}, sha256={r['sha256_bin']}")


if __name__ == "__main__":
    main()
