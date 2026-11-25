# Path A pre-specification: policy-switching oracle ceiling

**Timestamp (UTC):** 2026-11-25T09:25:44Z  
**Local HEAD at timestamp:** `d54b0d959480062d3948a2b9ac70b42341894238`  
**Status:** fixed before running the new oracle experiment.

> Timestamp note: this design was fixed and timestamped in the local research
> repository before the oracle runs (UTC timestamp and HEAD above). The protocol
> and results were later mirrored to the public `drift-gating-reproducibility`
> repository. This is a local pre-run record, not an independent public
> registration.

## Question

On real/public traces, how much can any switching controller gain over the best
single static policy? The answer is obtained from a hindsight oracle that picks
the best policy in every fixed window and pays an explicit switching cost. The
oracle is an upper bound, not a deployable policy.

## Pre-specified hypothesis

**H1:** On the available real/public traces, the charged oracle gain over the
best single static policy is below the smallest worthwhile gain defined below
for most trace families and capacities. Consequently, switching controllers
have little headroom over a strong static policy such as S3-FIFO.

## Pre-specified endpoint

Primary endpoint, computed per trace and capacity:

```text
gain = best_static_miss_ratio - oracle_charged_miss_ratio
```

Secondary endpoints:

- objective gain after adding the switching penalty,
- number of oracle switches,
- fraction of traces in a family where `gain >= 0.02`,
- zero-cost oracle gain as an absolute upper bound.

Results are reported per trace, per family, per capacity, and per window length.
Failures are retained; no family is dropped post hoc.

## Smallest worthwhile gain

A gain is **worthwhile** only if both conditions hold:

1. absolute miss-ratio reduction `>= 0.02` (2.0 percentage points), and
2. it occurs on at least two thirds of traces in that family at that capacity.

If no family/capacity meets this bar, take Path A and report a decisive negative
result: switching has little headroom. If a family/capacity meets it, first test
whether trace features predict the gain on held-out families; only then consider
Path B.

## Traces

Use every locally available replayable real/public trace:

- 60 instrumented-program page-level traces (`traces_real/`, 15 families x 4 seeds),
- 12 public FIU held-out prefixes (`reproduction/public_split/`, 6 families x train/test),
- 6 public PDL 1M-record prefixes (`reproduction/phase6_pdl/`, 6 families).

The FIU capacity-pilot trace (`phase10_capacity_pilot/webusers.bin`) is excluded
from evaluation because capacity was selected on it.

Limitation fixed before running: this is 78 evaluation traces, not the hundreds
called for in the full Path A plan. That is reported as a limitation, not hidden.

## Capacities

Working-set size is the number of distinct page IDs in a trace. For each trace:

```text
C in {max(1, round(0.01*WSS)), max(1, round(0.05*WSS)), max(1, round(0.10*WSS))}
```

No capacity is retuned using oracle results.

## Simulation settings

- warm-up: `min(100000, floor(0.10 * trace_length))` references,
- primary window length: `50000` references,
- sensitivity window length: `100000` references,
- primary switch cost: `C` misses, interpreted as one full-cache refill,
- zero-cost oracle also reported as an upper bound.

Trailing references after the last full window are ignored consistently for all
policies and oracles.

## Oracle construction

For each (trace, capacity, policy), simulate the policy continuously over the
whole trace and record misses per fixed window. Policy state is maintained from
its own continuous replay, so the oracle assumes every policy is always warm.
It therefore overstates what an implementable controller could achieve.

For each window, the oracle selects the policy minimizing:

```text
window_misses(policy) + switch_cost * 1{policy != previous_policy}
```

The initial policy choice is not charged as a switch. Ties are broken by policy
name order. The charged miss ratio uses only the selected policies' misses. The
objective adds the switch penalty. This is an optimistic ceiling with an
explicit, pre-specified switch cost.

## Policies

Candidate static policies are the fixed policies implemented in
`reproduction/sim_full.cpp`:

```text
LRU, FIFO, CLOCK, LFU-A, MRU, 2Q, ARC, S3-FIFO, LeCaR, LPR-style,
SIEVE, W-TinyLFU, LHD, CAR, LIRS, CLOCK-Pro, CACHEUS,
3L-style, MGLRU-style, DIP-set-duel
```

DA variants and Belady `OPT` are excluded because they are controllers or a
different kind of bound. A recent learned policy is not implemented locally;
this is an explicit gap, not a silent omission.

## Statistics and reporting

- one row per trace/capacity/window length for best static and oracle,
- one row per trace/capacity/window/for each policy's window misses,
- per-family and per-capacity aggregates with family as the cluster unit,
- bootstrap confidence intervals by family added after the raw table exists,
  with trace-level resampling, B=10000 and fixed seed 20261125,
- all traces and all capacities retained.

## Decision rule

- **Small gain:** write the decisive measurement study. Claim: switching has
  little headroom over S3-FIFO on these trace families, with explicit scope.
- **Large gain:** derive and test a trace-feature rule on unseen families before
  attempting a kernel implementation.

## Frozen-artifact protection

No frozen artifact is modified. All new scripts, binaries, protocols, and result
CSVs are additive under `reproduction/pathA_oracle/`.
