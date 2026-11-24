# Revision changelog — Drift-Aware Page Replacement

Source of truth for every change between
`Drift_Aware_Page_Replacement_Revised.pdf` (baseline) and `latex/main.pdf`.

---

## PHASE 10: INDEPENDENT CAPACITY PILOT (2026-11-24)

A reviewer noted that the FIU replay capacity $C=20{,}000$ had been chosen from
a pilot on `webresearch`, one of the six evaluated traces. Phase 10 was
registered in `PROTOCOL.md` **before** the trace was downloaded or converted.
The non-evaluation FIU trace
`fiu_webusers-030409-033109.oracleGeneral.zst` was streamed for exactly
1,000,000 records (WSS 72539; SHA256 in `phase10_capacity_pilot/manifest.csv`),
and the pre-registered seven-capacity grid re-selected $C=20{,}000$: the
smallest capacity with both miss ratios $\ge 0.01$ and an LRU--S3-FIFO gap
$\ge 0.10$ was $C=20{,}000$ (0.73590/0.52726, gap 0.20864; $C=10{,}000$ gave
0.74182/0.73317, gap 0.00865). No public performance number changed; only the
provenance paragraphs in both supplement trees were updated. The checker now
verifies the pilot manifest, all seven raw capacity points, the selection rule
and both supplements (499/499 PASS). The older `webresearch`-only pilot CSVs
are retained for provenance but are no longer the selection source.

## FINAL REPRODUCIBILITY PASS: PHASES 6--9 (2026-11-24, current authoritative for all later numbers)

All four phases were written into `PROTOCOL.md` before their runs; amendments
were recorded before affected runs. The frozen seed-5001 artifacts were not
modified (SHA256 verified by `reproduction/final_hygiene.py`).

* **Phase 6 (six further PDL families):** bounded 1M-reference prefixes of MSR,
  Alibaba, Tencent, CloudPhysics, Twitter and MetaKV were streamed with a SHA256
  manifest and replayed at 18 family$\times$capacity points. Means: S3-FIFO
  0.4683, ContShadow 0.4739, DA 0.4742, CLOCK 0.4973, LRU 0.4987; DA--S3-FIFO
  $+0.0059$ with Holm $p=0.0192$. DA is worse on these measured means; reported
  as a negative result, with no tuning.
* **Phase 7 (real asynchronous shadow worker):** additive `sim_full_async.cpp`
  built as `sim_async` with `-pthread`. Default deterministic columns and the
  detection CSV were verified byte-identical to `sim_full` (wall-clock
  `ns_per_ref` excluded by pre-run amendment). Three real repetitions gave
  0.5611/0.5676/0.5599 and paired async-minus-sync $+0.1082$/$+0.1147$/$+0.1070$;
  240 timing rows, 15,066 stale decisions, 1,192 applied results and 0 dropped.
  Reported as a negative result. The analytical `phase5/async_model.csv` is not
  presented as a prototype measurement.
* **Phase 8 (QEMU guest kernel):** Linux 6.6.1 built as user with recorded
  toolchain (`gcc-15 -std=gnu11`, bison 3.8.2, elfutils 0.191 libelf) and nine
  real fresh-boot runs (three each of fixed LRU, fixed MGLRU and a coupled
  userspace CUSUM controller). Build/boot failures and one complete but
  defective boot sequence were recorded in `PROTOCOL.md` and discarded before
  reporting. Parsed 191,370 real function-graph duration samples in 18 groups;
  only `handle_mm_fault` and `do_wp_page` produced samples. All nine runs have
  131,138 minor faults, zero refaults, zero `pgscan`/`pgsteal` deltas and zero
  controller toggles; cgroup `memory.max`/`memory.peak` files were empty. This
  is a null observation with real fault-path latency, not a reclaim-latency or
  in-kernel-DA result. No kernel DA policy and no kernel-faithful MGLRU baseline
  were built.
* **Phase 9 (compression without deleting results):** detail relocated to
  standalone supplements. Final `latex/main.pdf` is 11 pages with a 15-page
  supplement; `drift_gating_latex_source/main.pdf` is 10 pages with a 13-page
  supplement. Both mains have 0 undefined references and 0 overfull hboxes.
* **Traceability and hygiene:** `reproduction/check_paper_numbers.py` extended
  to **425/425 PASS**, including Phase 6--8 values read from generated CSVs and
  the LaTeX fragments. `claims_to_sources.csv`, `NOT_DONE.md`, `selfaudit.md`
  and `reproduction/README.md` record sources, discarded attempts and null
  results. `reproduction/final_hygiene.py` PASS. All LaTeX Phase 6--8 tables are
  generated from CSVs by `generate_phase_tables.py`; no hand-entered number.
* **Artifacts rebuilt:** both PDF trees, the DOCX from the final drift PDF,
  text extracts and stale preview pages; the required wording "DA is never the
  cheapest policy on the measured means" remains in both abstracts and the
  cost section.

---

## JOURNAL REVISION: TRACEABILITY, HONESTY, REPRODUCIBILITY (superseded by the entry above for all Phase 6--9 numbers)

Date: 2026-11-23. Triggered by a second rejection demanding strict claim-to-source
traceability, an honest negative/null-result framing, and reproducible public-data
checks. This revision changes the title, abstract, contributions, related work,
statistics, experimental artifacts, cost model and all generated figures. It also
adds a numeric consistency checker, three new raw-data experiments, and an explicit
NOT DONE list. No result was changed to look better; every newly reported number
comes from a real run of released code on real or generated traces.

### A. Abstract, title, framing (issue -> change -> evidence)

* **Title/abstract/contributions/conclusion inconsistent with a negative result** ->
  retitled "When Does Drift Gating Pay Off? A Reproducible Measurement Study of
  Drift-Aware Page Replacement"; abstract rewritten as a measurement study, 197
  words, five quantitative numbers {76, 0.030, 0.09, 15, 2.2}; contributions cut
  from four to three and conclusion aligned. Evidence: `latex/main.tex` abstract,
  "Introduction" contributions, "Conclusion"; word count verified on the built
  PDF via `pdftotext`.
* **Overstated mechanism** -> abstract and conclusion now state the effective
  mechanism is the CUSUM trigger plus sampled shadow evaluation, the KS stage
  showed no measurable benefit, and no validated statistical gate is claimed.
  Evidence: ablation Table VIII in `main_study_results.csv` (DA 0.453 vs
  DA-noS2 0.456); text in Sections I, V-F, VII.
* **Missing required comparison statement** -> abstract now says DA "is not
  significantly different from S3-FIFO (Holm-adjusted p = 0.09)". Evidence:
  `appendix`/`analyze_main_study.py` paired test, Holm-adjusted p = 0.09044;
  raw source `analysis_out.txt` and `check_paper_numbers.py`.
* **Required quantitative claims** -> 76% shadow-eval saving, 0.030 miss-ratio
  loss vs ContShadow, 15 real programs tying S3-FIFO at higher cost, break-even
  ~2.2 us: all present in the abstract. Evidence: `cost_model.csv`,
  `main_study_results.csv`, `whole_program_holdout_results.csv`,
  `real_trace_cost_15prog.csv`.

### B. Contributions and related work (issue -> change -> evidence)

* **Contributions listed a new algorithm and a validated gate** -> replaced with
  (1) controlled measurement vs continuous shadow evaluation and strong static
  baselines, (2) cost break-even model with measured fault-latency calibration,
  (3) reproducible negative/null-result protocol with ablations. Evidence:
  Introduction of `latex/main.tex`; no algorithm section claims novelty.
