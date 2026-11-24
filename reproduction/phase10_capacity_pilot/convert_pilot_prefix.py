#!/usr/bin/env python3
"""Stream the pre-registered Phase 10 capacity-pilot prefix from a PDL URL.

This is the Phase 6 conversion rule applied to the single independent pilot
trace registered in PROTOCOL.md.  It decodes exactly 1,000,000 packed
24-byte oracleGeneral records and records a manifest with content hashes.
"""
import csv
import datetime as dt
import hashlib
import os
import struct
import sys
import urllib.request

import zstandard

HERE = os.path.dirname(os.path.abspath(__file__))
REC = struct.Struct("<IQIq")  # packed 24-byte libCacheSim oracleGeneral record
N_REFS = 1_000_000
TRACE = "webusers"
URL = ("https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/"
       "cacheDatasets/fiu/fiu_webusers-030409-033109.oracleGeneral.zst")


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


def main():
    dst = os.path.join(HERE, TRACE + ".bin")
    manifest = os.path.join(HERE, "manifest.csv")
    ids = {}
    out = bytearray()
    n = 0
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    with urllib.request.urlopen(URL, timeout=120) as resp:
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
        raise RuntimeError(f"{TRACE}: expected {N_REFS} records, got {n}")
    with open(dst, "wb") as fh:
        fh.write(out)
    row = {
        "trace": TRACE,
        "url": URL,
        "http_status": status,
        "utc_start": started,
        "compressed_bytes_consumed": counted.bytes_read,
        "records": n,
        "wss": len(ids),
        "max_id": max(ids.values()) if ids else 0,
        "sha256_bin": hashlib.sha256(out).hexdigest(),
        "output": dst,
    }
    fields = list(row)
    mode = "a" if os.path.exists(manifest) else "w"
    with open(manifest, mode, newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if mode == "w":
            w.writeheader()
        w.writerow(row)
    print(f"{TRACE}: {row['records']} refs, WSS={row['wss']}, "
          f"sha256={row['sha256_bin']}", file=sys.stderr)


if __name__ == "__main__":
    main()
