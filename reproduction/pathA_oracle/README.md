# Path A oracle ceiling

This directory contains the additive experiment that compares the best single
static policy with a hindsight oracle that picks the best policy in every fixed
window and pays a pre-specified switching cost.

The design is fixed in `../../PATH_A_PROTOCOL.md` before the first full run.
The later trace-replication extension is fixed separately in
`../../PATH_A_EXTENSION_PROTOCOL.md`.

## Contents

| File | Purpose |
|---|---|
| `oracle_switching.cpp` | Reuses all fixed-policy implementations from `reproduction/sim_full.cpp` and adds the per-window oracle harness. |
| `oracle_switching` | Compiled binary (generated). |
| `run_pathA_oracle.py` | Enumerates all local real/public traces, computes WSS-relative capacities, and runs the oracle in parallel. |
| `analyze_pathA_oracle.py` | Aggregates by family/capacity/window and applies the pre-specified decision rule. |
| `check_pathA_oracle.py` | Read-only consistency checks on the raw outputs. |
| `extract_pathA_features.py` | Auxiliary trace features prepared for the held-out-family predictive-rule gate; not used to select the oracle endpoint. |
| `prepare_pathA_extension.py` | Converts the pre-specified extra public FIU traces and writes a hash manifest. |
| `run_pathA_extension.py` | Runs the same oracle on the extension manifest. |
| `analyze_pathA_extension.py` | Applies the pre-specified extension decision rule. |
| `verify_pathA_evidence.py` | Read-only verifier for all Path A counts, decisions, protocol timestamps, and public sync. |
| `results/summary.csv` | One charged and one zero-cost oracle row per trace/capacity/window. |
| `results/policy.csv` | Total misses for every candidate static policy. |
| `results/windows.csv` | Per-window oracle choice, switch flag, and per-window best policy. |
| `results/manifest.csv` | Trace inventory, WSS, max ID, and capacities used. |
| `results/aggregate_family.csv` | Per-family/capacity aggregates with family-clustered bootstrap CIs. |
| `results/decision.csv` | Path A vs Path B gate. |

## Build

```sh
g++ -O2 -std=c++17 -o reproduction/pathA_oracle/oracle_switching \
  reproduction/pathA_oracle/oracle_switching.cpp
```

## Run

Primary pre-specified run:

```sh
python3 reproduction/pathA_oracle/run_pathA_oracle.py --windows 50000 --workers 6
python3 reproduction/pathA_oracle/analyze_pathA_oracle.py
```

Sensitivity run:

```sh
python3 reproduction/pathA_oracle/run_pathA_oracle.py --windows 100000 --workers 6 \
  --results-dir reproduction/pathA_oracle/results_w100000
python3 reproduction/pathA_oracle/analyze_pathA_oracle.py \
  --results-dir reproduction/pathA_oracle/results_w100000
python3 reproduction/pathA_oracle/check_pathA_oracle.py \
  --results-dir reproduction/pathA_oracle/results_w100000
```

Trace-replication extension (pre-specified in `../../PATH_A_EXTENSION_PROTOCOL.md`):

```sh
python3 reproduction/pathA_oracle/prepare_pathA_extension.py \
  --src /path/to/fiu/zst --bin /path/to/extension/bin
python3 reproduction/pathA_oracle/run_pathA_extension.py --workers 6
python3 reproduction/pathA_oracle/check_pathA_oracle.py \
  --results-dir reproduction/pathA_oracle/results_extension
python3 reproduction/pathA_oracle/analyze_pathA_oracle.py \
  --results-dir reproduction/pathA_oracle/results_extension
python3 reproduction/pathA_oracle/analyze_pathA_extension.py
```

## Oracle definition

For each trace, capacity, and policy, the policy is replayed continuously over
the full trace. Misses are accumulated in fixed windows after warm-up. The
oracle selects, for each window, the policy minimizing:

```text
window_misses(policy) + switch_cost * 1{policy != previous_policy}
```

The initial policy choice is not charged as a switch. The primary switch cost is
`C` misses, interpreted as one full-cache refill. A zero-cost oracle is also
reported as an absolute upper bound.

All policies are assumed warm because each maintains its own continuous state.
The oracle therefore overstates what an implementable controller can achieve.
It is a ceiling, not a proposed policy.

## Scope limits

- 78 evaluation traces are available locally, not the several hundred in the
  full Path A plan.
- The traces are instrumented-program page traces, public FIU held-out prefixes,
  and bounded public PDL prefixes. They are not full public traces from many
  families.
- A recent learned policy is not implemented; this is reported, not hidden.
- The pre-run timestamp in `PATH_A_PROTOCOL.md` is a local git record later
  mirrored publicly, not an independent public registration.

No frozen artifact is modified by this experiment.