* **Related work missed direct comparators** -> added Acme (statistical cache-mode
  selection, [34]), DIP/DRRIP set dueling [37], MGLRU [38], ADWIN [7], SHARDS
  [14] and miniature simulation [13], with an explicit label of which statements
  are *direct observations from cited sources* and which are *inferred*. Evidence:
  Sections II--III of `main.tex`; `[37]`/`[38]` descriptions verified against
  the cited papers.
* **First-report history too long** -> reduced to one short paragraph in Section V;
  no first-report number is used in any claim. Evidence: single "A single earlier
  report..." paragraph; scan of `revised_paper.txt`.
* **Baseline count contradiction ("eleven" vs "ten")** -> one sentence explains
  that Table VI reports eleven non-proposed baselines and Table VII pairs DA
  against ten (MRU excluded). Evidence: `analyze_main_study.py` METHOD_ORDER and
  paired-test block.

### C. Experiments, statistics and cost (issue -> change -> evidence)

* **No public real-world trace results** -> downloaded six CMU PDL FIU block
  traces from `https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/fiu/`,
  converted prefixes with new `reproduction/convert_public_traces.py`, and ran
  the frozen controller with `--np 1048576 --C 20000 --warm 100000`. Raw output:
  `public_trace_results.csv`, `public_trace_detection.csv`, `public_pilot_C*.csv`.
  New Section V-I, Table "Public FIU Block Traces", reference [39] (URLs verified
  HTTP 200). Result: DA/ContShadow/LRU identical miss 0.6753, DA 0 switches,
  DA **Pareto-dominated by S3-FIFO** (0.5772 miss, 31.7 vs 82.5 ns/ref).
* **S3-FIFO absent from cost-accuracy comparisons** -> added to every cost table
  and figure, ablation table (0.468 miss / 28.5 ns/ref), cost-model CSV and
  break-even figure. `cost_model.py` now recomputes R = 783.28, direct break-even
  2196.2 ns (2.20 us), and an S3-FIFO/DA total-time crossover of 2.52 us.
  Evidence: `cost_model.py`, `cost_model.csv`, `fig8_breakeven.png`,
  `make_main_figures.py` fig7/fig8.
* **Uncertain interval basis** -> trace-level interval is now the primary
  uncertainty statement for every comparison; the 35-resample four-cluster
  bootstrap is labelled sensitivity-only and never a headline. Evidence:
  Sections V-D and Appendix of `main.tex`; `scenario_clustered_bootstrap.py`.
* **Stable-trace gain conflated with drift handling** -> added an explicit
  separation: stable DA 0.3071 with 0.80 switches / 1.73 evals vs LRU 0.5186,
  S3-FIFO 0.3301, ContShadow 0.3065; gain attributed to start-up selection, and
  not added to the drift-handling claim. Evidence: `main_study_results.csv`
  stable rows; `check_paper_numbers.py`.
* **Phase-aligned boundaries favour detection** -> added `--phase-offset` to
  `sim_full.cpp`; reran detection at offset 0 and 1370. Aligned run reproduces
  released detection exactly; offset 1370 detects 281/380 (73.9%) with 173
  spurious vs 278/380 (73.2%) and **169 spurious** at offset 0. Raw rows and
  per-scenario totals in `detection_offset0.csv`, `detection_offset1370.csv`,
  Table "Detection With and Without Epoch-Aligned Boundaries". Adding `--np`
  left miss ratios unchanged; only timing noise differed.
* **R and 2.2 us not recomputed from released code** -> `cost_model.py` rerun;
  R = 783.28, direct break-even 2196.2 ns, component break-even 2196.2 ns,
  implied evaluation cost 1.72 ms; S3-FIFO crossover 2.52 us. Evidence:
  `cost_model.csv`, text in Section V-J.
* **Cost-figure caveat** -> text now states break-even depends on unoptimized
  simulator timings; the ratio is more robust than absolute scale. Evidence:
  Section V-J, `prototype_fault_latency.cpp`, `fault_latency_results.txt`.

### D. Number cross-check (issue -> change -> evidence)

* **No systematic verification of numbers in abstract/tables/figures/text** ->
  created `reproduction/check_paper_numbers.py`, which reads the raw CSVs and
  text outputs and compares them with the manuscript values. Result: **139/139
  checks pass** (output captured in `consistency_check.txt`). It covers main
  study means, per-scenario values, stable-trace separation, ablations, cost
  ratios, capacity sensitivity, detection and offsets, public traces, cost-model
  quantities and appendix intervals. Any mismatch prints FAIL and exits 1.

### E. Deliverables and build

* Full revised text: `latex/main.pdf` and `latex/revised_paper.txt` (1068 lines).
* Final root PDF: `Drift_Aware_Page_Replacement_Journal_Revision.pdf` (15 pages).
* Build: two `pdflatex -interaction=nonstopmode -halt-on-error main.tex` runs,
  **0 errors, 0 overfull hboxes** (18 overfull from verbatim CSV/command listings
  fixed by removing the CSV header from the verbatim and reflowing the command
  with `\tiny` listings; remaining underfull hboxes are normal table padding).
* Scan: no TBD/placeholder strings; all required statements present in
  `revised_paper.txt`.
* Reference [39] added (CMU PDL cacheDatasets); reference list size 39.

### NOT DONE with real data in this session

1. Kernel-faithful MGLRU or other in-kernel replacement prototype (only a
   page-level MGLRU-style abstraction is simulated).
2. Production virtual-memory paging traces as primary evidence (public data are
   storage block/cache traces; real-program traces are 15 instrumented kernels).
3. In-kernel page-fault or reclaim latency measurements (only a user-space
   minor-fault microbenchmark is reported).
4. Full-shadow ranking-agreement validation of the sampled selector (not
   measured; H4 remains not evaluated).

---

## REVIEW-RESILIENCE REVISION (superseded by the entry above)

Date: 2026-11-23. Triggered by a second rejection. This revision is the first
that changes experimental artifacts, not only text: the selection sweep is
re-executed with the released simulator, the appendix interval script is
released, five real programs are added, and a cost break-even model with a
fault-latency calibration is added. Title and abstract were revised so that the
title question is answered with a measured break-even.

### Reproducibility
* **Selection sweep re-run with released code.** `reproduction/sweep_selection.py`
  runs all 48 configurations (candidate-set {4,5,6} x K {0,.05,.1,.2} x delay
  {2,5,10,20}) on the 15+32 training set and selects `ncand=5 K=0 edelay=10`
  (training non-stable miss 0.4400, zero stable false confirmations). Outputs
  `sweep_results.csv` and `sweep_selected.txt`. The earlier text that said the
  sweep "ran in the earlier simulator" / "is not re-executable" was removed.
* **Appendix interval script released.** `reproduction/appendix_intervals.py`
  generates the percentile intervals and Holm-adjusted p-values in
  `appendix_intervals.csv`. The contradictory phrase "not generated by a
  released script" was removed.
* **Training sizes made explicit.** `run_main_study.sh` now passes
  `--stable-per-prim 3 --per-scenario 8` (the simulator defaults are the 30+80
  test sizes), and runs `sweep_selection.py` first. `sim_full.cpp` gained
  `--da-only` and `--methods` filters for tractable sweeps and tuning.

