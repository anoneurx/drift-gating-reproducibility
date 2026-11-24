#!/usr/bin/env python3
"""Total-time envelope over CLOCK, S3-FIFO, ContShadow and DA.

Reads the frozen seed-5001 non-stable results and computes

    T_policy(c_m) = ns_per_ref_policy + miss_ratio_policy * c_m

for a miss cost c_m in ns.  It writes the paper table (as a LaTeX float), the
pairwise crossing table, an envelope summary, and the paper figure in PDF and
PNG form.  The bootstrap intervals come from bootstrap_total_time.py, which is
run automatically when its CSV is missing.

Run: python3 total_time_envelope.py
"""
import csv
import os
import shutil
import statistics as st
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "main_study_results.csv")
BOOT = os.path.join(HERE, "total_time_bootstrap.csv")
NONSTABLE = {"abrupt", "gradual", "recurring", "composite"}
METHODS = ["CLOCK", "S3-FIFO", "ContShadow", "DA"]
COLORS = {"CLOCK": "#555555", "S3-FIFO": "#009E73",
          "ContShadow": "#0072B2", "DA": "#D55E00"}

# Representative miss costs (us) for the paper table.
ROWS = [
    ("DRAM (illustrative)", 0.1),
    ("CLOCK/S3-FIFO crossing", 0.215539),
    ("Minor-fault calibration (measured)", 2.2),
    ("S3-FIFO/ContShadow crossing", 2.304942),
    ("Remote/RDMA (illustrative low)", 5.0),
    ("Remote/RDMA (illustrative high)", 10.0),
    ("NVMe SSD (illustrative low)", 20.0),
    ("NVMe SSD (illustrative high)", 100.0),
    ("Swap/page fault (illustrative)", 1000.0),
]


def load_means():
    d = defaultdict(lambda: {"ns": [], "m": []})
    for r in csv.DictReader(open(SRC)):
        if r["scenario"] not in NONSTABLE:
            continue
        if r["method"] in METHODS:
            d[r["method"]]["ns"].append(float(r["ns_per_ref"]))
            d[r["method"]]["m"].append(float(r["miss_ratio"]))
    out = {}
    for m in METHODS:
        out[m] = (st.mean(d[m]["ns"]), st.mean(d[m]["m"]), len(d[m]["ns"]))
    return out


def crossing(M, a, b):
    ta, ma = M[a][0], M[a][1]
    tb, mb = M[b][0], M[b][1]
    den = ma - mb
    if abs(den) < 1e-12:
        return float("nan")
    return (tb - ta) / den


def total(M, m, cm_ns):
    return M[m][0] + M[m][1] * cm_ns


def envelope(M):
    """Return the lower-envelope segments and the DA minimum excess."""
    # Sort by slope; the lower envelope of affine functions is the lower
    # convex hull of the lines.  With four lines a direct evaluation at all
    # crossings and interval midpoints is enough.
    cross = []
    for a, b in (("CLOCK", "S3-FIFO"), ("CLOCK", "ContShadow"),
                 ("S3-FIFO", "ContShadow")):
        x = crossing(M, a, b)
        if x == x and x > 0:
            cross.append(x)
    breaks = [0.0] + sorted(set(round(x, 9) for x in cross))
    # Add a large sentinel so the last interval covers all larger costs.
    breaks.append(1e12)
    segs = []
    for lo, hi in zip(breaks[:-1], breaks[1:]):
        mid = 0.5 * (lo + hi) if hi < 1e11 else lo + 1.0
        best = min(("CLOCK", "S3-FIFO", "ContShadow"),
                   key=lambda m: total(M, m, mid))
        if not segs or segs[-1][2] != best:
            segs.append([lo, hi, best])
        else:
            segs[-1][1] = hi
    # Merge consecutive segments of the same policy, then open the last one.
    merged = []
    for lo, hi, p in segs:
        if merged and merged[-1][2] == p:
            merged[-1][1] = hi
        else:
            merged.append([lo, hi, p])
    if merged:
        merged[-1][1] = float("inf")
    # Minimum DA excess at 0 or at a crossing among the non-DA policies.
    pts = [0.0] + [x for x in cross if x > 0]
    gaps = []
    for x in pts:
        da = total(M, "DA", x)
        other = min(total(M, m, x) for m in ("CLOCK", "S3-FIFO", "ContShadow"))
        gaps.append((da - other, x))
    gap, gap_x = min(gaps)
    return merged, gap, gap_x


