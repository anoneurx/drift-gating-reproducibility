#!/usr/bin/env bash
# =============================================================================
# scripts/run_all.sh
# Full reproduction pipeline for
# "When Does Policy Switching Beat the Best Static Policy?"
#
# Expected runtime: 4–8 hours on a modern 8-core machine.
# Outputs land in:
#   results/raw/          (CSV per step)
#   drift_gating_latex_source/  (table .tex + figure .pdf)
#   Drift_Gating_Final_IEEE.pdf
# =============================================================================
set -euo pipefail

PYTHON="${PYTHON:-python3}"
STUDY="reproduction/pathA_study"
LATEX="drift_gating_latex_source"

echo "================================================================"
echo " Drift-Gating Full Reproduction  $(date)"
echo "================================================================"

# Step 0 — build simulator
echo "[1/6] Building pathA_sim and real_io_bench ..."
make build

# Step 1 — oracle + controllers (88 traces × 3 caps × W={10k,25k,50k,100k})
echo "[2/6] Running oracle + controllers ..."
$PYTHON $STUDY/run_study.py

# Step 2 — fine cost/window sweep (W∈{5k,10k,25k,50k}, 9-point cost grid, 25/50% WSS)
echo "[3/6] Running reviewer fine-sweep ..."
$PYTHON $STUDY/run_reviewer_fixes.py

# Step 3 — shadow-budget ablation
echo "[4/6] Running shadow ablation ..."
$PYTHON $STUDY/run_ablation.py

# Step 4 — real I/O benchmark (pread latency)
echo "[5/6] Running real I/O benchmark ..."
(cd $STUDY && $PYTHON run_reviewer_fixes.py --bench-only)

# Step 5 — generate all tables + figures
echo "[6/6] Generating tables and figures ..."
$PYTHON $STUDY/generate_paper_assets.py

# Step 6 — build PDF
echo "[PDF] Building LaTeX PDF ..."
(cd $LATEX && $PYTHON build.py)

echo ""
echo "================================================================"
echo " Done.  Key outputs:"
echo "   PDF:    Drift_Gating_Final_IEEE.pdf"
echo "   Tables: drift_gating_latex_source/table_*.tex"
echo "   Figs:   drift_gating_latex_source/figs/*.pdf"
echo "   CSVs:   results/raw/"
echo "================================================================"
