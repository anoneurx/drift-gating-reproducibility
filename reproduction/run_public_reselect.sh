#!/bin/sh
# Evaluate the frozen and re-selected DA configurations on held-out suffixes
# of the six public FIU traces.  Frozen: ncand=5, K=0, edelay=10 (the main-study
# selection).  Re-selected: parameters chosen on the six training prefixes by
# sweep_public_selection.py (ncand=4, K=0, edelay=2 at the time of writing).
set -eu
SIM=./sim_full
NP=--np
COMMON="$NP 1048576 --C 20000 --warm 50000 --kfrac 0 --z 1.28 \
  --s3frac 0.05 --twoqkin 125 --lprthr 0.1 --lecarlr 0.6 --lirsfrac 0.05 \
  --methods LRU,S3-FIFO,DA"
TRACES=""
for f in public_split/*.test.bin; do TRACES="$TRACES --trace $f"; done

$SIM $COMMON --ncand 5 --edelay 10 $TRACES \
  --out public_test_frozen.csv --det public_test_frozen_det.csv

$SIM $COMMON --ncand 4 --edelay 2 $TRACES \
  --out public_test_reselected.csv --det public_test_reselected_det.csv
