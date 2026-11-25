# Path A primary oracle result

**Primary decision:** `PATH_A_DECISIVE_NEGATIVE`  
**Sensitivity decision:** `PATH_B_GATE` (one fragile group; see below)  
**Data:** `reproduction/pathA_oracle/results/` and `results_w100000/`  
**Design:** pre-specified in `PATH_A_PROTOCOL.md` at 2026-11-25T09:25:44Z.

## Run summary

- 78 replayable real/public traces: 60 instrumented-program page traces, 12 public FIU held-out prefixes, 6 public PDL 1M-record prefixes.
- 234 trace x capacity jobs, capacities = 1%, 5%, 10% WSS.
- 117 family x capacity groups.
- 468 summary rows (charged and zero-cost), 4,680 policy rows, 1,542 window rows.
- Window = 50,000 references; warm-up = 10% of trace length capped at 100,000.
- Primary switch cost = `C` misses, interpreted as one full-cache refill.
- Consistency checker: `FAILURES: 0`.

## Primary endpoint

The pre-specified worthwhile-gain bar was:

```text
gain >= 0.02 absolute miss ratio on at least 2/3 of traces in a family/capacity
```

Result with the charged oracle:

- **0 of 117** family x capacity groups met the bar.
- Largest family-mean charged gain: **0.01355** on `fiu_online.cs.fiu.edu` at `C=7769`, still below 0.02.
- Mean charged gain across all 234 trace x capacity rows: **-0.00130**.
- Charged oracle was often worse than the best static policy because the switch cost exceeded the per-window miss saving.
- The best single static policy was S3-FIFO in **101/234** trace x capacity rows (43.2%); the best policy varied across 16 policies, so the oracle comparison is not equivalent to a fixed S3-FIFO-only baseline.

Top charged groups by family-mean gain:

| Family | Capacity | Mean charged gain | Fraction >= 0.02 | Mean switches |
|---|---:|---:|---:|---:|
| `fiu_online.cs.fiu.edu` | 7769 | 0.01355 | 0.000 | 1.00 |
| `fiu_madmax` | 6564 | 0.00873 | 0.000 | 1.00 |
| `hashjoin` | 101 | 0.00126 | 0.000 | 2.00 |
| `fiu_webresearch` | 407 | 0.00052 | 0.000 | 1.00 |
| `hashjoin` | 50 | 0.00050 | 0.000 | 1.75 |

## Zero-cost upper bound

With switch cost explicitly set to zero:

- **3 of 117** groups meet the bar, all on `fiu_online.cs.fiu.edu`.
- Largest zero-cost family-mean gain: **0.05616** at `C=15539`.
- Mean zero-cost gain across all 234 rows: **0.00120**.

This is the important ceiling result: even an oracle that may switch for free clears the pre-specified bar in only 3/117 groups, and all of them are one FIU family. Once the pre-specified `C`-miss switching cost is charged, no group clears the bar.

## Interpretation

The primary run supports **Path A**: at 50,000-reference windows, the charged oracle never delivered a worthwhile gain at the family-capacity level. The sensitivity run finds one fragile exception at 100,000-reference windows. The honest combined claim is:

> On 78 local real/public traces at three WSS-relative capacities, a hindsight per-window policy oracle with a full-cache-refill switch cost delivered no worthwhile gain in 117/117 family-capacity groups at 50,000-reference windows. At 100,000-reference windows, 1/117 groups cleared the bar, from one FIU family and one trace. This is a gate for more evidence, not a Path B result.

This does **not** prove that switching can never help. The scope limits below matter.

## Sensitivity: 100,000-reference windows

The pre-specified sensitivity run completed with `FAILURES: 0`:

- 468 summary rows, 4,680 policy rows, 663 window rows.
- Charged-cost decision: **1/117** family-capacity groups met the bar.
- The single group is `fiu_online.cs.fiu.edu`, `C=15539`, with mean charged gain **0.04449** and 2 oracle switches. It contains one trace: `fiu_online.cs.fiu.edu_test`.
- The zero-cost bound also met the bar in that same single group.
- No other family or capacity cleared the bar.

This mechanically opens the pre-specified `PATH_B_GATE`, but the gate is fragile: it is one FIU family, one trace, one capacity, and it is absent in the primary 50,000-reference run. It is not sufficient evidence for a kernel implementation or an end-to-end systems claim. The correct next move is to test whether the gain reproduces on more traces from that family and on unseen families before considering Path B.

## Extension replication test

The pre-specified extension in `PATH_A_EXTENSION_PROTOCOL.md` added ten additional FIU records and tested the gate on more of the FIU-online trace and two unseen families. The result is recorded in `PATH_A_EXTENSION_RESULTS.md`:

- decision: **`PATH_A_STANDS`**;
- FIU-online replicas required 2 distinct traces, found 1;
- unseen-family groups required 1, found 0;
- the charged gain was found again only on a later segment of the same online trace (`fiu_online_seg1p5m_2m`, gain `0.04656` at `C=8116`, `W=100000`).

The single-trace sensitivity gate therefore does not survive the replication test. No primary result was modified.

A read-only verification of every reported number and its public copy is recorded in `PATH_A_VERIFICATION.md`.

## Scope limits

- 78 traces, not the several hundred in the full Path A plan.
- Public FIU/PDL traces are block/object traces converted to page-ID form, not native page-level VM traces.
- Instrumented-program traces are page-level but locally generated from a limited set of programs and seeds.
- A recent learned replacement policy is not implemented.
- The pre-run timestamp is a local git record that was later mirrored publicly; it is not an independent public registration.
- The oracle assumes every candidate policy is always warm and maintains its own continuous state. It is an optimistic ceiling, not a deployable controller.

## Next steps

1. Keep the short Path A paper aligned with the extension result.
2. Add a recent learned policy baseline before any Q1 generality claim.
3. Cross-check against libCacheSim.
4. Keep the held-out-family feature rule closed: the sensitivity gate did not survive replication.
5. Keep Path B closed; reopening it requires new independent evidence, not this sensitivity gate.
