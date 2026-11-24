# Recovering the original experimental material

The published Tables IV–XI cannot be modified or extended without the code and
raw data that produced them. `../sim.cpp` is an independent re-implementation
written from the paper text and is explicitly **not** the authors' code; its
numbers will not match the published tables.

Nothing is embedded in either PDF (`pdfdetach -list` reports 0 embedded files)
and no archives/CSVs exist in this folder. Request the following from the
corresponding author or supervisor (Mohsin Ghouri).

## 1. What to ask for

| # | Item | Why it is needed |
|---|---|---|
| 1 | Full simulator source at **round 2** (after amendment A1) | All results below come from round 2; round 1 used different state migration |
| 2 | Trace generator + the **exact seed lists**: 26 training traces, 110 test traces (seeds 1001+), 110 fresh traces (seeds 5001+) | Without the seeds no number can be reproduced |
| 3 | Raw **per-trace** results CSV (every method, every trace): miss ratio, switches, shadow evaluations, timings | Needed to recompute means, CIs, Wilcoxon and Holm p-values |
| 4 | Per-trace **detection log**: boundaries, alarms, confirmations, delays, spurious alarms | Needed for 269/280, 1,999 refs, 11 spurious, 0 false on stable |
| 5 | Exact implementations of **S3-FIFO, LPR-style, ContShadow, LeCaR** used in Tables VI–VIII | The paper says these are re-implementations "of the principle"; the local `sim.cpp` versions are guesses |
| 6 | Config file with the Table V parameters and the Eq. (1)–(3) constants | Confirms `p = 0.2`, `C_s = 200`, `K = 0.1C`, `z = 1.28`, etc. |
| 7 | Statistical analysis scripts (bootstrap CIs, Wilcoxon, Holm, KS) | Required to regenerate Table VII and the H1–H4 outcomes |
| 8 | The "supplementary material" promised in the Declarations | The current PDF claims it exists; if it does not, that sentence must be corrected |

Ask for a **tagged commit / dated archive**, not "the latest version", so the
published numbers can be tied to a specific code state.

## 2. Validate before changing anything

Do **not** tune until the recovered code reproduces the published tables
exactly. Check every line below; all must match.

| Table / claim | Expected values |
|---|---|
| VI — non-stable miss, DA / LRU / S3-FIFO / LPR-style / ContShadow | 0.410 / 0.477 / 0.402 / 0.381 / 0.407 |
| VI — DA stable miss | 0.332 |
| VI — `vs LRU (%)` column | DA 14.2, S3-FIFO 15.9, LPR-style 20.2, ContShadow 14.6 |
| VII — DA minus LRU | −0.0676 [−0.087, −0.050], 68/8/4, p < 0.001 |
| VII — DA minus S3-FIFO | +0.0080 [−0.010, +0.026], p = 0.281 |
| VII — DA minus LPR-style | +0.0287 [+0.012, +0.048], Holm p = 0.332 |
| VIII — ablation DA | non-stable 0.410, stable 0.332, 1.70 switches |
| VIII — DA-noShadow / DA-noPurge | 0.497 / 0.432 |
| IX — sensitivity | p=0.2 → 0.410; p=0.05 → 0.431; W=5,000 → 0.484 |
| X — capacity | C=500 → 0.536; C=1,000 → 0.410; C=2,000 → **0.234** |
| XI — n / Top-1 / mean ratio | 162, 465, 467 / 0.62, 0.71, 0.78 / 1.47, 1.17, 1.17 |
| Detection | 269/280 boundaries (96.1%), median 1,999 refs, 11 spurious, 0 false on stable |
| Cost | LRU 10.1 ns, S3-FIFO 13.3, LPR-style 16.5, DA 65.1, ContShadow 141.4 → 6.4× LRU |

If any line fails, stop: the code is not the published version, and results
from it cannot be presented as an improvement to this paper.

## 3. Only then: legitimately improve the results

The reviewer-identified weakness is that the candidate set is
`{LRU, LFU-A, 2Q, MRU}` — it excludes S3-FIFO and ARC, so the comparison does
not test drift gating. The defensible experiment is:

1. Add S3-FIFO and ARC (and LPR-style if desired) as shadow candidates.
2. Keep the protocol identical: tune/freeze on the 26 training traces, then
   evaluate **once** on the 110 fresh traces (seeds 5001+).
3. Recompute all tables and statistics from the raw per-trace data.
4. Report honestly if DA still loses — do not re-tune on the test set.

Even if the code never arrives, the Declarations sentence about supplementary
material must be corrected; offer that as a separate one-line text fix.
