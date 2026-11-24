# Self Audit

## Rule 1: No placeholders, no "TBD/XX/[insert]", no mock/estimated/simulated-for-illustration/imagined data
**Met.** Manuscript body grep for `TBD, XX, insert, session, change log, NOT_DONE, placeholder, lorem` (case-insensitive) in `latex/main.tex`/`paper_final.tex` returns only legitimate `insert` substrings in "insertion" words (3 matches). No TBD/XX/placeholder/lorem/mock/estimated/imagined data in manuscript body. All new numbers come from real simulator runs or released CSVs.

## Rule 2: Every number comes from released raw CSVs/logs or from a new run of the released code; for each new run record exact command, seed, and output file; impossible runs in NOT_DONE.md, never in manuscript body
**Met.** New real runs recorded in `NOT_DONE.md` with commands/seeds/defaults/outputs: repaired public/synthetic/holdout, detection offsets, post hoc trigger variants, FIU trigger check, param sweep, FIU/synthetic rankability sweeps, and the independent Phase 10 capacity pilot. Raw outputs: `reproduction/trigger_real/*`, `reproduction/param_sweep/*`, `reproduction/rankability_real/*`, `reproduction/phase10_capacity_pilot/*`, and repaired/offset CSVs named in `NOT_DONE.md`. `python3 reproduction/check_paper_numbers.py` passes 499/499 (final count below).

## Rule 3: Never tune/select/reword results to look better; null/negative results stay; any change made after seeing test results labeled "post hoc"
**Met.** Repaired capacity-sampling correction remained identical/no improvement and is labeled post hoc. Trigger/param/rankability measurements are labeled post hoc in `latex/main.tex` Section `sec:posthoc` and in `NOT_DONE.md`. FIU oracle produced 0 confirms (no bounds) and is reported as not evidence of benefit. Negative/worse cases retained (periodic/random worse than DA, W=4000 worse, FIU C=20000 zero switches).

## Rule 4: Do not invent references, datasets, venues, or quartiles; add citation only if verified
**Met after 2026-11-24 fix.** Patel & Maniar and EACLOCK were retained only after DOI/publisher verification. [39]/supplement [41] remains CMU PDL cacheDatasets; project page, FTP listing, exact FIU `madmax` filename, README and PDL copyright page were verified. No dataset-specific licence is claimed. Evidence is in `REFERENCE_VERIFICATION.md`; `NOT_DONE.md` no longer flags these as unverified.

## Rule 5: Manuscript body must contain no process language
**Met.** `latex/main.tex`/`paper_final.tex` have no `in this session`, `as requested`, `previous report/version`, `change log`, `NOT_DONE`. Process details are in `NOT_DONE.md`, `selfaudit.md`, `changes.md`, `claims_to_sources.csv`.

## Forbidden-string grep (manuscript body)
Command: case-insensitive grep for `TBD|XX|insert|session|change log|NOT_DONE|placeholder|lorem` on `latex/main.tex` and `paper_final.tex`.
- TBD: 0
- XX: 0
- insert: 3 matches in both files, all legitimate "insertion" word uses
- session: 0
- change log: 0
- NOT_DONE: 0
- placeholder: 0
- lorem: 0

## Evidence
- `reproduction/check_paper_numbers.py`: 255/255 PASS at that point; 499/499 in the final verification below.
- `latex/main.pdf` rebuilt (17 pages, pdflatex twice, no fatal errors).
- `claims_to_sources.csv` updated with post hoc real-run rows.
- `NOT_DONE.md` records unavailable items (MSR/Alibaba/Tencent/CloudPhysics, W-TinyLFU/SIEVE, ADWIN/Page-Hinkley, real async/kernel prototype) and all new real run commands/outputs.

## 2026-11-23 follow-up (Phases 1-5 executed, 6-7 partial)

- **Real runs completed:** Phase 1 rankability grid (288 jobs, 64,280 eval diags), Phase 2 budget frontier points/pairings, Phase 3 PH/ADWIN train grid (24) + 2 test evals, Phase 4 SIEVE/W-TinyLFU synthetic + 1944 real-trace/capacity result rows, Phase 5 t3 robustness and break-even/async tables.
- **Code changes:** sim_full.cpp gained eval-diag, PH/ADWIN triggers, SIEVE/W-TinyLFU baselines, lcb-dist t3; default DA behavior verified identical on miss/switches/shadow_evals/detection (ns_per_ref differs by timing).
- **Manuscript:** added post hoc follow-up section, extended cost model, updated abstract/conclusion/limitations/threats; rebuilt main.pdf/paper_final.pdf (17 pages).
- **Checks:** reproduction/check_paper_numbers.py 275/275 PASS.
- **Remaining blockers:** external traces not available/licensed, LHD not implemented, simplified independent baseline/detector implementations, FIU prepared 500k splits, no kernel/async prototype, [39] unverified, page-count compression needed.

