#!/usr/bin/env python3
"""Cost break-even model for drift-gated versus continuous shadow evaluation.

The reviewer asked for the shadow-evaluation cost at which drift-aware (DA)
evaluation beats continuous shadow evaluation (ContShadow) in *total* time.
This script makes the model explicit and writes both a CSV and a figure.

Measured inputs (means over the 80 non-stable fresh test traces, produced by
`run_main_study.sh` and read from `main_study_results.csv`):

    method        miss ratio   shadow evals/trace   ns/reference
    DA                m_DA          E_DA              t_DA
    S3-FIFO           m_S3          0                 t_S3
    ContShadow        m_CS          E_CS              t_CS

The times are simulated policy costs from the released single-threaded
simulator and exclude page-fault service.  Let c_m be the cost of one miss
(page fault + service) and c_e the cost of one shadow evaluation, both in ns.
With the same fast path for both methods,

    T = N*t0 + N*m*c_m + E*c_e

so DA has lower total time than ContShadow iff

    (m_DA - m_CS)*c_m + (E_DA - E_CS)*c_e/N < 0
    => c_e > R*c_m,   R = N*(m_DA - m_CS)/(E_CS - E_DA).

Equivalently, for a given evaluation cost, DA wins iff

    c_m < c_e/R.

The direct measured-time version, which does not decompose the simulator's
time, is T = t + m*c_m and gives c_m* = (t_CS - t_DA)/(m_DA - m_CS).
Both versions are reported; they agree to within the timing noise when the
simulator's implied evaluation cost is used.

Run: python3 cost_model.py
"""
import csv
import os
from collections import defaultdict
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "main_study_results.csv")
CSVOUT = os.path.join(HERE, "cost_model.csv")
FIGOUT = os.path.join(HERE, "fig8_breakeven.png")
NONSTABLE = ("abrupt", "gradual", "recurring", "composite")
# Generated non-stable trace lengths (sim_full.cpp): abrupt/gradual 6x100k,
# recurring 6x80k, composite 5x100k.
TRACE_LENGTHS = {"abrupt": 600_000, "gradual": 600_000,
                 "recurring": 480_000, "composite": 500_000}
N_AVG = mean(TRACE_LENGTHS.values())


def load_means():
    d = defaultdict(list)
    for r in csv.DictReader(open(SRC)):
        if r["scenario"] in NONSTABLE:
            d[r["method"]].append(r)
    out = {}
    for m in ("DA", "ContShadow", "S3-FIFO", "LRU"):
        rows = d[m]
        out[m] = {
            "miss": mean(float(r["miss_ratio"]) for r in rows),
            "evals": mean(float(r["shadow_evals"]) for r in rows),
            "ns": mean(float(r["ns_per_ref"]) for r in rows),
            "n": len(rows),
        }
    return out