### New evidence
* **Cost break-even.** `reproduction/cost_model.py` derives
  `T = N t0 + N m c_m + E c_e`; DA beats ContShadow iff `c_e > R c_m`, with
  `R ≈ 783`, i.e. a break-even miss cost of about **2.2 us**. New
  Section V-G (Cost Break-Even), Table
  `tab:breakeven`, Fig. `fig:breakeven`.
* **Fault-latency calibration.** `reproduction/prototype_fault_latency.cpp`
  measures a user-space 4 KiB first-touch minor fault at **1.98 us** and a
  refault after `MADV_DONTNEED` at **2.06 us** (resident access 16 ns). The
  paper explicitly labels this a user-space calibration, not a kernel prototype.
* **Five more real programs.** `real_traces.cpp` adds matvec, linkedlist,
  stringmatch, unionfind and binarysearch (15 programs x 4 seeds = 60 traces).
  Fifteen-fold whole-program holdout: DA 0.3304, S3-FIFO 0.3291, LRU 0.3540;
  DA--S3-FIFO +0.0013 [-0.0019, +0.0044]; no comparison survives Holm
  correction (smallest adjusted p = 0.096). Appendix table and text updated;
  the MGLRU-style baseline is explicitly not claimed as kernel MGLRU.

### Front matter and declarations
* Title changed to the question form "When Does Drift Gating Pay Off? A
  Reproducible Measurement Study of Drift-Aware Page Replacement".
* Student IDs removed. Author line now lists Muhammad Qasim (lead and
  corresponding, UMT Lahore and Anoneurx Research Lab,
  itskashie@anoneurx.com), Hunain Tahir (UMT), Hussain Ahmad (UMT) and Mohsin
  Ghaffar Ghouri (UMT, supervisor, now a co-author).
* Added Funding, Conflict of Interest and AI-use statements; the
  supervisor-only acknowledgment was removed because the supervisor is now an
  author.

### References and wording
* [17] EACLOCK and [29] Patel and Maniar are retained and now carry DOI and
  resolvable URL. Verified via Crossref (`10.1109/TKDE.2026.3724159`) and the
  Zenodo API (record 20576370). A verification note was added to
  `reproduction/README.md`.
* H3 and H4 wording changed from "pre-registered" claims to explicitly
  **post hoc** in Section V and in the threats-to-validity paragraph.

---

## AUDIT CONSISTENCY REVISION (superseded)

Date: 2026-11-22. Triggered by the completeness and claim audit in
`../AUDIT_REPORT.md`. This revision fixes textual contradictions without
changing any experimental data. The corrected Table IX values already present
from the earlier C=500 fix were preserved.

### Corrections applied
* **Claim language**: the frozen run used a cost-margin rule with **K = 0**, so no
  cost-aware switching claim is made. KS was **enabled** in the released run but
  gave no measurable benefit (0.453 versus 0.456 without it); the effective
  mechanism is described as a CUSUM trigger with sampled shadow evaluation, not
  a validated two-stage statistical gate. Abstract, introduction, H2, design
  lessons, threats, limitations and conclusion were aligned.
* **Configuration**: Table V now records K = 0 in the frozen run while retaining
  the design default 0.1C as context; Equation (1) includes the `/p` sampling
  rescaling used by `sim_full.cpp`.
* **Candidate set**: unified to the five-policy set
  `{LRU, LFU-A, 2Q, MRU, S3-FIFO}` in Table II, Section V-C and the limitations;
  ARC remains excluded from the controller's choices.
* **Ablations and baselines**: Table II no longer says migration purge costs
  0.022 miss ratio; the released ablation shows no measurable difference
  (0.453 vs 0.453). CAR, LIRS, CLOCK-Pro, CACHEUS, a 3L-style policy, an
  MGLRU-style policy and set-dueling DIP are described as implemented in the
  released simulator/CSVs but not reported in the main tables.
* **OPT**: described as a whole-trace reference point, not a strict lower bound
  on post-warm-up miss ratios.
* **Provenance**: the parameter sweep used an earlier simulator and is not
  re-executable from the released package; `run_main_study.sh` is described as
  replaying the frozen configuration. The main study is re-executable; the first
  report's protocol and numbers are not.
* **Statistics**: the scenario-clustered bootstrap now reports DA--S3-FIFO
  -0.0154 [-0.0294, -0.0048] with the 35-distinct-resample caveat, alongside the
  non-significant trace-level paired interval. H1-H4 are explicitly defined,
  the hypothesis table and appendix holdout table are cited, and the appendix
  comparisons are labelled exploratory.

### Verified build and delivery
* Two `pdflatex -interaction=nonstopmode -halt-on-error main.tex` runs from
  `latex/`: **12 pages, A4 (595.276 x 841.89 pt), 0 errors**, no undefined
  references or citations, and no overfull boxes. Underfull boxes in the wide
  comparison table and the long Table V row remain non-fatal.
* `latex/main.pdf` and `../Drift_Aware_Page_Replacement_Revised_Fixed.pdf` both
  have md5 **`c2bd1ba886a9974bb6389132304f0488`** after this rebuild.
* The previous "FINAL" headings below are retained only as historical
  provenance and are superseded by this section.

---

## Earlier final revision (historical — superseded by the audit revision above)

Triggered by the four rejections. The original simulator, seeds and per-trace
output were lost, so **Tables VI--XII of the first report cannot be regenerated
and are no longer used as primary evidence**. The whole main study was re-run
with the released `reproduction/sim_full.cpp` and those numbers are now the
primary result.

### What changed
* **Title/abstract/conclusion** reframed as an honest measurement study: "A
  Reproducible Measurement Study of When Drift Gating Pays Off". The phrase
  "statistically gated" is removed; the paper now states the implemented design
  is a **CUSUM trigger plus a cost margin** (the KS stage gave no measurable
  benefit).
* **New reproducible primary run**: parameters fixed on training seed 100
  (`--ncand 5 --kfrac 0 --z 1.28 --edelay 10`), then a single frozen evaluation
  on fresh seed 5001 (30 stable + 80 non-stable traces). Driver:
  `reproduction/run_main_study.sh`; all tables built by
  `reproduction/analyze_main_study.py` from raw CSVs (no transcription).
* **Primary numbers**: DA 0.453 [0.423, 0.484] vs LRU 0.570 (20.5% better);
  S3-FIFO 0.468 (paired $-0.0154$, Holm $p=0.090$, not significant);
  **ContShadow 0.423, i.e. 0.030 better than DA** (Holm $p=1.25\times10^{-5}$).
  Gating cut shadow evals 6.47 vs 27.39 = **76.4%**, but *not* at equal miss
  ratio in this study; the 81%/equal-miss-ratio claim is explicitly confined
  to the non-reproducible first report. Cost 2.7x LRU, 2.4x S3-FIFO.
* **Self-grading Q1/Q2 sentence deleted** from the discussion.
* **MGLRU-style baseline dropped**: page-level trace replay has no kernel
  aging/reclaim signal, so the implementation reduced to generation-indexed LRU
  (0.2915 vs LRU 0.2914). Text now explains why no such baseline is claimed.
* **References verified**: [17] EACLOCK (IEEE TKDE 38(11), Nov 2026,
  pp. 7387--7401, DOI 10.1109/TKDE.2026.3724159) and [29] (IJSRT 3(6),
  556--564, DOI 10.5281/zenodo.20576370) are real and retained.
* **Bootstrap clarified**: four clusters give only $\binom{7}{4}=35$ distinct
  resamples; the interval is reported as a coarse sensitivity check only.
