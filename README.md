# Drift-gating reproducibility

This repository now contains the full research code package:

- **Rust** (`src/`, `Cargo.toml`): dependency-free deterministic core that reproduces the frozen seed-5001 miss ratios, policy switch counts, shadow-evaluation counts, and drift-detection confirms.
- **C++** (`reproduction/*.cpp`, `reproduction/pathA_oracle/*.cpp`): authoritative trace-driven simulator, timing/async builds, fault-latency prototype, real-trace generator, and the Path A policy-oracle harness.
- **Python** (`reproduction/**/*.py`): trace conversion, study drivers, numeric/hygiene checkers, bootstrap analyses, figure-table generators, and Path A oracle runner/aggregator.

The Rust core intentionally omits non-deterministic timing measurements and emits
only reproducible values. The C++/Python layers retain the original measurement,
conversion, and analysis workflows.

## Build and test

Rust core:

```sh
cargo test --release
cargo run --release -- --check
```

Authoritative C++ simulator and Path A oracle:

```sh
g++ -O2 -std=c++17 -o reproduction/sim_full reproduction/sim_full.cpp
g++ -O2 -std=c++17 -o reproduction/pathA_oracle/oracle_switching \
  reproduction/pathA_oracle/oracle_switching.cpp
```

Python checks:

```sh
python3 reproduction/check_paper_numbers.py
python3 reproduction/final_hygiene.py
python3 reproduction/pathA_oracle/check_pathA_oracle.py
python3 reproduction/pathA_oracle/analyze_pathA_oracle.py
```

## Frozen validation command

```sh
cargo run --release -- \
  --seed 5001 --ncand 5 --kfrac 0 --z 1.28 --edelay 10 \
  --out results.csv --det detection.csv --check
```

`--check` verifies the 80 non-stable traces against the frozen aggregates:

| Method      | Miss ratio | Switches | Shadow evals |
|-------------|-----------:|---------:|-------------:|
| DA          | 0.45288775 |   2.3625 |        6.475 |
| ContShadow  | 0.42283225 |   3.1500 |       27.3875 |
| S3-FIFO     | 0.468310625 |      — |            — |
| LRU         | 0.56997525 |      — |            — |

## Outputs

`results.csv` columns:

```text
scenario,seed,method,miss_ratio,switches,shadow_evals
```

`detection.csv` columns:

```text
scenario,seed,method,n_bounds,detected,delays,spurious,confirms,false_after_100k
```

## Scope

The Rust core contains deterministic RNG, synthetic trace generation, LRU,
S3-FIFO, CUSUM drift gating, KS confirmation, sampled shadow evaluation, and CSV
output. The `reproduction/` tree contains the C++ simulator variants, driver
scripts, analysis scripts, frozen raw CSVs, and Path A oracle artifacts.

Large binary trace files are not stored here. See `reproduction/README.md` and
`reproduction/pathA_oracle/README.md` for the expected trace layout and commands.
No manuscript PDFs are included.

The Path A design and results are recorded in `PATH_A_PROTOCOL.md` and
`PATH_A_RESULTS.md`: the primary 50k-window run is a decisive negative result;
the 100k-window sensitivity run opens one fragile single-family gate that needs
more traces before Path B can be justified.

## License

MIT. See `LICENSE` and `CITATION.cff`.