## Follow-up pass (same day)
- [39] URLs and PDL terms verified by webfetch; no explicit dataset licence file found.
- LHD implemented (simplified independent heuristic), smoke-tested, run on synthetic + all available real traces; negative result (synth 0.6736, real 0.6979).
- Three original FIU traces downloaded from [39] and replayed at 1/5/10% WSS (3,274,061-ref webresearch and 918,010-ref madmax full length; homes 5M-prefix stated). DA no advantage; S3-FIFO best (0.6188).
- Default DA identity re-verified after all code changes: 110 rows, 0 metric mismatches, 0 detection mismatches.
- check_paper_numbers.py 285/285 PASS; claims_to_sources.csv 87 rows.
- Main paper compressed 17->15 pages; supplement 5 pages (includes literature, appendix, follow-up details and extra tables).
- Remaining: other PDL traces, kernel prototypes/measurements, page target 10-12 not reached without deleting results.

## Cost-claim correction (re-analysis of frozen seed-5001 data)

- **Withdrawn claim:** "gating pays off only when misses are cheap" and the DA/ContShadow-only break-even framing are removed from both paper trees; they were point estimates over only two policies and did not consider CLOCK or S3-FIFO.
- **New analysis, no new experiment:** `reproduction/phase5/total_time_envelope.py` and `bootstrap_total_time.py` read the unchanged `main_study_results.csv` (80 non-stable seed-5001 traces) and produce `total_time_table.{csv,tex}`, `pairwise_crossings.csv`, `envelope_summary.csv`, `total_time_bootstrap.csv` and Fig. 6 / Fig. 8. Frozen main-study miss/switch/eval/detection outputs were not modified.
- **Numbers:** lower envelope CLOCK `<0.215539 us`, S3-FIFO `0.215539-2.304942 us`, ContShadow `>2.304942 us`; DA is never on it, minimum excess 3.268673 ns/ref at 2.304942 us. Bootstrap (seed 20261124, B=10000): DA minimum-gap CI `[-28.597766, 40.231357] ns` includes zero, so the ranking is reported as point estimates, not statistical dominance; DA/S3 crossing CI uses 9394/10000 positive replicates and is labeled unstable.
- **Manuscript:** abstract, contributions, intro, cost section, Table XIII / Table IX, Fig. 6 / Fig. 8, hypothesis table, discussion, conclusion and supplement updated in `drift_gating_latex_source/main_template.tex`, `latex/main.tex`, `paper_final.tex` and `latex/supplement.tex`. Table XIII is generated by `\input{total_time_table.tex}` and is the single source for the table.
- **Artifacts rebuilt:** `drift_gating_latex_source/main.pdf` (15 pages), `paper.pdf`, `main.docx` (15 full-page images from the final PDF), `latex/main.pdf` and `latex/main_final.pdf` (16 pages), `latex/supplement.pdf` (5 pages), `paper_final.pdf` (16 pages).
- **Artifact hygiene:** stale `drift_gating_latex_source/main.txt`, `latex/revised_paper.txt` and `latex/preview/p-*.png` regenerated from the final PDFs, so no old claim survives in a file presented as paper text or a preview.
- **Checks:** `python3 reproduction/check_paper_numbers.py` 328/328 PASS; `claims_to_sources.csv` 110 rows; no undefined references in either main PDF; 0 overfull hboxes in the final builds.

## Phases 6-9 (2026-11-24): post hoc follow-ups recorded in `PROTOCOL.md`