def read_boot():
    if not os.path.exists(BOOT):
        import bootstrap_total_time
        bootstrap_total_time.main()
    out = {}
    for r in csv.DictReader(open(BOOT)):
        out[r["quantity"]] = (float(r["point"]), float(r["ci95_low"]),
                              float(r["ci95_high"]), int(r["valid_reps"]))
    return out


def fmt_us(x):
    return f"{x/1000:.3f}"


def fmt_cm(x):
    """Exact value up to six decimals, without trailing zeros."""
    return f"{x:.6f}".rstrip("0").rstrip(".")


def write_table(M, env, boot):
    rows = []
    for label, cm_us in ROWS:
        cm = cm_us * 1000.0
        vals = {m: total(M, m, cm) for m in METHODS}
        best_val = min(vals.values())
        best = [m for m in METHODS if vals[m] - best_val < 0.5]
        gap = vals["DA"] - best_val
        rows.append((label, cm_us, vals, best, gap))

    # Panel (b) crossing table.
    cross_rows = [
        ("CLOCK / S3-FIFO", "crossing_clock_s3"),
        ("S3-FIFO / ContShadow", "crossing_s3_cs"),
        ("DA / ContShadow", "crossing_da_cs"),
        ("DA / S3-FIFO", "crossing_da_s3"),
    ]

    lines = []
    lines.append(r"\begin{table*}[t]")
    lines.append(r"\caption{Total time per reference by miss cost, using the measured "
                 r"per-reference times and mean miss ratios of the 80 non-stable test "
                 r"traces. Panel (a): bold marks the lowest total in each row; DA is "
                 r"never the lowest, and the last column gives its excess over the best "
                 r"policy. Panel (b): pairwise crossing miss costs; the DA/S3-FIFO "
                 r"interval is unstable because the miss-ratio difference is small. "
                 r"All values are point estimates; bootstrap intervals are in the text.}")
    lines.append(r"\label{tab:breakeven}")
    lines.append(r"\centering\footnotesize")
    lines.append(r"\setlength{\tabcolsep}{3pt}")
    lines.append(r"\textbf{(a) Total time per reference ($\mu$s)}")
    lines.append(r"\par\vspace{2pt}")
    lines.append(r"\begin{tabular}{@{}lccccccc@{}}")
    lines.append(r"\toprule")
    lines.append(r"Miss-cost scenario & $c_m$ ($\mu$s) & CLOCK & S3-FIFO & "
                 r"ContShadow & DA & Cheapest & DA$-$best (ns) \\")
    lines.append(r"\midrule")
    for label, cm_us, vals, best, gap in rows:
        cells = []
        for m in ("CLOCK", "S3-FIFO", "ContShadow", "DA"):
            s = fmt_us(vals[m])
            if m in best:
                s = r"\textbf{" + s + "}"
            cells.append(s)
        best_s = "/".join(best)
        lines.append(f"{label} & {fmt_cm(cm_us)} & " + " & ".join(cells)
                     + f" & {best_s} & {gap:.1f} \\\\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\par\vspace{4pt}")
    lines.append(r"\textbf{(b) Pairwise crossing miss costs ($\mu$s)}")
    lines.append(r"\par\vspace{2pt}")
    lines.append(r"\begin{tabular}{@{}lcc@{}}")
    lines.append(r"\toprule")
    lines.append(r"Pair & Crossing & 95\% CI \\")
    lines.append(r"\midrule")
    for label, key in cross_rows:
        p, lo, hi, valid = boot[key]
        lines.append(f"{label} & {p:.3f} & [{lo:.3f}, {hi:.3f}] \\\\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\par\smallskip")
    lines.append(r"\footnotesize DA/S3-FIFO interval uses "
                 f"{boot['crossing_da_s3'][3]}/10{{,}}000 positive bootstrap "
                 r"replicates. Minimum DA excess over the best policy: "
                 f"{boot['min_da_gap_ns'][0]:.2f}\\,ns/ref "
                 f"[{boot['min_da_gap_ns'][1]:.1f}, {boot['min_da_gap_ns'][2]:.1f}] "
                 f"at $c_m\\approx{boot['min_da_gap_cm_us'][0]:.2f}\\,\\mu$s; "
                 r"the interval includes zero, so the crossing is not "
                 r"statistically resolved.")
    lines.append(r"\end{table*}")
    tex = "\n".join(lines) + "\n"
    with open(os.path.join(HERE, "total_time_table.tex"), "w") as f:
        f.write(tex)
    # Copy the table into both paper trees so \input can use a local path.
    for dest in ("../../drift_gating_latex_source/total_time_table.tex",
                 "../../latex/total_time_table.tex"):
        shutil.copyfile(os.path.join(HERE, "total_time_table.tex"),
                        os.path.join(HERE, dest))

    # Machine-readable table.
    with open(os.path.join(HERE, "total_time_table.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "cm_us", "CLOCK_ns", "S3-FIFO_ns",
                    "ContShadow_ns", "DA_ns", "cheapest", "DA_minus_best_ns"])
        for label, cm_us, vals, best, gap in rows:
            w.writerow([label, fmt_cm(cm_us),
                        f"{vals['CLOCK']:.3f}", f"{vals['S3-FIFO']:.3f}",
                        f"{vals['ContShadow']:.3f}", f"{vals['DA']:.3f}",
                        "/".join(best), f"{gap:.3f}"])

    return rows


