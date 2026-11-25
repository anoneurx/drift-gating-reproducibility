# Path A extension result: the single-trace gate did not replicate

**Decision:** `PATH_A_STANDS`  
**Design:** `PATH_A_EXTENSION_PROTOCOL.md` fixed at 2026-11-25T10:08:54Z; Amendment 1 fixed at 2026-11-25T16:36:57Z.  
**Data:** `reproduction/pathA_oracle/results_extension/`  
**Raw checker:** `FAILURES: 0`.

## What was run

Ten additional FIU records derived from verified CMU PDL `cacheDatasets/fiu/`
sources, using the same oracle settings as the primary study:

- 2,000,000-reference prefixes for online, webmail+online combined, casa,
  webmail, webresearch, homes, ikki, and madmax; madmax has only 918,010 refs
  and uses all available records under Amendment 1.
- two non-overlapping 500,000-reference segments from the online trace: refs
  1,000,001--1,500,000 and 1,500,001--2,000,000.
- 3 WSS-relative capacities x 2 window lengths (50,000 and 100,000).

Output: 120 summary rows, 1,200 policy rows, 1,347 window rows, 60 family /
capacity / window groups. Source and converted-trace SHA256 hashes are in
`results_extension/manifest.csv`; raw traces are not stored in the repository.

## Pre-specified gate

The extension required **both** conditions at the charged 100,000-reference
oracle:

1. at least two FIU-online-derived **distinct traces** with charged gain
   `>= 0.02` at some capacity; and
2. at least one unseen-family group (`fiu_casa` or
   `fiu_webmail_online_combined`) meeting the original worthwhile-gain bar.

Result:

| Condition | Required | Found | Status |
|---|---:|---:|---|
| Distinct FIU-online replicas | 2 | 1 | FAIL |
| Unseen-family groups | 1 | 0 | FAIL |

The only FIU-online record with charged gain `>= 0.02` at 100,000 references was
`fiu_online_seg1p5m_2m` at `C=8116`, gain `0.04656`, 3 oracle switches. The
50,000-reference charged gains `0.02388` at `C=4058` and `0.02196` at `C=8116`
came from the **same** trace. These are repeated observations from one segment,
not replication across traces.

No unseen-family group met the bar. At 100,000 references, `fiu_casa` charged
gains were `0.00000`, `0.00068`, and `-0.00447`; `fiu_webmail_online_combined`
charged gains were `0.00000`, `-0.00182`, and `-0.05089`.

## Full extension counts

- Charged groups meeting the bar: **2/60** at 50,000 references and **1/60** at
  100,000 references — all from `fiu_online_seg1p5m_2m`.
- Zero-cost groups meeting the bar: **9/60** at 50,000 and **4/60** at 100,000,
  spread across FIU-online, ikki, madmax, and webmail. These are upper-bound
  observations, not deployable gains.
- Mean charged gain across 60 trace x capacity x window rows: **-0.00595**.
- Mean zero-cost gain across the same rows: **0.01085**.
- Best static policy was S3-FIFO in 30/60 rows; six distinct policies won at
  least one row.

## Interpretation

The original 100,000-reference gate was mechanistically valid but fragile. The
extension found the gain again on a later segment of the same FIU-online source
trace, but not on a second distinct trace and not on either unseen family.
Therefore the gate does not survive the pre-specified replication test.

This strengthens the Path A conclusion: on all available real/public evidence,
switching has little demonstrated headroom over the best static policy. The
remaining anomaly is trace-specific, not family-level or cross-family.

## Scope limits

- The FIU-online segments come from one source file; they are not independent
  workloads.
- Every extension family-capacity group contains one trace, so bootstrap CIs
  are degenerate.
- FIU/PDL traces are converted block/object traces, not native VM page traces.
- No learned-policy baseline or libCacheSim cross-check was added by this
  extension.
- The primary `results/` and `results_w100000/` directories were not modified.