- All four phases are recorded post hoc in `PROTOCOL.md` (see version history). Amendments are also recorded there post hoc: async byte-identity clarification (wall-clock `ns_per_ref` excluded), 10 ms controller interval, QEMU 9p results mount, space-free kernel build path, local bison, local libelf build and `-Wno-error` for an unrelated elfutils warning. Frozen seed-5001 artifacts were not modified.
- **Phase 6:** six CMU PDL families, 1M records each, streamed with SHA256 manifest; 18 real simulator points. DA is worse than S3-FIFO on these points (+0.0059, Holm p=0.0192) and is reported that way. No tuning after seeing results.
- **Phase 7:** additive `sim_async` build with a real worker thread; default deterministic columns and detection CSV verified byte-identical to current `sim_full`. Three real async repetitions are worse than synchronous DA (+0.1082/+0.1147/+0.1070); reported as a negative result. No analytic-model number is presented as a prototype measurement.
- **Checker:** extended with Phase 6/7 values read directly from generated CSVs; `python3 reproduction/check_paper_numbers.py` now 342/342 PASS. `claims_to_sources.csv` has trace rows for every new printed number.
- **Kernel:** real build failures (path with spaces, missing bison, missing `gelf.h`) were recorded in `PROTOCOL.md`/`NOT_DONE.md`; host build dependencies were resolved locally without sudo. No kernel measurement is claimed until real guest CSVs exist.
- **Hygiene:** all new LaTeX fragments are generated by `reproduction/generate_phase_tables.py` from measured CSVs; no hand-entered Phase 6/7 table numbers. Final page counts, DOCX rebuild and frozen-artifact SHA checks were completed in the final verification below.

## Final verification (2026-11-24, authoritative)

- **Rules 1--5 rechecked:** no placeholder/TBD/XX text in either manuscript
  (`reproduction/final_hygiene.py` PASS); every Phase 6--8 number is read from a
  generated CSV by `check_paper_numbers.py` (499/499 PASS) and has a row in
  `claims_to_sources.csv`; null and negative results (six-family DA worse than
  S3-FIFO, async worse than sync, guest kernel null) are stated prominently;
  no result was tuned after inspection; no unverified citation was added.
- **Phase 8 traceability:** the nine real boots, 191,370 ftrace samples,
  131,138 minor faults per run and all zero deltas/toggles are cross-checked
  against `kernel_summary.csv`, `ftrace_summary.csv`, `ftrace_durations.csv`
  and the two generated LaTeX fragments. Five discarded build/boot attempts
  and one defective complete sequence are recorded in `PROTOCOL.md` and
  `NOT_DONE.md`; none of their values appears in the paper.
- **Build fixes are recorded post hoc (see version history):** space-free source path,
  local bison/libelf, make command-line `CC="gcc-15 -std=gnu11"`, `-lm` link
  order, initramfs dynamic loader, `/dev/null`, `uname`, filter file inside the
  9p mount and cgroup metadata capture.
- **Frozen artifacts:** SHA256 of `main_study_results.csv` and
  `main_study_detection.csv` verified unchanged by `final_hygiene.py`.
- **Compiled output:** `latex/main.pdf` 11 pages and `drift_gating_latex_source/main.pdf`
  10 pages, both with 0 undefined references and 0 overfull hboxes;
  supplements 15 and 13 pages, also clean. DOCX rebuilt from the final drift
  PDF; text extracts and preview pages regenerated; duplicate `paper.pdf`,
  `main_final.pdf` and `paper_final.pdf` copies refreshed from the final PDFs.
- **Remaining gaps (not claimed):** no in-kernel DA policy, no kernel-faithful
  MGLRU baseline, no production VM paging traces, no guest reclaim-latency
  result, no demonstrated cgroup memory pressure, and no full-shadow
  ranking-agreement validation for H4.

## Phase 10 follow-up: independent capacity provenance (2026-11-24)

- **Reviewer issue resolved with a real run.** Phase 10 was written into
  `PROTOCOL.md` before the pilot trace was fetched, converted or run. The
  pilot is the non-evaluation FIU `webusers` trace; WSS 72539 and SHA256 are in
  `reproduction/phase10_capacity_pilot/manifest.csv`, and all seven exact
  commands are in `commands.csv`.
- **Rule applied once, no override.** `select_capacity.py` selected the
  smallest capacity with both miss ratios $\ge0.01$ and LRU--S3-FIFO gap
  $\ge0.10$: C=10000 had gap 0.00865 (rejected), C=20000 had gap 0.20864
  (selected). The selected capacity equals the already frozen replay capacity,
  so no public performance number or main-study artifact changed.
- **Text and ledger updated, not results.** Both supplement trees now cite the
  independent pilot; the superseded `webresearch`-only pilot CSVs remain for
  provenance only. `claims_to_sources.csv` gained the pilot manifest, raw point
  and selection rows, and `check_paper_numbers.py` verifies all of them
  (499/499 PASS).