def write_summary(M, env, gap, gap_x, boot):
    with open(os.path.join(HERE, "pairwise_crossings.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pair", "crossing_us", "ci95_low_us", "ci95_high_us",
                    "valid_reps"])
        for label, key in (("CLOCK/S3-FIFO", "crossing_clock_s3"),
                           ("S3-FIFO/ContShadow", "crossing_s3_cs"),
                           ("DA/ContShadow", "crossing_da_cs"),
                           ("DA/S3-FIFO", "crossing_da_s3"),
                           ("CLOCK/ContShadow", "crossing_clock_cs"),
                           ("CLOCK/DA", "crossing_clock_da")):
            p, lo, hi, valid = boot[key]
            w.writerow([label, f"{p:.6f}", f"{lo:.6f}", f"{hi:.6f}", valid])
    with open(os.path.join(HERE, "envelope_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quantity", "value", "unit"])
        for lo, hi, p in env:
            w.writerow([f"lower_envelope_{p}_start", f"{lo/1000:.6f}", "us"])
            w.writerow([f"lower_envelope_{p}_end",
                        "inf" if hi > 1e8 else f"{hi/1000:.6f}", "us"])
        w.writerow(["da_min_excess", f"{gap:.6f}", "ns"])
        w.writerow(["da_min_excess_at", f"{gap_x/1000:.6f}", "us"])
        w.writerow(["da_on_lower_envelope", "false", "bool"])


