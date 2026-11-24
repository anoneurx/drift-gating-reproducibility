# Research paper audit — Drift-Aware Adaptive Page Replacement

Date: 2026-11-22
Scope: `latex/main.tex` / `latex/main.pdf` (12 pages), `reproduction/` (source,
CSVs, analysis scripts), `recovery/` (provenance notes), and external
verification of the cited literature.

## Overall verdict

**Structurally complete but NOT yet claim-complete.** The paper compiles
cleanly, has all standard sections, tables, figures and references, and most
primary numbers are exactly reproducible from the released CSVs. However, a
small number of statements in the abstract, tables and limitations contradict
the released artifacts or the paper's own ablation table. Those statements
must be corrected before the paper is submission-safe. No change to the
experimental data is needed; the problems are in the write-up and in what the
artifacts actually contain.

---

## 1. Structural completeness — PASS (with omissions)

| Check | Result |
|---|---|
| Sections I–VIII, Appendix, Declarations, 38-item bibliography | Present |
| PDF build | 12 pages A4, 0 errors, 0 overfull boxes, no undefined refs/citations |
| PDF vs delivered copy | `latex/main.pdf` == `Drift_Aware_Page_Replacement_Revised_Fixed.pdf` (MD5 `2cd35bc6…`) |
| Figures 1–7 | Present and referenced |
| Tables I–IX, Table (hypotheses), Appendix table | Present, but the last two are **never cited in the text**, and H1–H4 are **never defined** (only used in Table X and one sentence in §VI). This is a real completeness gap. |
| `figs/fig8_sensitivity.png`, `figs/fig9_capacity.png` | Present but unused (harmless leftovers) |

---

## 2. Claims that ARE verified

### 2.1 Primary experimental numbers (reproduced exactly)

`python3 reproduction/analyze_main_study.py` reproduces every number in
Tables VI–VIII and the cost/detection sections from raw CSVs:

- DA 0.453 [0.423, 0.484], LRU 0.570, S3-FIFO 0.468, ContShadow 0.423, OPT 0.302.
- DA 20.5% below LRU; DA–S3-FIFO −0.0154, Holm p = 0.09044 (not significant);
  DA–ContShadow +0.0301, Holm p = 1.25e−5 (DA significantly worse).
- Eight of ten paired comparisons significant at adjusted p < 0.001.
- Ablation: noShadow 0.619; noPurge 0.453; noS2 0.456; noCost 0.453; noDwell 0.453.
- Shadow evaluations 6.47 (DA) vs 27.39 (ContShadow) → 76.4% reduction.
- Detection 278/380 = 73.2%, median delay 2,000, 169 spurious, 1 stable false
  confirmation after reference 100,000.
- Cost: DA 67.4 ns/ref, LRU 25.1, S3-FIFO 28.5, ContShadow 133.4 → 2.7× and 2.4×.

I also recomputed the ten Wilcoxon tests with SciPy's exact procedure: the
p-values and Holm adjustments match the paper's script to displayed precision.

### 2.2 Real-program appendix (reproduced from `whole_program_holdout_results.csv`)

Column means match Table XI exactly: OPT 0.1573, S3-FIFO 0.2623, DA 0.2631,
ContShadow 0.2631, LRU 0.2914, etc. DA–S3-FIFO = +0.0007; bootstrap CI is
[−0.0038, +0.0050] with 10k resamples (paper reports −0.0037, a seed-level
difference of 0.0001). Treat the appendix CIs as approximate, since no script
generates them.

### 2.3 Literature verification — PASS

All 15 reviewed works [15]–[29] plus [34] exist as claimed. Verified via
Crossref, arXiv API, Zenodo API and publisher pages:

