# blackwall-drift

A dependency-free Rust implementation of the deterministic core of the Black Wall
drift-gating simulator. It reproduces the frozen seed-5001 miss ratios, policy
switch counts, shadow-evaluation counts, and drift-detection confirms from the
original study.

The port intentionally omits non-deterministic timing measurements. It emits only
reproducible values.

## Build and test

```sh
cargo test --release
cargo run --release -- --check
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

This repository contains only the core Rust simulator: deterministic RNG,
synthetic trace generation, LRU, S3-FIFO, CUSUM drift gating, KS confirmation,
sampled shadow evaluation, and CSV output. It does not include the paper PDF,
protocol documents, Python analysis scripts, or C++ sources.

## License

MIT. See `LICENSE` and `CITATION.cff`.
