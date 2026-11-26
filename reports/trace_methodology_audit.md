# Phase 4: Trace Conversion and Dataset Methodology Audit

**Sources Audited:** `tracer/pc_trace.c`, `tracer/capture_app_traces.py`, `real_traces.cpp`, `reproduction/phase6_pdl/convert_pdl_prefix.py`, `results/raw/manifest.csv`, `traces/README.md`, `src/pathA_sim.cpp`  
**Audit Branch:** `research-validation-revision`  
**Date:** 2026-11-26

---

## 1. End-to-End Trace Representation & Conversion Rules

All 88 traces are stored and consumed by `src/pathA_sim.cpp` as flat binary arrays of 32-bit unsigned little-endian page/object identifiers (`uint32_t`, `.bin`).

| Aspect | `real_app_pageref` (10 traces) | `instrumented_program` (60 traces) | `fiu_public` (12 traces) | `pdl_public` (6 traces) |
|---|---|---|---|---|
| **Raw source** | Linux syscalls via `LD_PRELOAD` (`pc_trace.c`) | In-process `ACC(ptr)` (`real_traces.cpp`) | CMU PDL `oracleGeneral` (FIU block I/O) | CMU PDL `oracleGeneral.zst` (6 systems) |
| **Address → Page ID** | `pg = off >> 12` (4 KiB file page); 64-bit key `(ino * 1315423911) ^ pg ^ (dev << 48)` | `((uintptr_t)p) >> 12` (4 KiB virtual page) | 64-bit `oid` field from `<IQIq` record (24 bytes) | 64-bit `oid` field from `<IQIq` record (24 bytes) |
| **Request sizes (`len` / `sz`)** | Split into $\lfloor(\text{off}+\text{len}-1)/4096\rfloor - \lfloor\text{off}/4096\rfloor + 1$ sequential 4 KiB pages | Single pointer access $\to$ 1 page ref | `_sz` ignored; 1 record $\to$ 1 ref | `_sz` ignored; 1 record $\to$ 1 ref |
| **Reads vs. Writes** | Both `read/pread/fread` and `write/pwrite/fwrite` logged identically; `mmap` logs `off..off+len` at map time | Read/write indistinguishable (`ACC`) | Ignored (`oracleGeneral` struct has no op flag used) | Ignored (`_ts, oid, _sz, _nxt` unpacked; `_ts/_sz/_nxt` discarded) |
| **Dense normalization** | `convert_u64_to_u32()` maps unique 64-bit keys in first-touch order to `0..WSS-1` | `unordered_map<u64,u32>` maps on first touch to `0..WSS-1` | Shared `train`/`test` first-touch mapping (`max_id` in `test` exceeds `test` `wss`) | First-touch `ids[oid] = len(ids)` to `0..WSS-1` |
| **Trace boundaries** | `PC_TRACE_MAX` (550k SQLite; unbounded/full run for `git`/`python`, 0.31M–2.29M) | Fixed `CAP = 300,000` refs | `500,000` refs (`fiu_madmax_test`: `418,010`) | Fixed `N_REFS = 1,000,000` prefix |
| **Malformed / partial records** | `len == 0` or non-regular FDs (`!S_ISREG`) skipped | N/A | Partial trailing bytes `< 24` ignored | `upto = len(buf) - (len(buf) % 24)`; raises error if `< 1,000,000` |

---

## 2. Simulator Boundary, WSS, and Compulsory Miss Calculations

Inside `src/pathA_sim.cpp:1596-1603`:
1. **Working-Set Size (WSS):**  
   $$\text{WSS} = |\{r_0, r_1, \dots, r_{N-1}\}|$$
   computed over the **entire** trace (`unordered_set<u32> distinct(refs.begin(), refs.end())`), including warm-up.
2. **Cache Capacity:**  
   $$C = \max(1, \operatorname{round}(f \cdot \text{WSS})), \quad f \in \{0.01, 0.05, 0.10, 0.25, 0.50\}.$$
3. **Warm-up & Evaluation Windows:**  
   $$N_{\text{warm}} = \min(100{,}000, \lfloor N / 10 \rfloor), \quad T = \lfloor (N - N_{\text{warm}}) / W \rfloor, \quad N_{\text{eval}} = T \cdot W.$$
   Trailing $(N - N_{\text{warm}}) \bmod W$ references are discarded so all windows have equal length $W$.
4. **Compulsory First-Touch Misses:**  
   A reference $r_i$ ($i \ge N_{\text{warm}}$) is a compulsory miss if $r_i \notin \{r_0, \dots, r_{i-1}\}$. In high-churn FIU traces (e.g., `fiu_ikki_test`: $N = 500{,}000$, $\text{WSS} = 326{,}035$), at least $65.2\%$ of all references are distinct objects, imposing a high irreducible compulsory-miss floor ($\ge 31\%$ across FIU traces) regardless of replacement policy.

---

## 3. Reproducible Conversion Pseudocode & Worked Example

```text
ALGORITHM: ConvertOracleGeneralPrefix(stream, N_max)
  ids <- empty map<u64, u32>
  out <- empty array<u32>
  while len(out) < N_max and stream has 24-byte record (ts, oid, sz, nxt):
      if oid not in ids:
          ids[oid] <- len(ids)
      append ids[oid] to out
  return out, len(ids)
```

**Worked Example:**  
Suppose raw 24-byte records yield object IDs `oid = [9001, 42, 9001, 777, 42, 888]`:
1. `9001` $\to$ unseen $\to$ `ids[9001] = 0`, emit `0`.
2. `42` $\to$ unseen $\to$ `ids[42] = 1`, emit `1`.
3. `9001` $\to$ seen $\to$ emit `0`.
4. `777` $\to$ unseen $\to$ `ids[777] = 2`, emit `2`.
5. `42` $\to$ seen $\to$ emit `1`.
6. `888` $\to$ unseen $\to$ `ids[888] = 3`, emit `3`.  
Output `.bin`: `[0, 1, 0, 2, 1, 3]` ($N = 6$, $\text{WSS} = 4$, `max_id = 3`).

---

## 4. Comparability Effects & Dataset Licensing

1. **Unit & Granularity Heterogeneity:** `real_app_pageref` and `instrumented_program` represent 4 KiB page references (with multi-page `read`/`write` expansion in `pc_trace.c`), whereas `fiu_public` and `pdl_public` treat each block/KV `oid` as a unit-size object (ignoring `_sz`). Thus cache capacity $C = f \cdot \text{WSS}$ represents page slots in the former and object/block slots in the latter.
2. **Post-`mmap` Fault Blindness:** `pc_trace.c` logs `mmap()` page ranges at map time, not hardware page faults occurring on subsequent memory loads/stores.
3. **Train/Test ID Offset in FIU:** `fiu_*_test` traces retain global IDs (`max_id > wss`), which triggered the pre-fix `NP` out-of-bounds bug resolved in `src/pathA_sim.cpp:1594`.
4. **Licensing & Redistribution:**
   - `real_app_pageref` & `instrumented_program`: Original artifacts, CC-BY-4.0 (redistributable; `traces_real/*.bin` checksummed in `traces/SHA256SUMS`).
   - `fiu_public` & `pdl_public`: Obtained from CMU PDL `cacheDatasets` (`https://pdl.cmu.edu/CacheEviction/index.shtml`); **upstream-only** (non-commercial academic terms; raw `.bin` files excluded from public redistribution).