* **Real programs stay appendix-only** and exploratory: DA 0.2631 vs S3-FIFO
  0.2623 ($+0.0007$ [$-0.0037$, $+0.0050$], a tie), LRU 0.2914, DA 2.5x S3-FIFO
  cost; five of ten kernels below 0.02 miss ratio.
* Figures fig3--fig7 regenerated from the new CSVs by
  `reproduction/make_main_figures.py`.

### Build / delivery at that time (superseded by the audit revision)
* `\documentclass[10pt,twocolumn,a4paper]{IEEEtran}` unchanged; author block
  unchanged (Hunain Tahir, Muhammad Qasim, Hussain Ahmad; F2024332128,
  F2024332122, F2024332173; Supervisor: Mohsin Ghaffar Ghouri; no affiliation).
* Two `pdflatex -interaction=nonstopmode -halt-on-error main.tex` runs:
  **12 pages, A4 (595.276 x 841.89 pt), 0 errors, 0 overfull boxes**, no
  undefined references or citations.
* `latex/main.pdf` copied to `../Drift_Aware_Page_Replacement_Revised_Fixed.pdf`;
  both had md5 **`b60c2b7f408329065fa09d9431c4f9c8`** at that build (superseded
  by the current audit revision above).
* Source and PDF scans confirm absence of stale strings: `81%`, `14.2`,
  `0.410`, `6.4 times`, `MGLRU-style`, `Q1/Q2`, `Q2-tier`, `statistically gated`,
  `96.1`. This described the delivered PDF at that time; see the current
  audit revision above.

### Earlier consistency audit (follow-up; historical)
A second pass caught and fixed six residual inconsistencies introduced by the
large rewrite:
1. `Tables~VI--IXI` (a global-replace collision) corrected to `VI--XII` in the
   two places that refer to the *first report's* tables.
2. Introduction stance paragraph still said the main study was not
   independently reproducible; rewritten to point to the released simulator.
3. Introduction evidence-limits paragraph still said "the main tables come from
   the original simulator" and claimed the appendix adds multi-generation LRU
   baselines; rewritten to the reproducible main study and the dropped MGLRU
   claim.
4. *Data and code availability* was completely backwards (said the main study's
   artifacts were lost); rewritten to state that the main study is regenerated
   by `run_main_study.sh` and only the first report is lost.
5. Appendix retitled from "Independent Exploratory Replication" to
   "Exploratory Real-Program Evidence" (with matching TOC entry).
6. Threats to Validity: "Stage-1 monitor" -> "CUSUM monitor", stale
   "reporting both rounds" internal-validity claim rewritten, and
   "sensitivity at two others" corrected to one other capacity.
Final verification: 12 pages, A4, 0 errors, 0 overfull boxes, 0 undefined
references/citations, all stale strings absent.

### C=500 correction (after the background run completed)
When the optional sweeps finished, re-running `analyze_main_study.py` showed the
earlier C=500 values had been read from a **partially written CSV**. Table IX and
its prose were corrected to the complete-file values: DA 0.580, LRU 0.693,
2Q 0.654, S3-FIFO 0.590, ContShadow 0.555, OPT 0.434 (previously 0.560/0.689/
0.638/0.578/0.541/0.371). All primary-study numbers (Tables VI--VIII, cost and
detection) were unchanged and byte-identical on re-analysis. fig8/fig9 were
regenerated from the complete sweep CSVs.

---

## Earlier entries (historical provenance; superseded by the current audit revision above)

Scope of the earlier pass: **Group 1 — text and consistency fixes only.**
Items requiring new runs are listed at the end as *not addressed*.

---

## Baseline
`latex/main.tex` was first written as a faithful transcription of the PDF
(12 pages, 9 figures, 12 tables, 36 references) and compiled successfully
*before* any fix was applied, so that every subsequent change is isolated.

---

## Fix 1 — Verification note on LFU-A aging (Table IV vs Table V)

**Problem (review item 1a).** Table IV says the stand-alone LFU-A halves its
counts every `4C = 4,000` references; Table V says "Count aging: halved every
50 epochs" (100,000 references). A draft "Verification note" said the source
code must confirm whether the difference is intended.

**Resolution.** No simulator source exists, so the two numbers were resolved
against the paper's own text rather than against code. Section V-C already
states that the controller "updates two counters per page (last access and an
aged count)" and that "LFU-A and 2Q use the aged counts to place pages" during
migration. The two rows therefore describe two different counters:

* Table IV / the LFU-A candidate: frequency counts halved every `4C`
  references, scaled to the capacity in use (`4C_s = 800` at the shadow
  capacity `C_s = 200`).
* Table V "Count aging": the controller's own fast-path aged count, halved
  every 50 epochs = 100,000 references, used only for state migration.

**Change.** The draft note is deleted and replaced by an explicit clarification
paragraph in Section V-B; Table IV's LFU-A entry now says the rule scales with
the capacity in use, and the Section V-C cross-reference is given explicitly.

**Status:** resolved — confirmed against the paper's own Section V-C (fast path
updates last access + aged count; migration uses those aged counts) and the
differing intervals (100,000 vs 4,000 references). No author decision pending.

---

## Fix 2 — Verification note on the stable-reference count (Section V-G)

**Problem (review item 1b).** The manuscript reports 8.4 million stable
references and a rule-of-three bound of 0.36 per million, but the counting
rule stated one sentence earlier ("after reference 100,000", 30 traces of
300,000 references) gives 6.0 million and 0.50 per million.

**Arithmetic.** `30 × (300,000 − 100,000) = 6,000,000`.
Rule of three: `3 / 6.0 = 0.50` per million.
(8.4 M would correspond to excluding only the 20,000-reference cold fill,
`30 × 280,000`, which contradicts the stated 100,000 cutoff.)

**Change.** The draft note is deleted; the sentence now states 6.0 million and
0.50 per million, consistent with the counting rule given in the same passage.

**Status:** resolved by arithmetic.

---

## Fix 3 — "No external trace repositories were accessible" vs. cited MSR traces

**Problem (review item 2).** Section I justified the synthetic-only evaluation
with "no external trace repositories were accessible in the evaluation
environment", yet the paper cites the public MSR Cambridge traces [31].

**Change.** Section I no longer claims the repository was inaccessible. It now
states plainly that no real traces were collected for this study, that public
block traces such as [31] do exist but are storage-block rather than
page-reference traces (Section II-A already warns that block traces are not
direct evidence about virtual-memory paging), and that recording page traces
from running programs was not carried out. Section VII now names this as the
single most significant gap of the study.

**Status:** resolved (claim corrected; gap stated honestly).

---

## Fix 4 — Table X (0.234) vs. body text (0.235) at C = 2,000

**Problem (review item 8).** Table X gives DA = 0.234 for C = 2,000; Section
V-H says 0.235.

**Change.** Body text now reads 0.234, matching the table.

**Status:** resolved (table treated as the data of record).

---

## Fix 5 — Table XI sample sizes n = 162 / 465 / 467 unexplained

**Problem (review item 9).** n differs across sampling rates with no
explanation.

**Change.** Section V-H now defines n as the number of shadow evaluations in
which both the sampled ranking and the full-capacity reference ranking were
computable, i.e. the sampled window met the ≥100-sample requirement; that
requirement binds much harder at p = 0.05, which is why n grows with p
(162 → 465 → 467).

**Status:** resolved — author confirmed this reading. ⚠ *Note:* it remains an
inference from the paper, not a claim from raw result files: the only explicit
"≥100 samples" rule in the manuscript is for the KS test (Section V-C, Table V),
not for shadow ranking. The text in Section V-H is kept as written.

