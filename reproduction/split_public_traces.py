#!/usr/bin/env python3
"""Split the six converted FIU page-id traces into training prefixes and
held-out suffixes for public-trace parameter re-selection.

Each converted trace is a raw array of uint32 page ids.  The first SPLIT refs
become the training prefix; the remaining refs become the held-out suffix.
Both are written as raw uint32 .bin files readable by sim_full --trace.
"""
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "/tmp/opencode/fiu"
OUT = os.path.join(HERE, "public_split")
SPLIT = 500000

NAMES = [
    "fiu_homes-110108-112108.oracleGeneral",
    "fiu_ikki-110108-112108.oracleGeneral",
    "fiu_madmax-110108-112108.oracleGeneral",
    "fiu_online.cs.fiu.edu-110108-113008.oracleGeneral",
    "fiu_webmail.cs.fiu.edu-110108-113008.oracleGeneral",
    "fiu_webresearch-030409-033109.oracleGeneral",
]


def main():
    os.makedirs(OUT, exist_ok=True)
    for name in NAMES:
        src = os.path.join(SRC, name + ".bin")
        with open(src, "rb") as f:
            data = f.read()
        n = len(data) // 4
        assert n * 4 == len(data), name
        pre = data[:SPLIT * 4]
        suf = data[SPLIT * 4:]
        with open(os.path.join(OUT, name + ".train.bin"), "wb") as f:
            f.write(pre)
        with open(os.path.join(OUT, name + ".test.bin"), "wb") as f:
            f.write(suf)
        print(f"{name}: {n} refs -> train {len(pre)//4}, test {len(suf)//4}")


if __name__ == "__main__":
    main()
