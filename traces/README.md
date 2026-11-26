# Trace Corpus Directory

This directory stores metadata and SHA-256 checksums (`SHA256SUMS`) for all **88 traces** across **30 families** and **4 sources**. Large binary `.bin` files (32-bit little-endian page IDs) are excluded from git/lightweight release bundles; see `scripts/download_traces.sh` and `results/raw/manifest.csv`.

## Trace Sources & Redistribution Status

1. **Real-Application Page-Level Traces (`real_app_pageref`, 10 traces, 3 families)**
   - Workloads: SQLite (`sqlite_oltp_scan`, `sqlite_join_agg`, `sqlite_mixed_rw`), `git` (`git_repo`), Python ETL (`python_etl`).
   - Capture method: `tracer/pc_trace.c` (`LD_PRELOAD` interposition).
   - Redistribution: **Yes** (CC-BY-4.0; reproducible locally via `tracer/capture_app_traces.py`).

2. **Instrumented-Program Kernel Traces (`instrumented_program`, 60 traces, 15 families)**
   - Algorithms: BFS, binary search, B-tree, hash join, hash map, heap, linked list, matvec, PageRank, radix sort, sort, sparse matvec, stencil, string match, union-find (4 seeds/variants each).
   - Redistribution: **Yes** (CC-BY-4.0).

3. **Public FIU Block-I/O Traces (`fiu_public`, 12 traces, 6 families)**
   - Workloads: `homes`, `ikki`, `madmax`, `online`, `topgun`, `webresearch` (train/test splits).
   - Upstream: FIU / CMU PDL `cacheDatasets` (`https://pdl.cmu.edu/CacheEviction/index.shtml`).
   - Redistribution: **Upstream only** (non-commercial academic terms; do not mirror without upstream permission).

4. **Public PDL Cache/Storage Traces (`pdl_public`, 6 traces, 6 families)**
   - Workloads: Alibaba, CloudPhysics, MetaKV, MSR Cambridge, Tencent, Twitter (1M-reference prefixes).
   - Upstream: CMU PDL `cacheDatasets` (`https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/`).
   - Redistribution: **Upstream only** (`https://pdl.cmu.edu/Publications/copyright.shtml`).

## Verification

Verify any locally placed `.bin` traces against `traces/SHA256SUMS`:
```bash
sha256sum -c --ignore-missing traces/SHA256SUMS
```