---

## Fix 6 — Rank correlation 0.76 at p = 0.05 vs 0.72 at p = 0.2

**Problem (review item 10).** "Agreement was lower at smaller sampling rates"
sits oddly with a *higher* rank correlation at the smallest rate.

**Change.** The sentence now attributes the monotone statement to top-1
agreement only (0.62 → 0.71 → 0.78) and states explicitly that rank
correlation did not decrease with p (0.76 at p = 0.05 against 0.72 at p = 0.1
and 0.2), i.e. the two measures behave differently.

**Status:** resolved.

---

## Fix 7 — "17% more misses" vs. Table XI mean ratio 1.17

**Problem (review item 11).** The text says the chosen policy incurred 17%
more misses *when it was wrong*, but Table XI reports a single "Mean ratio" of
1.17 with no per-subset breakdown, so the reader cannot tell whether the
average is over all evaluations or only the wrong ones.

**Change.** After an interim rewrite that (incorrectly) applied 1.17 to all
evaluations, the author-confirmed reading is restored: Table XI's mean ratio of
1.17 and P95 of 3.5 are reported **over the evaluations where the sampled and
full-capacity rankings disagreed**, matching the original manuscript's "when it
was wrong". The 1.17 / 17% and 3.5 figures still agree with Table XI.

**Status:** resolved — author confirmed the denominator is disagreements, not
all evaluations.

---

## Fix 8 — 2.12 switches per non-stable trace (Section V-G) vs 1.70 (Table VIII)

**Problem (review item 12).** Section V-G says 2.12 switches per non-stable
trace; Table VIII says 1.70 per trace over all traces. Both are only
consistent if stable traces also switch, which the text never says.

**Arithmetic.** Table VIII is labelled "ALL TRACES": `1.70 × 110 = 187`, which
is exactly the "187 switches" reported in Section V-G. Non-stable:
`2.12 × 80 ≈ 170`, leaving `187 − 170 = 17` switches on the 30 stable traces,
i.e. ≈0.57 per stable trace.

**Change.** Section V-G now states both denominators explicitly and reports
that stable traces account for the remaining ~17 switches (≈0.57 each),
reconciling 2.12, 1.70 and 187 in one sentence.

**Status:** resolved by arithmetic.

---

## Fix 9 — Abstract length (323 words)

**Problem (review item 13).** The abstract is 323 words, over the usual IEEE
limit.

**Change.** Rewritten to 247 words (from 323) while keeping every quantitative
claim: 0.410 / 14.2% / the Holm-significant set, the S3-FIFO 0.402 and
LPR-style 0.381 comparisons, 96% of 280 boundaries, 0 false confirmations on 30
stable traces *plus* the 11 spurious confirmations on the 60 detection traces,
81% fewer shadow evaluations, 6.4× LRU, and the negative conclusion.

**Status:** resolved.

---

## Fix 10 — Figure referencing (consistency, bonus)

**Problem.** The original had nine figures but only Fig. 1–8 were ever
numbered or cited; the capacity plot had a caption but no number and was never
referenced in the body. Fig. 5 (paired differences) had no caption at all, and
no figure caption carried its number.

**Change.** The capacity plot is now Fig. 9 and is cited in Section V-H; Fig. 5
has a caption; all captions are numbered by IEEEtran.

**Status:** resolved.

---

## Fix 11 — Table VI lost its "vs LRU (%)" column during transcription

**Problem (found by the author, not by the reviewer).** A numeric-token diff of
the rebuilt PDF against the original caught that Table VI had been transcribed
with only 7 of its 8 columns: the trailing `vs LRU (%)` column (0.0, 0.2, 1.7,
6.2, −87.9, 9.6, 5.9, 15.9, 11.9, 20.2, 14.6, 14.2, 53.4) was missing, so the
`−87.9` and `53.4` values existed nowhere in the paper.

**Change.** Column restored; all 13 rows and 8 columns verified against the
original. The table needed `\scriptsize` and `\tabcolsep = 2.2pt` to fit the
IEEE column without an overfull box. Table I was also narrowed
(`0.17/0.39/0.35\columnwidth`, `\tabcolsep = 5.4pt`) to clear a 6.5 pt overfull.

**Also caught by the same diff:** the first abstract rewrite had silently
dropped the clause "(11 spurious confirmations outside boundary windows
occurred on the 60 non-stable detection traces)". Restored (the body already
carried both facts, so this was an abstract-only loss).

**Status:** resolved.

---

## Build status

> **Superseded by the final 2026-11-21 build at the end of this file.** The
> entry below records the intermediate 12-page state after Fixes 1--11; the
> submitted PDF is 14 pages.

`pdflatex -interaction=nonstopmode -halt-on-error main.tex` (run twice):
**12 pages, 0 errors, 0 overfull boxes.** Structure and format match the
original — **A4** (`a4paper`), IEEEtran two-column 10 pt, 9 figures, 12 tables
(I–XII), 36 references, 247-word abstract.

**Delivered PDF:**
`../Drift_Aware_Page_Replacement_Revised_Fixed.pdf`
(the original `Drift_Aware_Page_Replacement_Revised.pdf` is untouched).

A numeric-token diff against the original shows no dropped table columns or
rows; the only value changes are 0.235→0.234, 8.4→6.0, 0.36→0.50, 62%→0.62,
plus the explanatory figures added by Fixes 5–8.

## Author decisions locked in (2026-11-20)

| Item | Decision |
|---|---|
| Table V "Count aging" | Controller's own fast-path aged count (Section V-C), distinct from LFU-A's `4C` counter — confirmed from the paper text; cross-reference added |
| Table XI `n` | Kept as "evaluations where both rankings were computable / ≥100-sample rule" — author confirmed; note in Fix 5 that it is an inference |
| Table XI mean ratio 1.17 | Restored to the author's "when it was wrong" reading, i.e. over **disagreements**, not all evaluations |
| Group 2/3 items | Left documented only; no experiments, no reframing changes |

---

## Not addressed (out of agreed scope — need new experiments)

| Review item | Why not done here |
|---|---|
| Central claim fails vs S3-FIFO (0.410 vs 0.402) and LPR-style (0.381); 6.4× LRU; LPR-style at 16.5 vs 65.1 ns | Group 2 claim reframing / Group 3 re-runs; the paper already states these results in Sections V-E, V-G, VII |
| Test traces favour the controller and its detector; parameters tuned on same-generator training traces; baselines untuned and re-implemented "of the principle" | Group 2 (reframing) and Group 3 (re-tuning) |
| Candidate set excludes ARC and S3-FIFO, so the S3-FIFO comparison does not test drift gating | Group 3 (re-run with wider candidate set) |
| Disjoint page ranges, epoch-aligned boundaries flatter 96% / 1,999-ref delay | Group 2 (reframing already partly present in Section V-G) |
| Loops larger than memory over-represented | Group 2/3 |
| Missing baselines CAR, LIRS, CLOCK-Pro, CACHEUS, 3L-Cache, S4-FIFO, EACLOCK, Clock2Q+ | Group 3 (implementations) |
| Effective n < 80 treated as independent; z = 1.28 vs t = 1.64 on four autocorrelated blocks | Group 2 (statistics reframing) |
| Recorded page traces from real programs — "the single biggest gap for a systems paper" | Group 3 (trace collection); the gap is now stated explicitly (Fix 3) |

