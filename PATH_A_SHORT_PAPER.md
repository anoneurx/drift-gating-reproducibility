# Switching Policies Rarely Beats the Best Static Page Replacement Policy: A Hindsight Oracle Study

## Abstract

A drift-aware replacement controller can only help if there is headroom above a
strong static policy. We measured that headroom with a pre-specified hindsight
oracle: 20 fixed policies are replayed continuously and, in every fixed window,
the oracle chooses the policy with the lowest misses after paying an explicit
switch cost equal to one full-cache refill. The study uses 78 real/public traces
(27 families) at three capacities relative to working-set size. With the
pre-specified 50,000-reference window, **0/117** family-capacity groups reached
the worthwhile-gain bar of a 0.02 absolute miss-ratio reduction on at least
two thirds of traces; the largest family-mean charged gain was 0.01355. Even a
zero-switch-cost oracle cleared the bar in only 3/117 groups, all from one FIU
family. A 100,000-reference sensitivity run opened 1/117 groups, but that group
contains a single trace and a single capacity, with gain 0.04449. These results
support a narrow Path A conclusion: on the available traces, switching has
little demonstrated headroom over the best static policy. Path B is not
justified until the single sensitivity gate reproduces on more traces and
unseen families.

## 1. Question

Page-replacement papers often motivate adaptive controllers by showing that the
best policy changes across workloads or phases. That observation is not enough:
a controller must gain enough after switching cost to beat a strong static
policy. We ask:

> How large is the best achievable gain from switching policies, relative to
> the best single static policy on the same trace and capacity?

We answer this with an oracle, not a deployable controller. The oracle is a
hindsight ceiling: it knows each window's best policy and assumes every policy
is warm. Any real controller should be expected to do worse.

The design was fixed in `PATH_A_PROTOCOL.md` at `2026-11-25T09:25:44Z`, with
local HEAD `d54b0d959480062d3948a2b9ac70b42341894238`, before the oracle runs.
It was later mirrored publicly; it is a local pre-run record, not an independent
public registration.

## 2. Data and experimental design

### 2.1 Traces

We used every locally replayable real/public trace available at pre-specification
time:

- 60 instrumented-program page-level traces: 15 families x 4 seeds.
- 12 public FIU held-out prefixes: 6 families x train/test.
- 6 public PDL 1M-record prefixes.

Total: **78 traces across 27 families**. The FIU `webusers` capacity-pilot trace
was excluded because capacity had been selected on it. Public FIU/PDL traces are
block/object traces converted to page-ID form, not native VM page traces.

### 2.2 Capacities and simulation

Working-set size (WSS) is the number of distinct page IDs in a trace. For each
trace we used capacities `round(0.01*WSS)`, `round(0.05*WSS)`, and
`round(0.10*WSS)`, floored at 1. Warm-up was
`min(100000, floor(0.10 * trace_length))` references. Evaluation used
50,000-reference windows for the primary run and 100,000-reference windows for
the sensitivity run. Trailing references after the last full window were
ignored consistently.

Twenty fixed policies from `reproduction/sim_full.cpp` were candidates: LRU,
FIFO, CLOCK, LFU-A, MRU, 2Q, ARC, S3-FIFO, LeCaR, LPR-style, SIEVE, W-TinyLFU,
LHD, CAR, LIRS, CLOCK-Pro, CACHEUS, 3L-style, MGLRU-style, and DIP-set-duel.
Drift-aware variants, Belady `OPT`, and learned policies were excluded. The
absence of a recent learned baseline is a reported limitation.

### 2.3 Oracle and endpoint

Each candidate policy was replayed continuously over the whole trace, recording
misses per fixed window. For each window, the oracle selected the policy
minimizing:

```text
window_misses(policy) + switch_cost * 1{policy != previous_policy}
```

The initial choice was not charged as a switch; ties were broken by policy name.
The primary switch cost was `C` misses, interpreted as one full-cache refill. A
zero-cost oracle was also reported as an absolute upper bound. The charged miss
ratio uses only selected policies' misses; the objective ratio adds the switch
penalty.

The primary endpoint was:

```text
gain = best_static_miss_ratio - oracle_charged_miss_ratio
```

A gain was **worthwhile** only if `gain >= 0.02` and it occurred on at least
`2/3` of traces in that family-capacity group. Groups were keyed by family and
exact capacity, because capacities differ slightly across traces with different
WSS. Bootstrap confidence intervals used trace-level resampling with `B=10000`
and seed `20261125`.

## 3. Results

Both runs passed the raw-output checker with `FAILURES: 0`. The primary run
produced 468 summary rows, 4,680 policy rows, and 1,542 window rows; the
sensitivity run produced the same summary/policy counts and 663 window rows.

| Window | Oracle cost | Groups meeting bar | Max family-mean gain | Mean row gain | Best static = S3-FIFO |
|---:|---|---:|---:|---:|---:|
| 50,000 | charged `C` | 0/117 | 0.01355 | -0.00130 | 101/234 |
| 50,000 | zero | 3/117 | 0.05616 | 0.00120 | 101/234 |
| 100,000 | charged `C` | 1/117 | 0.04449 | -0.00048 | 101/234 |
| 100,000 | zero | 1/117 | 0.04449 | 0.00072 | 101/234 |

### 3.1 Primary 50,000-reference run

