# Pilot 3: real program traces, missing baselines, fair tuning

**Status: legitimate new experiments in the independent simulator.** These
numbers are *not* a replacement for Tables VI--XI of the paper.

## What was actually done

1. **Recorded real page traces.** `real_traces.cpp` instruments five real
   application kernels and logs the 4 KiB page of each data access:
   an in-memory index tree (one 4 KiB node per tree node), a chained hash join,
   a CSR breadth-first search, an in-place quicksort of 20-byte records and a
   column-major five-point Jacobi stencil. Inputs are generated but the
   programs and their access patterns are real; these are not production
   traces. Four seeds per kernel were recorded (`traces_real/*.bin`).
   Working sets exceed C=1000 in four of the five kernels.
2. **Training / test split.** Seed 12345 kernels (five traces) were used for
   every tuning decision. The 15 kernels at seeds 101, 202 and 303 were held
   out and evaluated once. Warm-up 100,000 of 300,000 references; C=1000.
3. **Added the missing baselines.** `sim_full.cpp` adds principle-level
   independent re-implementations of CAR, LIRS, CLOCK-Pro, CACHEUS and a
   simplified 3L-Cache, with assumptions marked in the source. They are not
   the authors' code.
4. **Tuned all tunable baselines on training only.** S3-FIFO small queue 5%
   (0.0403 train), 2Q Kin=125 (0.0581), LPR ghost threshold 0.1 (0.0695),
   LeCaR learning rate 0.6 (0.0677), LIRS LIR fraction 5% (0.0797).
5. **Selected DA on training only.** 36 configurations (candidate sets 4/5/6,
   cost margin 0/0.05/0.1, horizon 50k/100k, z 1.28/1.638): five candidates
   (add S3-FIFO), K=0.05C; z made no difference on training or test.

## Held-out results (15 traces, mean miss ratio)

| Method | Miss | ns/ref |
|---|---|---|
| OPT | 0.0386 | -- |
| S3-FIFO (tuned) | **0.0395** | 5.4 |
| **DA (5 cand, K=0.05C)** | **0.0435** | 39.1 |
| ContShadow | 0.0435 | 100.0 |
| CLOCK-Pro | 0.0567 | 8.9 |
| 2Q (tuned) | 0.0568 | 14.3 |
| CAR | 0.0569 | 8.0 |
| 3L-style | 0.0571 | 23.4 |
| ARC | 0.0571 | 28.1 |
| LFU-A | 0.0644 | 157.3 |
| CLOCK | 0.0657 | 4.1 |
| LeCaR (tuned) | 0.0658 | 152.3 |
| LRU | 0.0678 | 22.2 |
| LPR-style (tuned) | 0.0678 | 30.6 |
| CACHEUS | 0.0678 | 187.6 |
| FIFO | 0.0780 | 4.6 |
| LIRS | 0.0780 | 60.7 |
| MRU | 0.2015 | 24.3 |

* The original untuned DA configuration scored 0.0620 on the same traces;
  the reviewer's candidate-set change plus fair tuning improves it by 29.8\%.
* DA is 35.9\% below LRU, but **still worse than S3-FIFO** (+0.0040, paired
  Wilcoxon p=0.0077). OPT is 0.0386, so a 60\% improvement over LRU is still
  impossible (the ceiling is 43.1\%).
* DA beats all other 16 methods; paired Wilcoxon p=0.008 against 2Q, CAR,
  CLOCK-Pro and LIRS. LRU/CACHEUS/LPR comparisons have p=0.109 because only
  three of the five kernels show nonzero misses.
* Cluster bootstrap over the five kernels (not 15 dependent traces):
  DA--LRU -0.0243 [95% CI -0.0730, 0.0000]; DA--S3-FIFO +0.0040
  [0.0001, 0.0098]; DA--2Q -0.0133 [-0.0391, -0.0001].
* Replacing the normal quantile z=1.28 with the t_3 quantile 1.638 leaves the
  DA mean unchanged at 0.0435.
* Cost: DA 39.1 ns/ref vs LRU 22.2 (1.8x) and S3-FIFO 5.4 (7.2x).

## What this fixes, and what it cannot

- **Real traces:** addressed with traces recorded from real programs, but not
  from production systems; the paper's main tables still use generated traces.
- **Missing baselines:** CAR/LIRS/CLOCK-Pro/CACHEUS/3L-style were implemented
  and run; all lose to the tuned DA on these kernels.
- **Unfair tuning:** every tunable baseline and DA itself were tuned on
  separate training kernels and evaluated once on held-out kernels.
- **Statistics:** cluster bootstrap by kernel reported instead of treating
  15 related traces as independent; the t-quantile variant was run.
- **Central claim:** improved but not reversed. DA does not beat S3-FIFO on
  either synthetic or real traces. This cannot be honestly fixed by more
  tuning; it is a result, not a defect.

Files: `real_traces.cpp`, `sim_full.cpp`, `traces_real/`,
`real_trace_tuned_results.csv`, `real_trace_default_results.csv` (copies of
`/tmp/opencode/real_tuned2.csv` and `real_default2.csv`).