## Next step chosen by the author: recover the original experimental material

No code or raw result files exist locally, and neither PDF has embedded
attachments. The author elected to request the original simulator, seeds and
per-trace data from the co-authors/supervisor before any re-tuning is attempted.

* `../recovery/REQUEST_AND_VALIDATION.md` — exact file list, reproduction
  checklist (every published table/value), and the only defensible experiment
  (add S3-FIFO/ARC to the candidate set, keep the train/fresh-trace protocol).
* `../recovery/email_template.txt` — ready-to-send request.

**Do not change any published number until the reproduction checklist passes.**
If the material cannot be recovered, the Declarations sentence claiming
supplementary material is available must be corrected instead.

### Declarations corrected (2026-11-20)

The false availability claim was replaced in `main.tex` and both PDFs rebuilt:

> "The result tables are reported in full in this paper. The simulator source,
> trace generators with seeds and configuration files were not retained, so the
> numerical results cannot be independently regenerated."

The pilot results in `PILOT_EXPERIMENT.md` and `PILOT2_TRAIN_TEST.md` were
**not** inserted into the paper: they come from `sim.cpp`, an independent
reimplementation whose absolute numbers differ from the published tables
(LRU 0.5700 vs 0.477, DA 0.4966 vs 0.410). Mixing the two would be invalid.
They remain exploratory evidence that the reviewer's candidate-set suggestion
is worth repeating on the original simulator.

### Appendix added at the author's request (2026-11-20)

A compact, explicitly labelled "Appendix: Independent Exploratory Replication"
was inserted before the Declarations. It states that the numbers come from a
different reimplementation (LRU 0.5700 vs 0.477; DA 0.4966 vs 0.410), that
they do **not** replace Tables VI–XI, and reports the pilot result (0.4529,
20.5% below LRU, S3-FIFO p = 0.090, ContShadow still better at higher cost).

**Format unchanged:** `\documentclass[10pt,twocolumn,a4paper]{IEEEtran}`, same
fonts, margins, columns and bibliography style. The added appendix extends the
paper from 12 to **13 pages**; the 13th page holds the tail of the references.
Build: 0 errors, 0 overfull boxes.

### Author block moved under names (2026-11-20)

The student IDs, SST/UMT affiliation and supervisor line were previously a
`\thanks` footnote at the bottom of page 1; at the author's request they are
now plain `\\` lines in `\author{}`, rendered directly beneath the three names.
IEEEtran format unchanged; build still clean.

### Real traces, missing baselines, fair tuning (2026-11-20)

New files: `real_traces.cpp` (instrumented index tree, hash join, BFS,
quicksort and stencil; 4 seeds each in `traces_real/`), `sim_full.cpp`
(independent simulator extended with CAR, LIRS, CLOCK-Pro, CACHEUS and a
simplified 3L-style policy, external-trace input, tunable baseline parameters
and a `--z` quantile option), and `recovery/PILOT3_REAL_TRACES.md` plus raw
CSV results.

Protocol: seed-12345 kernels used only for tuning; 15 held-out kernels
(seeds 101/202/303) evaluated once; 300k refs, 100k warm, C=1000. All tunable
baselines were tuned on training only; DA selected on training (5 candidates,
K=0.05C); z=1.28 and t_3=1.638 gave identical results.

Held-out result: tuned DA 0.0435 vs untuned 0.0620; 35.9% below LRU (0.0678);
beats all added baselines and ContShadow (0.0435), but S3-FIFO (0.0395) and
OPT (0.0386) remain better (p=0.008). Cluster bootstrap over 5 kernels:
DA--LRU -0.0243 [-0.0730, 0.0000], DA--S3-FIFO +0.0040 [0.0001, 0.0098].
Cost 39.1 ns/ref vs LRU 22.2 and S3-FIFO 5.4.

The appendix was expanded with these results, still explicitly labelled as
independent exploratory work that does not replace Tables VI--XI. The
false availability claim remains corrected. `\balance` was removed to clear
a 0.87 pt overfull vbox; IEEEtran class/options/fonts/margins unchanged.
Final build: 13 pages, A4, 0 errors, 0 overfull boxes.

### Author line correction (2026-11-20)

At the author's request the SST/UMT affiliation line was removed from the
title block and the supervisor name corrected to **Mohsin Ghaffar Ghouri** in
both the author line and the Acknowledgment. Build still clean: 13 pages,
0 errors, 0 overfull boxes.

---

## Final rewrite and submission build (2026-11-21)

The paper was rebuilt around one consistent story: **generated traces are the
main study; real-program traces are exploratory appendix evidence only.** The
IEEEtran class and options (`[10pt,twocolumn,a4paper]`) were not changed.

### Narrative

* Abstract, Introduction, Limitations, Conclusion, Appendix and Declarations
  rewritten to match that story. The abstract now states the negative result
  explicitly: DA 0.410 is 14.2\% below LRU but not better than S3-FIFO (0.402)
  or LPR-style (0.381); the independent re-implementation did not reproduce
  the absolute numbers; the whole-program holdout gives DA 0.0649 versus LRU
  0.0683, S3-FIFO 0.0397 and set dueling 0.0580.
* Removed all stale overclaims: ``No real traces were recorded'',
  ``reproducible comparison'', ``a reproducible protocol'', ``frozen'',
  ``viable but not yet'', ``primary limitation'', ``required follow-up
  analysis'', ``beat every other method'', ``stayed better'', and the claim
  that real traces were an inaccessible/future-work item. Table caption
  ``Frozen Controller Parameters'' is now ``Controller Parameters Fixed After
  Training''.
* Cost figures reconciled rather than mixed: main simulator 65.1 vs 10.1
  ns/ref = 6.4$\times$ LRU; independent exploratory simulator 71.2 vs 24.9
  ns/ref = 2.9$\times$ LRU and 12.9$\times$ the 5.5 ns S3-FIFO. The paper says
  the absolute timings are not comparable across implementations and neither
  is a kernel latency measurement; DA is not competitive on the cost--quality
  frontier in either.
* Q1/Q2 framing: no in-kernel prototype, no page-fault/reclaim latency and no
  superiority over S3-FIFO/LPR-style are claimed. The paper is framed as an
  account of when drift gating helps and when it does not.

### Reviewer requests addressed

* **Whole-program holdout.** `recovery/whole_program_holdout.py` holds out
  each of five programs in turn; all tunable baselines and DA are tuned on the
  other four programs (16 traces) and evaluated once on the four held-out
  traces. Per-fold results are in `recovery/whole_program_holdout_results.csv`:
  OPT 0.0389, S3-FIFO 0.0397, CLOCK-Pro 0.0569, 2Q 0.0571, DIP-set-duel 0.0580,
  DA 0.0649, ContShadow 0.0649, LRU 0.0683, MGLRU-style 0.0692. Five-program
  cluster bootstrap: DA--S3-FIFO $+0.0252$ [$+0.0002$, $+0.0732$] (DA
  significantly worse), DA--LRU $-0.0034$ [$-0.0102$, $0.0000$] and
  DA--DIP-set-duel $+0.0069$ [$0.0000$, $+0.0205$]. Appendix states that four
  of five kernels barely miss at $C=1000$, so power is low.
* **Stronger baselines.** `sim_full.cpp` gained set-dueling DIP [37] and an
  MGLRU-style multi-generation policy [38], both marked with explicit
  ASSUMPTION comments; compiled cleanly with `g++ -O2 -std=c++17`. CAR, LIRS,
  CLOCK-Pro, CACHEUS and a 3L-style policy were already present.
