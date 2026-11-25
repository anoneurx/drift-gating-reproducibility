# Path A extension pre-specification: trace-replication test

**Timestamp (UTC):** 2026-11-25T10:08:54Z  
**Local HEAD at timestamp:** `ffc9f3768ef9a1e066d8077d80f67be26779faa7`  
**Status:** fixed before downloading, converting, or running any new trace.

> This is an additive diagnostic extension. It does **not** replace or retune the
> primary 78-trace experiment recorded in `PATH_A_PROTOCOL.md` and
> `PATH_A_RESULTS.md`. The primary results remain frozen.

## Motivation

The 100,000-reference sensitivity run opened `PATH_B_GATE` in one group only:
`fiu_online.cs.fiu.edu`, `C=15539`, one trace (`fiu_online.cs.fiu.edu_test`),
charged gain `0.04449`. That is not enough for a systems claim. The extension
tests two things:

1. whether the FIU-online gain replicates on additional parts of the same public
   trace; and
2. whether any **unseen family** shows a worthwhile charged gain.

## New traces, fixed before download

All sources are from the verified CMU PDL `cacheDatasets/fiu/` directory:
`https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/fiu/`.
Use is non-commercial research with citation; raw traces are not redistributed.

| Label | Source file | Conversion limit | Role |
|---|---|---:|---|
| `fiu_online_full2m` | `fiu_online.cs.fiu.edu-110108-113008.oracleGeneral.zst` | first 2,000,000 refs | more FIU-online evidence |
| `fiu_online_seg1m_1p5m` | same file | refs 1,000,001--1,500,000 | non-overlapping FIU-online segment |
| `fiu_online_seg1p5m_2m` | same file | refs 1,500,001--2,000,000 | non-overlapping FIU-online segment |
| `fiu_webmail_online_combined_2m` | `fiu_webmail+online.cs.fiu.edu-110108-113008.oracleGeneral.zst` | first 2,000,000 refs | unseen mixed family |
| `fiu_casa_2m` | `fiu_casa-110108-112108.oracleGeneral.zst` | first 2,000,000 refs | unseen family |
| `fiu_webmail_2m` | `fiu_webmail.cs.fiu.edu-110108-113008.oracleGeneral.zst` | first 2,000,000 refs | extend existing family |
| `fiu_webresearch_2m` | `fiu_webresearch-030409-033109.oracleGeneral.zst` | first 2,000,000 refs | extend existing family |
| `fiu_homes_2m` | `fiu_homes-110108-112108.oracleGeneral.zst` | first 2,000,000 refs | extend existing family |
| `fiu_ikki_2m` | `fiu_ikki-110108-112108.oracleGeneral.zst` | first 2,000,000 refs | extend existing family |
| `fiu_madmax_2m` | `fiu_madmax-110108-112108.oracleGeneral.zst` | first 2,000,000 refs | extend existing family |

`fiu_webusers-030409-033109.oracleGeneral.zst` remains excluded because the
FIU capacity was selected on that trace. The first 1,000,000 refs of the six
original FIU files are already represented by `public_split/` train/test; the
new FIU-online segments start at ref 1,000,001 so they are non-overlapping.

Conversion uses `reproduction/convert_public_traces.py`, which maps object IDs
to dense IDs on first touch and ignores timestamps and sizes, exactly as for the
existing FIU traces. A manifest records source URL, SHA256 of the compressed
source and converted `.bin`, refs, WSS, max ID, and capacities.

## Simulation and oracle settings

Identical to the primary protocol:

- capacities: `round(0.01*WSS)`, `round(0.05*WSS)`, `round(0.10*WSS)`, floored at 1;
- warm-up: `min(100000, floor(0.10 * trace_length))`;
- windows: 50,000 (primary extension) and 100,000 (sensitivity extension);
- switch cost: `C` misses, plus a zero-cost upper bound;
- 20 fixed policies from `reproduction/sim_full.cpp`;
- oracle assumes all policies are warm; initial choice free; ties by policy name;
- worthwhile gain: absolute miss-ratio reduction `>= 0.02` on at least `2/3`
  of traces in a family-capacity group;
- bootstrap: trace-level resampling, `B=10000`, seed `20261125`.

All new artifacts are additive under `reproduction/pathA_oracle/results_extension/`.
No frozen manuscript or main-study artifact is modified.

## Pre-specified extension decision

The extension is diagnostic and cannot overturn the primary negative result.

The `PATH_B_GATE` survives the extension **only if both** conditions hold at the
100,000-reference charged oracle:

1. at least **two** FIU-online-derived records have charged gain `>= 0.02` at
   some capacity; and
2. at least **one** unseen-family record (`fiu_casa_2m` or
   `fiu_webmail_online_combined_2m`) has a family-capacity group meeting the
   original worthwhile-gain bar.

If either condition fails, keep Path A and report the sensitivity gate as a
single-trace artifact. If both hold, the result is still only a gate for a
held-out-family feature rule and a learned-policy baseline, not a kernel result.

## Reporting

Report per trace/capacity/window for all new records, family aggregates with
bootstrap CIs, and a separate extension decision CSV. Keep the primary
`results/` and `results_w100000/` directories byte-identical.