def main():
    m = load_means()
    da, cs = m["DA"], m["ContShadow"]
    delta_m = da["miss"] - cs["miss"]          # positive: DA is worse
    delta_e = cs["evals"] - da["evals"]        # positive: CS does more evals
    delta_t = cs["ns"] - da["ns"]              # positive: CS is slower

    # Direct measured-time break-even (no decomposition).
    cm_star_direct = delta_t / delta_m         # ns per miss

    # Component model: R is the evaluation-cost / miss-cost ratio at break-even.
    R = N_AVG * delta_m / delta_e              # dimensionless
    ce_implied = delta_t * N_AVG / delta_e     # ns per evaluation implied by the times
    cm_star_component = ce_implied / R         # ns per miss at the implied cost

    print("Measured means over 80 non-stable traces")
    for name in ("DA", "ContShadow", "S3-FIFO", "LRU"):
        v = m[name]
        print(f"  {name:12} miss={v['miss']:.4f} evals={v['evals']:.2f} "
              f"ns/ref={v['ns']:.1f}")
    print()
    print(f"DA - ContShadow: miss {delta_m:+.4f}, evals {-delta_e:+.2f}, "
          f"time {-delta_t:+.1f} ns/ref")
    print(f"Average non-stable trace length: {N_AVG:,.0f} references")
    print(f"Direct break-even miss cost: {cm_star_direct:.0f} ns "
          f"({cm_star_direct/1000:.2f} us)")
    print(f"Implied shadow-evaluation cost: {ce_implied/1e6:.2f} ms")
    print(f"Break-even ratio R = c_e/c_m: {R:.0f} "
          f"(one evaluation costs {R:.0f} misses)")
    print(f"Component-model break-even miss cost at implied c_e: "
          f"{cm_star_component/1000:.2f} us")
    # Static S3-FIFO reference: total-time crossover with DA.
    crossover_s3_us = ((da["ns"] - m["S3-FIFO"]["ns"]) /
                       ((m["S3-FIFO"]["miss"] - da["miss"]) * 1000.0))
    print(f"S3-FIFO / DA total-time crossover: {crossover_s3_us:.2f} us "
          f"(S3-FIFO cheaper and lower-miss on the public FIU traces)")

    # Break-even table: for each miss cost, the evaluation cost at which DA wins.
    rows = []
    for cm_us in (0.5, 1.0, 2.0, 5.0, 10.0, 100.0):
        cm = cm_us * 1000.0  # ns
        ce = R * cm          # ns
        rows.append({
            "miss_cost_us": cm_us,
            "break_even_eval_cost_ms": ce / 1e6,
            "DA_wins_if_eval_cost_exceeds_ms": ce / 1e6,
        })
        print(f"  miss cost {cm_us:6.1f} us -> DA wins if one shadow eval "
              f"costs > {ce/1e6:7.2f} ms")

    with open(CSVOUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quantity", "value", "unit"])
        w.writerow(["DA_miss_ratio", f"{da['miss']:.5f}", "ratio"])
        w.writerow(["S3-FIFO_miss_ratio", f"{m['S3-FIFO']['miss']:.5f}", "ratio"])
        w.writerow(["ContShadow_miss_ratio", f"{cs['miss']:.5f}", "ratio"])
        w.writerow(["DA_shadow_evals_per_trace", f"{da['evals']:.3f}", "count"])
        w.writerow(["S3-FIFO_shadow_evals_per_trace", f"{m['S3-FIFO']['evals']:.3f}", "count"])
        w.writerow(["ContShadow_shadow_evals_per_trace", f"{cs['evals']:.3f}", "count"])
        w.writerow(["DA_ns_per_ref", f"{da['ns']:.2f}", "ns/ref"])
        w.writerow(["S3-FIFO_ns_per_ref", f"{m['S3-FIFO']['ns']:.2f}", "ns/ref"])
        w.writerow(["ContShadow_ns_per_ref", f"{cs['ns']:.2f}", "ns/ref"])
        w.writerow(["delta_miss_DA_minus_ContShadow", f"{delta_m:.5f}", "ratio"])
        w.writerow(["delta_evals_ContShadow_minus_DA", f"{delta_e:.3f}", "count"])
        w.writerow(["delta_time_ContShadow_minus_DA", f"{delta_t:.2f}", "ns/ref"])
        w.writerow(["average_nonstable_trace_length", f"{N_AVG:.0f}", "refs"])
        w.writerow(["direct_break_even_miss_cost", f"{cm_star_direct:.1f}", "ns"])
        w.writerow(["implied_shadow_eval_cost", f"{ce_implied:.1f}", "ns"])
        w.writerow(["break_even_ratio_R", f"{R:.2f}", "c_e/c_m"])
        w.writerow(["component_break_even_miss_cost", f"{cm_star_component:.1f}", "ns"])
        w.writerow(["S3_vs_DA_total_time_crossover_us", f"{crossover_s3_us:.2f}", "us"])
        w.writerow([])
        w.writerow(["miss_cost_us", "break_even_eval_cost_ms"])
        for r in rows:
            w.writerow([f"{r['miss_cost_us']:.1f}",
                        f"{r['break_even_eval_cost_ms']:.3f}"])

    # Figure: total time per reference versus miss cost.
    cm_us = [i / 10 for i in range(0, 101)]  # 0..10 us
    t_da = [da["ns"] + da["miss"] * c * 1000 for c in cm_us]
    t_cs = [cs["ns"] + cs["miss"] * c * 1000 for c in cm_us]
    t_s3 = [m["S3-FIFO"]["ns"] + m["S3-FIFO"]["miss"] * c * 1000 for c in cm_us]
    fig, ax = plt.subplots(figsize=(3.4, 2.5), dpi=200)
    ax.plot(cm_us, t_da, label="DA (gated)", color="#1f77b4")
    ax.plot(cm_us, t_cs, label="ContShadow (continuous)", color="#d62728")
    ax.plot(cm_us, t_s3, label="S3-FIFO (static)", color="#2ca02c", ls="--", lw=1.2)
    ax.axvline(cm_star_direct / 1000, color="0.35", ls="--", lw=1)
    ax.annotate(f"break-even\n{cm_star_direct/1000:.2f} $\\mu$s",
                xy=(cm_star_direct / 1000, min(t_da + t_cs)),
                xytext=(cm_star_direct / 1000 + 0.8, min(t_da + t_cs) + 60),
                fontsize=7, color="0.25",
                arrowprops=dict(arrowstyle="->", color="0.35", lw=0.7))
    ax.set_xlabel("miss (page-fault) cost ($\\mu$s)", fontsize=8)
    ax.set_ylabel("total time per reference (ns)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    ax.grid(True, lw=0.3, alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIGOUT)
    print(f"\nWrote {CSVOUT} and {FIGOUT}")


if __name__ == "__main__":
    main()