* **Scenario-clustered analysis.**
  `recovery/scenario_clustered_bootstrap.py` treats the four non-stable
  scenarios as clusters for the independent synthetic data: DA--LRU
  $-0.1171$ [$-0.1313$, $-0.0907$], DA--S3-FIFO $-0.0154$ [$-0.0294$,
  $-0.0048$]; the trace-level DA--S3-FIFO interval still crossed zero
  [$-0.0348$, $+0.0041$]. The original Tables VI--XI cannot receive this
  analysis because their raw per-trace output was not retained; the paper
  says so in both Section V and the Appendix.
* **Prior art and references.** Added [37] Qureshi et al., DIP/DRRIP, ISCA
  2007 (`10.1145/1250662.1250709`) and [38] Linux multi-gen LRU docs, with a
  new prior-art paragraph in Section II. [17] EACLOCK was verified (TKDE
  38(11), Nov. 2026, `10.1109/TKDE.2026.3724159`) and [29] was verified as a
  Zenodo-hosted journal record (`10.5281/zenodo.20576370`); both citations
  remain unchanged. Bibliography widened from `{36}` to `{38}`.

### Figures and artifacts

* `recovery/make_fig1.py` regenerated `latex/figs/fig1_arch.png` without the
  old ``future work: real traces'' annotation, which contradicted the
  appendix.
* `reproduction/` contains the independent source, instrumented trace
  generator, all seeds, `configs.txt`, raw CSVs, analysis scripts and a README
  that states plainly that it reproduces only the exploratory appendix, not
  Tables VI--XI.

### Status at that time (superseded)

* Main published Tables VI--XI are byte-for-byte unchanged in content; no
  independent-simulator number was substituted into them.
* Author block unchanged: Hunain Tahir, Muhammad Qasim, Hussain Ahmad;
  Student IDs F2024332128, F2024332122, F2024332173; Supervisor: Mohsin
  Ghaffar Ghouri; no affiliation line.
* Build: `pdflatex -interaction=nonstopmode -halt-on-error main.tex` twice,
  **14 pages, A4 (595.276 $\times$ 841.89 pt), 0 errors, 0 overfull boxes**.
* `latex/main.pdf` copied to `../Drift_Aware_Page_Replacement_Revised_Fixed.pdf`;
  both had md5 `a551cafed2b9dde9be41bcd6f7988058` at that build. **Superseded
  by later revisions documented above.** The original
  `Drift_Aware_Page_Replacement_Revised.pdf` is untouched.

### Correction made after the first submission build (same day)

`whole_program_holdout.py` originally appended its fixed `--ncand 5 --kfrac 0`
defaults *after* the tuned arguments. Since the simulator parses last-wins,
DA's candidate-set and cost-margin tuning was silently overridden, which made
the earlier DA 0.0438 / 35.9\% figure and the claim that folds selected four
candidates unjustified. The driver now puts defaults first, uses a portable
temp directory, and resolves its paths whether it lives in `recovery/` or in
a standalone `reproduction/` package. The holdout was **re-run from scratch**.
The corrected result is stronger evidence against the headline claim: DA
0.0649, only 5.0\% below LRU and behind CLOCK-Pro, 2Q, DIP-set-duel and
S3-FIFO; per-fold cost is 71.2 ns/ref. All affected numbers in the abstract,
Limitations, Conclusion, appendix table, appendix text and this changelog were
updated, and both PDFs were rebuilt.

---

## Earlier expansion to ten programs and submission build (2026-11-21)

This was the authoritative state at that time; it superseded the five-program
whole-program holdout numbers reported in the two sections immediately above,
and is now superseded by the current audit revision above.
The reviewer's remaining concern was that the exploratory appendix rested on
only five instrumented programs and a five-cluster bootstrap with almost no
inferential power.

### What changed

* **`real_traces.cpp` expanded from five to ten programs.** The original index
  tree, hash join, CSR BFS, quicksort and stencil were joined by sparse-matrix
  value gathers, a random-decrease-key binary heap, a histogram scatter over a
  16 MB key array, a random walk over a CSR adjacency array, and an
  open-addressing hash table. An early attempt using a blocked dense matrix
  multiply and a top-only heap produced traces with too few distinct pages at
  $C=1000$; those kernels were replaced with the current five so that six of
  the ten have working sets above 1000 pages. Each kernel logs 300,000
  references; four seeds (default, `_s101`, `_s202`, `_s303`) are used.
* **Holdout re-run with whole programs held out.** `whole_program_holdout.py`
  now iterates over ten folds (tune on the other nine programs, 36 traces;
  evaluate once on four held-out traces). The old `matrix*.bin` traces were
  removed. Raw results are in `recovery/whole_program_holdout_results.csv`
  (and the identical copy in `reproduction/`).
* **New ten-program result.** DA 0.2631, 9.7\% below LRU (0.2914), is
  statistically **indistinguishable** from S3-FIFO (0.2623;
  DA--S3-FIFO $+0.0007$ [$-0.0037$, $+0.0050$]) and ContShadow (0.2631), and
  significantly better than 2Q, ARC, DIP-set-duel, LRU, LPR-style and
  MGLRU-style. DA is **not** better than S3-FIFO on miss ratio and cost 2.5
  times as much. The conclusion therefore changed from ``DA is worse than
  S3-FIFO'' to ``no superiority over S3-FIFO is established,'' with the Q2-tier
  evidence tier stated explicitly in the Limitations.
* **New exploratory cost.** DA 49.1 ns/ref against LRU 24.5 (2.0$\times$) and
  S3-FIFO 19.9 (2.5$\times$). This replaces the old 71.2/24.9/5.5 figures. The
  main study still reports 65.1 vs 10.1 ns = 6.4$\times$ LRU; the paper
  explains that the absolute timings are not comparable across implementations
  and that neither is a kernel latency measurement.
* **Provenance and Q1/Q2 framing.** A provenance paragraph was added at the top
  of Section V stating that Tables VI--XI come from the original simulator
  whose source, seeds, configs and raw per-trace output were not retained, and
  that the independent numbers are never substituted into them. The Limitations
  now state that this is Q2-tier evidence and spell out what Q1 would require
  (beat the best static policy on real workloads at lower cost, or an in-kernel
  page-fault/reclaim latency prototype); neither exists.
* **Corrected accuracy detail.** Five of the ten kernels (hash join, BFS, sort,
  stencil, radix) have miss ratios below 0.02 at $C=1000$; the mean is dominated
  by three high-miss kernels where DA and S3-FIFO are nearly tied. Both the
  paper and the reproduction README now say this.
* **Reproduction package synced.** `reproduction/real_traces.cpp`,
  `whole_program_holdout.py` and `whole_program_holdout_results.csv` are
  byte-identical to the current sources. `reproduction/README.md` documents the
  ten-program protocol, seeds and results. The package was smoke-tested:
  both C++ files compile with `g++ -O2 -std=c++17`, 40 traces regenerate from
  the four seeds, and the first three holdout folds reproduced the shipped CSV
  exactly. Generated binaries and traces were removed from the package (the
  paper promises code, seeds, configs, CSVs and scripts, not trace binaries).

### Status at that time (superseded)

* `\documentclass[10pt,twocolumn,a4paper]{IEEEtran}` unchanged; author block
  unchanged (Hunain Tahir, Muhammad Qasim, Hussain Ahmad; F2024332128,
  F2024332122, F2024332173; Supervisor: Mohsin Ghaffar Ghouri; no affiliation).
