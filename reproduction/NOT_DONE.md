# NOT DONE (leave out of paper body)

1. **Fix the public-trace capacity–sampling fault in the released controller.**  
   The diagnostic identified that `Cs = p*C = 4000` at C=20000 exceeds sampled public-trace working sets, making all candidates tie and keeping DA on LRU. A proper fix would redesign shadow scaling/sampling (e.g., decouple `Cs` from `p*C`, or adjust `p`/windowing for large C) and re-run all affected public-trace claims. This is a code/algorithm change with new experimental consequences; it was not performed. The paper reports the fault and the failed re-selection instead.

2. **Restore abstract to the old constraint “≤200 words and ≤6 numbers”.**  
   The user requested per-scenario detection in the abstract. The revised abstract is ~200 words but contains 18 numerals, violating the prior ≤6-number constraint. Reconciling both constraints would require moving per-scenario detection out of the abstract, which conflicts with the explicit request.

3. **Independent real-system / kernel validation of detection rates and cost model.**  
   Boundary offsets 250–1370 remain inside generator epochs and do not remove alignment artefacts; detection rates are not real-system rates. Cost model uses unoptimized user-space simulator timings and a minor-fault microbenchmark, not a kernel page-replacement prototype.

4. **Evaluate dropped H4 (full-capacity shadow ranking agreement).**  
   Full ranking agreement was not measured. H4 was dropped from the hypothesis table; no claim is made from it.

5. **Re-run S3-FIFO/DA comparison with a fault-fixed public-trace controller.**  
   Because of the capacity–sampling fault, the public-trace DA result is not a fair evaluation of the controller’s selection logic on those traces. Only the faulty configuration, its diagnostics, and the inert re-selection are reported.