- [15] 3L-Cache: 4,855 traces (USENIX FAST'25 abstract) — correct.
- [16] LPR: LRU/MRU regret-based switching (Scientific Reports 15, 4721) — correct.
- [17] EACLOCK DOI 10.1109/TKDE.2026.3724159 — resolves; DOI metadata gives Yuan et al., *IEEE TKDE* 38(11), 7387--7401, Nov. 2026, matching the citation; the CSDL/IEEE pages resolve to the same title.
- [18] Clock2Q+ DOI 10.14778/3827998.3828002 — resolves; "up to 28.5% lower
  miss ratio than S3-FIFO on metadata traces" is a correct "up to" claim.
- [19] S4-FIFO, OSDI'26 — exists; description correct.
- [20]–[27] arXiv IDs/titles/dates all resolve.
- [28] arXiv:2609.28870 — exists.
- [29] Zenodo 10.5281/zenodo.20576370 — DOI and journal page resolve; Patel
  Nilen and Himanshu Maniar, *Int. J. Sci. Res. Technol.* 3(6), 556--564, 2026,
  with matching title. The abstract confirms "ARC highest on average" and
  workload-dependent ranking.
- [34] Acme — abstract confirms "at most 16%, 4% on average" vs optimal mode.

### 2.3a Reviewer-flagged references — PASS (2026-11-24)

- Main-paper [12] / older [29] (Patel & Maniar): kept, with DOI URL and journal
  article URL added to all bibliography sources.
- Main-paper [27] / older [17] (EACLOCK): kept, with DOI URL and Nov. 2026 issue
  date added to all bibliography sources.
- Supplement [41] / older [39] (CMU PDL): kept, but the licence wording was
  narrowed. The cache-eviction project page links to `cacheDatasets`; the FTP
  `fiu/` listing contains `fiu_madmax-110108-112108.oracleGeneral.zst` (HTTP
  200, Content-Length 3,189,409). The README specifies zstd 24-byte records and
  citation papers but no dataset-specific licence. PDL's copyright page says
  server materials are provided on a non-commercial basis; it does not grant a
  named dataset licence. Manuscript text now says exactly this. Details are in
  `REFERENCE_VERIFICATION.md`.

### 2.4 Simulator sanity checks — PASS (with caveat below)

Independent run on a 1,200-page loop at C=1,000: LRU 1.000, MRU = OPT = 0.165.
Matches the paper's stated sanity checks.

---

## 3. Claims that are NOT verified / contradicted (fix before submission)

Severity: P1 = blocking for claim validity, P2 = important, P3 = documentation.

| # | Sev | Claim in paper | Problem | Evidence |
|---|---|---|---|---|
| 1 | P1 | Table IX: at C=500 DA 0.560, LRU 0.689, 2Q 0.638, S3-FIFO 0.578, ContShadow 0.541, OPT 0.371 (`main.tex:804–824`) | **Stale numbers.** Released `main_study_C500.csv` gives DA 0.580, LRU 0.693, 2Q 0.654, S3-FIFO 0.590, ContShadow 0.555, OPT 0.434. | `analyze_main_study.py` capacity_tables() |
| 2 | P1 | Table II: "removing [recency-filtered migration] costs 0.022 miss ratio" (`main.tex:391`) | **Contradicted by the paper's own ablation**: DA 0.453 vs DA-noPurge 0.453 (Δ = 0.000). The 0.022 belongs to the discarded first report. | Table VIII; ablation CSV |
| 3 | P1 | "Candidate set is {LRU, LFU-A, 2Q, MRU}" (§V-C, `main.tex:521–523`); Table II "S3-FIFO is not a candidate" (`main.tex:390`); Limitations "main candidate set excludes … S3-FIFO" (`main.tex:935–937`) | **Contradicted by protocol and code**: training selected five candidates by adding S3-FIFO (`main.tex:508–510`); `sim_full.cpp` with `--ncand 5` includes S3-FIFO as candidate id 4; stable-trace gain is credited to start-up selection. | `sim_full.cpp:336–340, 367, 373`, `run_main_study.sh:18` |
| 4 | P1 | "KS confirmation gave no measurable benefit, so the implemented mechanism is a CUSUM trigger plus a cost margin rather than a two-stage statistical gate" (Abstract `main.tex:36–37`, §V-I `main.tex:852–854`, §VI `main.tex:900–903`, Conclusion `main.tex:965–966`) | **Misdescribes the released implementation**: `Params::useKS = true` by default and the primary run does not disable it. Correct phrasing: KS was implemented, showed no measurable benefit (0.453 → 0.456 when removed), so the *effective* mechanism was a CUSUM trigger; it was not removed. Also the cost margin is K = 0 in the frozen configuration, so it was inactive. | `sim_full.cpp:333–335, 393`, Table V, Table VIII |
| 5 | P1 | "CAR, LIRS, CLOCK-Pro [36], CACHEUS, 3L-Cache … were not implemented" (`main.tex:484–485`); "MGLRU baseline deliberately not claimed" (`main.tex:932–934`, `1036–1038`) | **False as written**: `sim_full.cpp:445–447` implements CAR, LIRS, CLOCK-Pro, CACHEUS, 3L-style, MGLRU-style and DIP-set-duel, and all appear in the raw CSVs (main and appendix). They are simply *not reported in the main tables*. | code + `main_study_results.csv`, `whole_program_holdout_results.csv` |
| 6 | P1 | "the offline optimum is never exceeded" (`main.tex:433–434`) | **False in the artifacts**: 38 traces in `main_study_results.csv` have a policy below OPT (e.g. recurring seed 8006: S3-FIFO 0.17031 vs OPT 0.23615). Cause: OPT minimises misses over the *whole* trace, including the warm-up, so it is not a strict lower bound for warm-up-excluded misses. Do not use OPT as a hard bound, or fix OPT to optimise only the post-warm suffix. | scripted check over all CSV rows |
| 7 | P2 | "a four-cluster bootstrap … is reported in the Appendix" (`main.tex:620–622`) | The Appendix only mentions it (`main.tex:988–990`) without reporting values. `scenario_clustered_bootstrap_results.csv` shows DA–S3-FIFO cluster CI [−0.0294, −0.0048], which **excludes zero** and conflicts with the non-significance claim. Report the values with the 35-resample caveat, or reword to "discussed, not reported". | CSV rows 2–12 |
| 8 | P2 | Switching rule Eq. (1) `((LCB(Δπ)/B_raw) H − K > 0)` (`main.tex:560–563`) | Code computes `(lcb / p / Braw) * H − K` (`sim_full.cpp:375`). The printed formula omits the sampling-rate rescaling `/p`. Redefine Δπ as per-*raw*-reference gain or add `/p`. | code vs equation |
| 9 | P2 | "parameters were fixed on training traces" with the released simulator (`main.tex:38–40, 412–418, 506–513`) | The selection sweep ({4,5,6} × K × delay) is **not reproducible from the package**: `run_main_study.sh` hardcodes the winner; no sweep script/results are released. `recovery/PILOT2_TRAIN_TEST.md` states the sweep used `sim_study.cpp`, a different simulator from `reproduction/sim_full.cpp`. Release the sweep script/results or soften the claim. | `run_main_study.sh:18–25`, PILOT2 doc |
| 10 | P2 | H1–H4 outcomes reported in Table X (`main.tex:831–845`) and referenced in §VI (`main.tex:908–909`) | Hypotheses are **never stated anywhere**; "H3 budget" and "H4 threshold" are never defined. Add an explicit hypotheses paragraph (or delete the table and the sentence). Tables X and XI are also never cited in text. | full-text search |
| 11 | P3 | Appendix claim "significantly better than 2Q, ARC, DIP, LRU and LPR-style" (`main.tex:1033–1035`) | CIs are not generated by a released script and shift slightly with bootstrap seed; with 10 program clusters and many tied/zero differences, percentile bootstrap CIs are fragile. Label as exploratory. | recomputation from holdout CSV |
| 12 | P3 | Supporting documentation | `latex/CHANGELOG.md` contains several mutually contradictory "authoritative final" sections (top says primary study re-run; lower sections say "Tables VI–XI remain the original"). `recovery/PILOT2_TRAIN_TEST.md` says its numbers "cannot be inserted" although they are now the primary result. Archive or rewrite the stale sections so an auditor can trace provenance. | CHANGELOG lines 8–83 vs 529–602 |

---

## 4. Claim language guide

### Safe to claim as written (after fixing the contradictions above)
- "On 80 generated non-stable traces, DA reduced mean miss ratio by 20.5% vs LRU."
- "DA was not significantly better than S3-FIFO (Holm-adjusted p = 0.09)."
- "Continuous shadow evaluation had a 0.030 lower mean miss ratio than DA (p < 0.001)."
- "Gating cut shadow evaluations by 76% relative to continuous evaluation, at a miss-ratio cost in the generated study."
- "The KS stage, migration purge and dwell rule produced no measurable change in miss ratio in this study."
- "Simulated time per reference: DA ≈ 2.7× LRU and 2.4× S3-FIFO (not kernel latency)."
- "Detection: 278/380 boundaries with median 2,000-reference delay under generated phase boundaries."
- "On ten instrumented programs DA tied S3-FIFO and beat LRU by 9.7%; DA cost 2.5× S3-FIFO."
- "The 15-work review links adaptive replacement, drift detection and emerging memory systems; key quantitative statements about those works are accurate."

### Claim only with an explicit caveat
- "Cost-aware switching" — K = 0 in the frozen configuration; the margin did not constrain switches.
- "Statistically gated detector" — KS was enabled but contributed no measurable benefit; reuse-time p-values are not calibrated under dependence/ties.
- "Significantly better than eight of ten baselines" — valid only for the ten listed paired comparisons on generated traces sharing five generators; not evidence about real workloads.
- "Offline optimum" — report as a reference point, not a guaranteed lower bound for post-warm-up misses.
- "Reproducible" — primary tables yes; parameter sweep and appendix CIs no.

### Do NOT claim
- DA is superior to S3-FIFO, ContShadow or the best adaptive baseline.
- Equal miss ratio at 76% less shadow work in the main study (true only in the ten-program appendix, as a tie).
- A two-stage statistical gate was validated, removed, or necessary.
- The KS stage, purge, cost margin or dwell rule improved accuracy (no measurable effect).
- MGLRU, set-dueling or the extra principle-level baselines were absent from the implementation.
- Kernel page-fault/reclaim latency, production traces, systematic-review completeness, or a generalisable 73.2% detection rate.

---

## 5. Minimal edit list (highest impact first)

1. Regenerate Table IX from `main_study_C500.csv` (or mark clearly as non-reproducible).
2. Delete "0.022 miss ratio" from Table II; point to the ablation showing no measurable effect.
3. Unify candidate-set description: either say the five-candidate set including S3-FIFO was used everywhere, or rerun with four; current text alternates.
4. Replace "implemented mechanism is … not a two-stage statistical gate" with "KS was enabled but gave no measurable benefit; the effective trigger was CUSUM plus shadow evaluation (K = 0)."
5. Change "were not implemented" to "implemented in the released simulator but not reported in the main tables", and likewise for MGLRU-style.
6. Remove/repair "offline optimum is never exceeded".
7. Report the cluster-bootstrap numbers (with the 35-resample warning) or remove the claim that they are reported; explain that the scenario-clustered CI for DA–S3-FIFO excludes zero.
8. Fix Eq. (1) for the `/p` factor.
9. Add the sweep script/results to the package or soften the training-selection claim.
10. Define H1–H4, cite Tables X and XI in the text, and clean the CHANGELOG.

---

## 6. Evidence commands (all run without modifying the paper)

```sh
cd reproduction
python3 analyze_main_study.py                    # Tables VI–VIII, cost, detection, capacity
python3 - <<'PY'
import csv,collections
from statistics import mean
rows=[r for r in csv.DictReader(open('main_study_C500.csv')) if r['scenario']!='stable']
d=collections.defaultdict(list)
for r in rows: d[r['method']].append(float(r['miss_ratio']))
print({m: round(mean(v),4) for m,v in d.items()})
PY
```