* Tables VI--XI remain the original published numbers; no independent-simulator
  number was substituted into them.
* Build: two `pdflatex -interaction=nonstopmode -halt-on-error main.tex` runs,
  **14 pages, A4 (595.276 $\times$ 841.89 pt), 0 errors, 0 overfull boxes**
  (28 underfull hboxes, unchanged in kind from the previous build's 26).
* `latex/main.pdf` copied to `../Drift_Aware_Page_Replacement_Revised_Fixed.pdf`;
  both have md5 **`4db469b3fe12814c2bbaa33f82ac0f56`**. The original
  `Drift_Aware_Page_Replacement_Revised.pdf` is untouched.
* Final scans confirm every stale five-program value is absent from both source
  and PDF (`0.0649`, `0.0683`, `0.0397`, `0.0580`, `0.0569`, `0.0571`, `71.2`,
  `24.9`, `12.9`, `0.0252`, `0.0732`, `0.0034`, `0.0069`, `35.9`, etc.), while
  [17], [29], [37], [38] and the full author block render correctly.
## 2026-11-23 seven-issue traceability, diagnostics and bootstrap revision

### Issue 1: Detection attribution, per-scenario reporting and stable-trace locations
- **Change.** Abstract reports per-scenario detection 97/100 abrupt, 24/100 gradual, 96/100 recurring, 61/80 composite. Section V-F attributes the 169 spurious confirmations as 16 abrupt, 109 gradual, 14 recurring, 30 composite. Methods state detection is evaluated on all 80 non-stable traces (380 true boundaries). Stable-trace analysis reports 23 confirmations total: 17 before 50k, 5 between 50k and 100k, 1 at 160000; only 1 after 100000.
- **Evidence.** `reproduction/main_study_detection.csv` (per-scenario sums); `reproduction/sim_full_diag.cpp` diagnostic run `--detail-log /tmp/opencode/diag_main_detail.csv` with confirmation positions. `reproduction/check_paper_numbers.py` checks the per-scenario counts and stable totals.

### Issue 2: Boundary offsets 250/500/1000/1370 and script-generated Table IX
- **Change.** Ran offsets 250, 500, 1000, 1370 with the released `sim_full` (same frozen config). Replaced hand-transcribed 2-offset table with a 5-offset table generated from raw CSVs by `reproduction/generate_offset_table.py`.
- **Evidence.** `reproduction/detection_offset250.csv`, `detection_offset500.csv`, `detection_offset1000.csv`, `detection_offset1370.csv`, `main_study_detection.csv`; `generate_offset_table.py` writes `latex/offset_table.tex`. Table shows 274–281 detected, 169–173 spurious, 23 stable spurious at every offset.

### Issue 3: Public-trace diagnostics, fault, and parameter re-selection
- **Change.** Added per-candidate shadow margins and CUSUM logging via `sim_full_diag.cpp` (behaviourally identical to released simulator). Reported why DA/ContShadow never left LRU: CUSUM threshold crossed (max Sp 7.95–20.30, Sn 6.08–33.30) and all traces had confirmed alarms, but every shadow evaluation gave identical miss counts for all 5 candidates because `Cs=p*C=4000` exceeded the sampled working set at C=20000. Identified as a capacity–sampling fault. S3-FIFO is candidate id 4 in `mkCand`; it is visible at C=1000. C=20000 was selected by a pilot on one test trace (`webresearch`), now stated explicitly. Re-selected DA on 500k training prefixes of the six public traces using the 48-config grid; all configs identical (0.68027 miss, 0 switches) due to the same fault. Held-out suffixes: frozen and re-selected both 0.66834 miss, 0 switches. Reported as failed external validation.
- **Evidence.** `public_diagnostic_summary.csv`, `public_detail.csv` (raw event log), `public_pilot_C*.csv`, `split_public_traces.py`, `sweep_public_selection.py`, `public_sweep_results.csv`, `public_sweep_selected.txt`, `public_test_frozen.csv`, `public_test_reselected.csv`, C=1000 diagnostic check.

### Issue 4: Ablation activation counts
- **Change.** Added component-activation paragraph. Purge acted at 47/213 switches, dropped 39,405 stale pages. KS active on all 643 alarms, rejected 173; 570 evals. Cost margin never acted (K=0) and dwell never blocked (0); described as inactive under the frozen configuration, not as having no benefit.
- **Evidence.** `diag_component_totals.csv` from `sim_full_diag --detail-log` on main study (0 behavioral mismatches, byte-identical detection CSV).

### Issue 5: Break-even bootstrap CIs and direct shadow-evaluation timing
- **Change.** Added 10,000-replicate trace-level bootstrap CIs: R 783.3 [426.3, 1186.7], direct break-even 2.196 us [1.441, 4.059] us. Added direct timing-only shadow-evaluation measurement: mean 2.46 ms, median 2.33 ms (570 evals) vs implied 1.72 ms; noted 1.4x difference and that direct measurement weakens the gating case. Stated DA already contains S3-FIFO as candidate id 4.
- **Evidence.** `bootstrap_cost_model.py`, `cost_model_bootstrap.csv`, `sim_full_bench.cpp`, `bench_eval_timing.csv`, `cost_model.csv`.

### Issue 6: Housekeeping
- **Change.** Fixed `Table~IX` capacity reference to `Table~\ref{tab:capacity}` (Table XII). Removed process language, raw CSV rows, and command lines from body to `latex/supplement.tex`. Dropped H4 (unmeasured ranking agreement). Verified [39] URL resolves (CMU PDL cacheDatasets page fetched). Declared M. Qasim's Anoneurx affiliation and Anoneurx Astra tool role in competing-interests statement.
- **Evidence.** `main.tex` diffs; `supplement.tex`; webfetch of [39] page; rebuilt PDF text scan.

### Issue 7: Deliverables
- **Change.** Updated checker to 190/190 PASS. Rebuilt 15-page PDF (0 errors, 0 overfull hboxes). Updated README, CHANGELOG, supplement, and reproduction artifacts.
- **Evidence.** `check_paper_numbers.py` output, `latex/main.pdf`, `Drift_Aware_Page_Replacement_Journal_Revision.pdf`.

### Issue 8: Cost-claim correction (2026-11-24)
- **Change.** Withdrew "gating pays off only when misses are cheap" and the DA-versus-ContShadow-only break-even framing. Added a total-time envelope over CLOCK, S3-FIFO, ContShadow and DA: CLOCK cheapest below 0.215539 us, S3-FIFO 0.215539-2.304942 us, ContShadow above 2.304942 us; DA never on the envelope (minimum excess 3.268673 ns/ref at 2.304942 us). Bootstrap (seed 20261124, B=10000) minimum-gap CI includes zero, so ranking is stated as point estimates. Added CLOCK and S3-FIFO to Fig. 6 / Fig. 8 and replaced the break-even table with generated Table XIII / Table IX. Manuscript now says DA is never best in these measurements.
- **Evidence.** `reproduction/phase5/{bootstrap_total_time.py,total_time_envelope.py,total_time_bootstrap.csv,total_time_table.csv,envelope_summary.csv,pairwise_crossings.csv}`, `claims_to_sources.csv` (110 rows), `check_paper_numbers.py` 328/328 PASS, rebuilt `drift_gating_latex_source/main.pdf` (15 pages), `latex/main.pdf` / `paper_final.pdf` (16 pages), supplement (5 pages), DOCX from final PDF.
