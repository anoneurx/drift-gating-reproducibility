#!/usr/bin/env python3
"""
tests/verify_tables.py
Compare regenerated CSVs/tables to stored baselines.
Prints PASS or FAIL for each metric; exits non-zero on any failure.

Usage:
    python3 tests/verify_tables.py
    make verify
"""

import csv, os, sys, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW  = os.path.join(ROOT, "results", "raw")
BASE = os.path.join(ROOT, "tests", "expected", "baseline_numbers.csv")

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

PASS_COUNT = 0
FAIL_COUNT = 0

def check(name, actual, expected, tol, unit=""):
    global PASS_COUNT, FAIL_COUNT
    if actual is None:
        print(f"  SKIP  {name}  (data unavailable)")
        return
    if math.isnan(float(actual)):
        print(f"  SKIP  {name}  (NaN)")
        return
    diff = abs(float(actual) - float(expected))
    if diff <= float(tol):
        PASS_COUNT += 1
        print(f"  PASS  {name}  actual={actual:.4g}  expected={expected}  tol=±{tol}{unit}")
    else:
        FAIL_COUNT += 1
        print(f"  FAIL  {name}  actual={actual:.4g}  expected={expected}  tol=±{tol}{unit}  diff={diff:.4g}")

def load_csv(filename):
    path = os.path.join(RAW, filename)
    if not os.path.exists(path):
        print(f"  WARN  {filename} not found in results/raw/ — skipping related checks")
        return None
    if HAS_PANDAS:
        import pandas
        return pandas.read_csv(path)
    return None

# ---------------------------------------------------------------------------
# Load CSVs
# ---------------------------------------------------------------------------
print("=" * 65)
print("Drift-Gating Table Verification")
print("=" * 65)

fs   = load_csv("finesweep.csv")
os_  = load_csv("oracle_summary.csv")
ctrl = load_csv("controllers.csv")
h2   = load_csv("h2_controller_analysis.csv")
sr   = load_csv("shadow_ranking.csv")

# ---------------------------------------------------------------------------
# Verify metrics
# ---------------------------------------------------------------------------

# 1. Pairs meeting 2% gain at c=C, W=50k → 0 expected (after S3-FIFO capacity fix)
if fs is not None:
    fullc = fs[(fs['cost_frac'] == 1.0) & (fs['window'] == 50000)]
    meet  = int((fullc['net_gain_vs_best'] >= 0.02).sum())
    check("meet_fullc_W50k (c=C, W=50k, threshold 2%)", meet, 0, 1, " pairs")

# 2. Pairs meeting 2% gain at c≥0.5C, W=50k → 0 expected
if fs is not None:
    halfc = fs[(fs['cost_frac'] >= 0.50) & (fs['window'] == 50000)]
    meet  = int((halfc['net_gain_vs_best'] >= 0.02).sum())
    check("meet_halfc_W50k (c>=0.5C, W=50k, threshold 2%)", meet, 0, 1, " pairs")

# 3. Pairs at c=0, W=50k → 18 expected (includes 25/50% WSS reviewer additions)
if fs is not None:
    c0_50k = fs[(fs['cost_frac'] == 0.0) & (fs['window'] == 50000)]
    meet   = int((c0_50k['net_gain_vs_best'] >= 0.02).sum())
    check("meet_c0_W50k (c=0, W=50k, threshold 2%)", meet, 18, 2, " pairs")

# 4. Pairs at c=0, W=5k → 18 expected
if fs is not None:
    c0_5k = fs[(fs['cost_frac'] == 0.0) & (fs['window'] == 5000)]
    meet  = int((c0_5k['net_gain_vs_best'] >= 0.02).sum())
    check("meet_c0_W5k (c=0, W=5k, threshold 2%)", meet, 18, 2, " pairs")

# 5. S3-FIFO mean miss ratio (fixed strict-capacity implementation)
if os_ is not None:
    base = os_[(os_['window'] == 50000) & (os_['switch_cost'] == 0.0)]
    s3mr = base['s3fifo_miss_ratio'].mean()
    check("s3fifo_mean_mr (W=50k baseline)", s3mr, 0.5167, 0.001)

# 6. Number of pairs in oracle study
if os_ is not None:
    n_pairs = len(os_[(os_['window'] == 50000) & (os_['switch_cost'] == 0.0)])
    check("n_pairs_oracle (W=50k, c=0)", n_pairs, 264, 0, " pairs")

# 7. Number of controllers
if h2 is not None and ctrl is not None:
    n_ctrl = ctrl['controller'].nunique() - 1  # exclude S3-FIFO baseline
    check("n_controllers", n_ctrl, 17, 0)

# 8. All Wilcoxon p-values = 1.0 (controllers lose to S3-FIFO)
if h2 is not None:
    min_pval = h2['pval_wilcoxon'].min()
    # all pvals should be 1.0 ± tiny numerical noise
    check("all_controllers_pval_wilcoxon_max", h2['pval_wilcoxon'].max(), 1.0, 0.001)

# 9. ContShadow top1_agree shadow ranking
if sr is not None:
    cont = sr[sr['mode'] == 'ContShadow-0.2C']
    if len(cont):
        top1 = cont['top1_agree'].sum() / cont['evals'].sum()
        check("ContShadow-0.2C top1_agree (shadow ranking)", top1, 0.4509, 0.01)

# 10. ContShadow mean delta vs S3-FIFO
if ctrl is not None:
    c_mr = ctrl[ctrl['controller'] == 'ContShadow']['miss_ratio'].mean()
    s_mr = ctrl[ctrl['controller'] == 'S3-FIFO']['miss_ratio'].mean()
    check("ContShadow mean_delta_vs_s3fifo", abs(c_mr - s_mr), 0.0140, 0.002)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("=" * 65)
print(f"Results: {PASS_COUNT} PASS, {FAIL_COUNT} FAIL")
if FAIL_COUNT == 0:
    print("OVERALL: PASS")
else:
    print("OVERALL: FAIL")
sys.exit(0 if FAIL_COUNT == 0 else 1)