def plot(M, env, gap, gap_x):
    cm_us = [i / 200.0 for i in range(0, 1201)]  # 0..6 us
    fig, ax = plt.subplots(figsize=(3.45, 2.95))
    # Lower envelope first, so the policy curves stay visible on top.
    env_y = [min(total(M, m, c * 1000.0)
                 for m in ("CLOCK", "S3-FIFO", "ContShadow"))
             for c in cm_us]
    ax.plot(cm_us, env_y, color="black", lw=1.8, ls=(0, (4, 2)),
            alpha=0.85, label="lower envelope", zorder=1)
    for m in ("CLOCK", "S3-FIFO", "ContShadow", "DA"):
        ys = [total(M, m, c * 1000.0) for c in cm_us]
        ax.plot(cm_us, ys, color=COLORS[m], lw=1.25, zorder=3,
                label={"CLOCK": "CLOCK", "S3-FIFO": "S3-FIFO",
                       "ContShadow": "ContShadow", "DA": "DA (gated)"}[m])
    ax.axvspan(1.98, 2.06, color="#E69F00", alpha=0.35, lw=0,
               label="measured minor fault", zorder=0)
    for x, lab in ((0.215539, "0.216"), (2.304942, "2.305")):
        ax.axvline(x, color="0.35", lw=0.7, ls=":")
        ax.text(x + 0.06, 300, lab, fontsize=6.0, color="0.25",
                rotation=90, va="bottom")
    ax.set_xlim(0, 6)
    ymax = max(total(M, m, 6000) for m in METHODS)
    ax.set_ylim(0, ymax * 1.06)
    ax.set_xlabel("Miss cost $c_m$ ($\\mu$s)")
    ax.set_ylabel("Total time per reference (ns)")
    ax.grid(lw=0.3, alpha=0.45)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(loc="upper left", frameon=False, fontsize=6.0,
              handlelength=1.4, borderaxespad=0.3)

    # Inset: the CLOCK/S3-FIFO crossing.
    ins = ax.inset_axes([0.57, 0.12, 0.38, 0.28])
    xs = [i / 10000.0 for i in range(0, 3501)]
    for m in ("CLOCK", "S3-FIFO", "DA"):
        ins.plot(xs, [total(M, m, x * 1000.0) for x in xs],
                 color=COLORS[m], lw=0.9)
    ins.axvline(0.215539, color="0.35", lw=0.5, ls=":")
    ins.set_xlim(0, 0.35)
    ins.set_xticks([0, 0.2, 0.35])
    ins.set_yticks([0, 100, 200])
    ins.tick_params(labelsize=5.0, length=2, pad=1)
    ins.set_title("zoom: CLOCK/S3", fontsize=5.2, pad=1.5)
    ins.grid(lw=0.2, alpha=0.4)

    fig.tight_layout(pad=0.2)
    pdf = os.path.join(HERE, "fig_breakeven.pdf")
    png = os.path.join(HERE, "fig8_breakeven.png")
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    shutil.copyfile(pdf, os.path.join(HERE, "../../drift_gating_latex_source/figs/fig_breakeven.pdf"))
    shutil.copyfile(png, os.path.join(HERE, "../../latex/figs/fig8_breakeven.png"))
    shutil.copyfile(png, os.path.join(HERE, "../fig8_breakeven.png"))


def main():
    M = load_means()
    print("means (ns/ref, miss):")
    for m in METHODS:
        print(f"  {m:12s} {M[m][0]:8.2f}  {M[m][1]:.5f}  n={M[m][2]}")
    env, gap, gap_x = envelope(M)
    print("lower envelope:")
    for lo, hi, p in env:
        print(f"  {p:10s} {lo/1000:8.4f} .. {hi/1000:8.4f} us")
    print(f"DA minimum excess: {gap:.3f} ns at {gap_x/1000:.4f} us")
    boot = read_boot()
    write_table(M, env, boot)
    write_summary(M, env, gap, gap_x, boot)
    plot(M, env, gap, gap_x)
    print("Wrote total_time_table.{csv,tex}, pairwise_crossings.csv, "
          "envelope_summary.csv, fig_breakeven.pdf, fig8_breakeven.png")


if __name__ == "__main__":
    main()
