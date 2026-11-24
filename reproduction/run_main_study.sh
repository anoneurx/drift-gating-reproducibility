#!/usr/bin/env sh
# Reproducible main study with the released simulator.
#
# Protocol (all parameters chosen on TRAINING traces only; test traces are
# touched exactly once):
#   1. Training: seed 100 (5 primitives x 3 = 15 stable, 4 scenarios x 8 = 32
#      non-stable traces). sweep_selection.py re-runs the full grid
#      (candidate-set size {4,5,6} x cost margin K {0,0.05,0.1,0.2} x
#      evaluation delay {2,5,10,20}, 48 configurations) with the released
#      simulator and selects 5 candidates (adding S3-FIFO), K = 0 and
#      evaluation delay = 10: the lowest training miss ratio with zero
#      stable-trace false confirmations. See sweep_results.csv.
#   2. Test: fresh seed 5001 (30 stable + 80 non-stable traces), never used in
#      the sweep. FROZEN configuration below; no post-hoc changes.
#
# Defaults otherwise: C=1000, W=2000 epochs, p=0.2, warm-up 20,000,
# h=5, alpha=1e-3, z=1.28, KS confirmation enabled, recency purge enabled.
set -eu
g++ -O2 -std=c++17 -o sim_full sim_full.cpp

COMMON="--ncand 5 --kfrac 0 --z 1.28 --edelay 10"
# Training-set sizes (15 stable + 32 non-stable); the simulator defaults are
# 30 + 80, which is the TEST set, so the training flags must be explicit.
TRAIN="--seed 100 --stable-per-prim 3 --per-scenario 8"

# 1. Parameter-selection sweep on training traces (released code, 48 configs).
python3 sweep_selection.py --jobs 4

# 2. Training run with the selected configuration (record only; not used for
#    any reported result, but kept for provenance).
./sim_full $TRAIN $COMMON --out main_study_training.csv --det main_study_training_detection.csv

# 3. PRIMARY test run, frozen configuration, with ablations enabled.
./sim_full --seed 5001 $COMMON --ablations \
    --out main_study_results.csv --det main_study_detection.csv

# 4. Capacity sensitivity (same frozen controller configuration).
./sim_full --seed 5001 $COMMON --C 500 \
    --out main_study_C500.csv --det main_study_C500_detection.csv
./sim_full --seed 5001 $COMMON --C 2000 \
    --out main_study_C2000.csv --det main_study_C2000_detection.csv

# 5. Sampling-rate sensitivity (same frozen controller configuration).
./sim_full --seed 5001 $COMMON --p 0.05 \
    --out main_study_p005.csv --det main_study_p005_detection.csv
./sim_full --seed 5001 $COMMON --p 0.1 \
    --out main_study_p01.csv --det main_study_p01_detection.csv

echo "Main-study CSVs written."