No charged-cost family-capacity group met the pre-specified bar. The largest
family-mean charged gain was 0.01355 on `fiu_online.cs.fiu.edu` at `C=7769`,
with fraction `0/1` above 0.02. The mean charged gain across 234 trace-capacity
rows was negative (-0.00130): once a full-cache-refill switch cost is charged,
the hindsight oracle was often worse than the best static policy.

The best static policy was S3-FIFO in 101/234 rows (43.2%), but it was not
universal. Sixteen policies won at least one row, including 2Q (45), CLOCK-Pro
(18), CAR (18), LHD (11), and MGLRU-style (10). The oracle comparison is
therefore not equivalent to a fixed S3-FIFO-only baseline.

With zero switch cost, 3/117 groups met the bar. All three were from
`fiu_online.cs.fiu.edu`, and each group contained one trace. The largest
zero-cost family-mean gain was 0.05616 at `C=15539`. No instrumented-program or
PDL family cleared the bar even with free switching.

### 3.2 Sensitivity 100,000-reference run

The charged oracle cleared the bar in exactly one group:
`fiu_online.cs.fiu.edu`, `C=15539`, mean gain 0.04449, two oracle switches.
That group contains only the trace `fiu_online.cs.fiu.edu_test`. The zero-cost
oracle cleared the bar in the same single group. No other family or capacity
cleared the bar.

This mechanically opens the pre-specified `PATH_B_GATE`, but it is a fragile
gate: one family, one trace, one capacity, and absent in the primary 50,000-run.
It is evidence for collecting more traces, not evidence for a kernel
implementation or an end-to-end systems claim.

## 4. Interpretation

The primary result is a decisive negative for switching headroom on the
available evidence. At 50,000-reference windows, even an oracle that knows the
best policy in every window and starts every policy warm never delivered a
worthwhile charged gain at the family-capacity level. At 100,000-reference
windows, the single exception is too narrow to generalize.

The correct claim is deliberately narrow:

> On 78 local real/public traces at three WSS-relative capacities, a hindsight
> per-window policy oracle with a full-cache-refill switch cost delivered no
> worthwhile gain in 117/117 family-capacity groups at 50,000-reference
> windows. At 100,000-reference windows, 1/117 groups cleared the bar, from one
> FIU family and one trace. This is a gate for more evidence, not a Path B
> result.

Because the oracle is warm and clairvoyant, a real controller has less headroom
than these numbers. Detection delay, misclassification, cold-start costs, and
implementation overhead would all reduce the achievable gain. Conversely, the
switch-cost model is simple: `C` misses approximates one full-cache refill but
does not model every system-level cost.

## 5. Threats to validity

- 78 traces and 27 families, not the several hundred in the full Path A plan.
- FIU/PDL traces are converted block/object traces, not native page-level VM
  traces.
- Instrumented-program traces come from a limited set of programs and seeds.
- No recent learned replacement policy is included.
- No cross-check against libCacheSim was performed.
- The 100,000-window gate is a single trace; train/test capacities differ, so
  the two FIU online prefixes do not form a replicated group at `C=15539`.
- The pre-run timestamp is local and was mirrored later; it is not a public
  registration.

## 6. Reproducibility

Artifacts:

- `PATH_A_PROTOCOL.md`: pre-specified design and timestamp.
- `PATH_A_RESULTS.md`: primary and sensitivity result memo.
- `reproduction/pathA_oracle/oracle_switching.cpp`: C++ oracle harness reusing
  the fixed-policy implementations from `reproduction/sim_full.cpp`.
- `reproduction/pathA_oracle/run_pathA_oracle.py`: trace discovery, capacity
  computation, and parallel run driver.
- `reproduction/pathA_oracle/analyze_pathA_oracle.py`: aggregation and gate.
- `reproduction/pathA_oracle/check_pathA_oracle.py`: read-only consistency check.
- `reproduction/pathA_oracle/results/` and `results_w100000/`: raw and
  aggregated CSVs.

Commands:

```sh
g++ -O2 -std=c++17 -o reproduction/pathA_oracle/oracle_switching \
  reproduction/pathA_oracle/oracle_switching.cpp
python3 reproduction/pathA_oracle/run_pathA_oracle.py --windows 50000 \
  --workers 6
python3 reproduction/pathA_oracle/check_pathA_oracle.py
python3 reproduction/pathA_oracle/analyze_pathA_oracle.py
python3 reproduction/pathA_oracle/run_pathA_oracle.py --windows 100000 \
  --workers 6 --results-dir reproduction/pathA_oracle/results_w100000
python3 reproduction/pathA_oracle/check_pathA_oracle.py \
  --results-dir reproduction/pathA_oracle/results_w100000
python3 reproduction/pathA_oracle/analyze_pathA_oracle.py \
  --results-dir reproduction/pathA_oracle/results_w100000
```

The public code/CSV package is at
`https://github.com/anoneurx/drift-gating-reproducibility.git`. Frozen main-study
artifacts were not modified by this experiment.

## 7. Conclusion

On the available real/public traces, the headroom for policy switching is small.
The primary oracle result is decisively negative, and the sensitivity exception
is a single-trace gate rather than a robust effect. We therefore take Path A:
report the measurement study with explicit scope limits. Path B remains closed
until larger trace coverage, a learned-policy baseline, and held-out-family
validation show a reproducible worthwhile gain.
