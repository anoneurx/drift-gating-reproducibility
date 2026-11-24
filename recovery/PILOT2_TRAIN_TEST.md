# Pilot 2: proper train/test search for a better DA configuration

**Status: legitimate protocol, real results — still not insertable into the
current paper** (different simulator, see below).

## Protocol

1. **Training only** (seed 100 — deliberately non-overlapping with the fresh
   seed-5001 family; `--seed 1001` would have generated phased traces up to
   seed 5008 and contaminated the test set): 15 stable + 32 non-stable traces.
2. Swept 12 configurations: candidate set {4, 5, 6} × cost margin K ∈
   {0, 0.05, 0.1, 0.2}. Then swept evaluation delay ∈ {2, 5, 10, 20}.
3. Selected the best on **training**: 5 candidates (add S3-FIFO, not ARC) with
   K = 0 and evaluation delay 10.
4. Evaluated **once** on untouched fresh traces (seed 5001, 30 stable +
   80 non-stable). No tuning after this step.

Files: `sim_study.cpp`, `training_sweep_best.csv`, `fresh_train_test_results.csv`,
`fresh_train_test_detection.csv`.

## Fresh-trace results (80 non-stable, mean miss ratio)

| Method | Miss | DA vs it (paired Wilcoxon) |
|---|---|---|
| **DA (5 cand, K=0)** | **0.4529** | — |
| S3-FIFO | 0.4683 | DA better, p = 0.090 (marginal) |
| 2Q | 0.5220 | DA better, p = 2.3e−09 |
| ARC | 0.5287 | DA better, p = 8.5e−10 |
| LPR-style | 0.5329 | DA better, p = 2.2e−09 |
| LFU-A | 0.5461 | DA better, p = 5.2e−11 |
| LeCaR | 0.5509 | DA better, p = 3.0e−11 |
| CLOCK | 0.5594 | DA better, p = 2.1e−11 |
| LRU | 0.5700 | DA better, p = 1.4e−11 |
| FIFO | 0.6001 | DA better, p = 1.0e−12 |
| MRU | 0.9352 | DA better, p = 7.9e−15 |
| **ContShadow** | **0.4228** | **DA worse, p = 6.3e−06** |

* DA is **20.5% better than LRU** (up from 12.9% for the original 4-candidate
  configuration in this simulator).
* DA beats **10 of 11** baselines; 9 of them at p < 0.001. S3-FIFO is a marginal
  win (p = 0.090).
* On 30 stable traces: DA 0.3071, S3-FIFO 0.3301, LRU 0.5186.
* Cost trade-off: DA 63.1 ns/ref with 6.47 shadow evaluations and 2.36 switches;
  ContShadow 124.8 ns/ref with 27.39 shadow evaluations. ContShadow buys its
  lower miss ratio with ~2× the time and ~4× the shadow work.
* No configuration in either sweep beat ContShadow on training miss ratio —
  the gated controller cannot match continuous shadow evaluation on misses
  without paying its cost. Evaluation delay 10 (the original) was best.

## Why this still cannot be pasted into the paper

The unmodified independent simulator gives LRU = 0.5700 and DA = 0.4966, while
the paper reports 0.477 and 0.410. The 0.4529 figure belongs to a different
simulator with documented assumptions; mixing it with the published tables
would be scientifically invalid.

## What to do with it

This is strong evidence that the reviewer's candidate-set suggestion works:
once the original simulator and seeds arrive, repeat the exact 4→5 candidate
change (add S3-FIFO), re-run with the original train/fresh split, and rebuild
Tables VI–XI from raw per-trace data. Report ContShadow honestly as the
higher-accuracy / higher-cost alternative.
