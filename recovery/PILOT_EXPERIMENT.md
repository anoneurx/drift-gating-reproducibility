# Pilot experiment: widening DA's shadow candidate set

**Status: run and reproducible, but NOT publishable in the current paper.**
See "Why this cannot go into the paper" below.

## What was done

The reviewer noted that DA's candidate set is `{LRU, LFU-A, 2Q, MRU}` and
excludes S3-FIFO and ARC, so the S3-FIFO comparison does not test drift gating.
A pilot test of that suggestion was run using the **independent** simulator in
`../sim.cpp`, which is written from the paper text and is not the authors' code.

* `../sim.cpp` — unmodified, 4 candidates (baseline)
* `../sim_ext.cpp` — same code with `mkCand()` extended to 6 candidates:
  IDs 4 = S3-FIFO, 5 = ARC; all `Eval` arrays and candidate loops widened to
  `NCAND = 6`. Nothing else changed.
* Both runs: 110 traces (30 stable + 80 non-stable), seed 5001, C = 1000,
  p = 0.2, W = 2000, same defaults as the paper.
* Raw per-trace data: `pilot_baseline_results.csv`,
  `pilot_extended_results.csv`, `pilot_extended_detection.csv`.

## Results (non-stable mean miss ratio, lower is better)

| Method | 4 candidates | 6 candidates |
|---|---|---|
| LRU | 0.5700 | 0.5700 |
| LPR-style | 0.5329 | 0.5329 |
| S3-FIFO | 0.4683 | 0.4683 |
| **DA (gated)** | **0.4966** | **0.4559** |
| ContShadow (ungated) | 0.4714 | 0.4310 |

* DA improves by **0.0407 miss ratio (8.2% relative)**.
* With 6 candidates DA beats S3-FIFO on the mean (0.4559 vs 0.4683, 2.6%) and
  in **all four** scenarios: abrupt 0.3758 vs 0.4057, gradual 0.4410 vs 0.4411,
  recurring 0.4009 vs 0.4119, composite 0.6061 vs 0.6146.
* Stable traces: DA 0.3071 (vs 0.3217 with 4 candidates), still ahead of
  S3-FIFO (0.3301) and LRU (0.5186).
* Switching drops from 3.11 to 2.55 per non-stable trace; shadow evaluations
  rise slightly (6.14 → 6.47).

**But:** paired Wilcoxon DA vs S3-FIFO gives **p = 0.298** — DA wins 37 traces
and loses 43. The better mean comes from a few large wins, not consistent
per-trace superiority. And ungated ContShadow (0.4310) still beats gated DA.

## Why this cannot go into the paper

1. **Different simulator.** The unmodified independent simulator produces DA
   = 0.4966 and LRU = 0.5700, whereas the paper reports 0.410 and 0.477.
   Inserting 0.4559 into the paper would mix two incompatible experiments.
2. **No statistical support.** p = 0.298 does not justify a superiority claim.
3. **Protocol.** The original paper freezes parameters on training traces and
   evaluates once on fresh traces. This pilot reran on the same traces used for
   the comparison, so it is a design study, not a confirmatory experiment.

## What it is good for

It is evidence that the reviewer's suggested change is **worth running on the
original simulator**. Once the original code and seeds arrive (see
`REQUEST_AND_VALIDATION.md`), repeat exactly this 4→6 candidate change, keep
the original train/fresh-trace split, recompute all tables from raw per-trace
data, and report the result — including if it remains non-significant.

Commands to reproduce:

```
g++ -O2 -std=c++17 -o /tmp/sim sim.cpp
g++ -O2 -std=c++17 -o /tmp/sim_ext sim_ext.cpp
/tmp/sim     --seed 5001 --out baseline.csv --det det1.csv
/tmp/sim_ext --seed 5001 --out extended.csv --det det2.csv
```
