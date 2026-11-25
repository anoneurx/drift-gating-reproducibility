#!/usr/bin/env python3
"""Generate LaTeX fragments for Phases 6-8 directly from measured CSVs."""
import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
P6 = os.path.join(HERE, "phase6_pdl")
P7 = os.path.join(HERE, "phase7_async")
P8 = os.path.join(HERE, "phase8_kernel")
OUTDIRS = [
    os.path.join(ROOT, "drift_gating_latex_source"),
    os.path.join(ROOT, "latex"),
]


def rows(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def write_all(name, body):
    for d in OUTDIRS:
        with open(os.path.join(d, name), "w") as fh:
            fh.write(body)


def begin_table(caption, label, tabular, columns):
    return [r"\begin{table}[t]", r"\caption{" + caption + "}", r"\label{" + label + "}",
            r"\centering\footnotesize", r"\begin{tabular}{@{}" + tabular + r"@{}}", r"\toprule",
            columns, r"\midrule"]


def end_table():
    return [r"\bottomrule", r"\end{tabular}", r"\end{table}"]


def phase6():
    s = rows(os.path.join(P6, "summary.csv"))
    all_lines = begin_table(
        "Phase 6: means over 18 PDL family$\\times$capacity points (1M-reference prefixes)",
        "tab:pdl_all", "lcccc",
        r"Method & Mean miss & Switches/trace & Shadow evals/trace & ns/ref \\")
    for r in s:
        all_lines.append(f"{r['method']} & {float(r['mean_miss']):.4f} & {float(r['mean_switches']):.2f} & "
                         f"{float(r['mean_shadow_evals']):.2f} & {float(r['mean_ns_per_ref']):.1f} \\\\")
    all_lines += end_table()
    write_all("phase6_pdl_table.tex", "\n".join(all_lines) + "\n")

    keep = ["CLOCK", "LRU", "S3-FIFO", "DA", "ContShadow"]
    by = {r["method"]: r for r in s}
    main_lines = begin_table(
        "Phase 6: selected methods across six CMU PDL families (18 points)",
        "tab:pdl_main", "lccc",
        r"Method & Mean miss & Shadow evals/trace & ns/ref \\")
    for m in keep:
        r = by[m]
        main_lines.append(f"{m} & {float(r['mean_miss']):.4f} & {float(r['mean_shadow_evals']):.2f} & "
                          f"{float(r['mean_ns_per_ref']):.1f} \\\\")
    main_lines += end_table()
    write_all("phase6_pdl_main_table.tex", "\n".join(main_lines) + "\n")


def phase7():
    p = rows(os.path.join(P7, "paired.csv"))
    s = {r["repetition"]: r for r in rows(os.path.join(P7, "summary.csv"))}
    lines = begin_table(
        "Phase 7: real asynchronous-shadow prototype, 80 non-stable traces per repetition",
        "tab:async_main", "lccc",
        r"Rep. & Mean miss & DA$-\!$sync [95\% CI] & Win/Tie/Loss \\")
    for r in p:
        rep = r["repetition"]
        diff = float(r["mean_async_minus_sync"])
        lo = float(r["ci_low"])
        hi = float(r["ci_high"])
        lines.append(f"{rep} & {float(s[rep]['mean_miss']):.4f} & "
                     f"${diff:+.4f}$ [${lo:+.4f}$,${hi:+.4f}$] & "
                     f"{r['n_negative']}/{r['n_zero']}/{r['n_positive']} \\\\")
    lines += end_table()
    write_all("phase7_async_main_table.tex", "\n".join(lines) + "\n")


def phase8():
    if not os.path.exists(os.path.join(P8, "kernel_summary.csv")) or not os.path.exists(os.path.join(P8, "ftrace_summary.csv")):
        print("phase8 tables not generated: guest-kernel CSVs do not exist yet")
        return
    k = rows(os.path.join(P8, "kernel_summary.csv"))
    fd = rows(os.path.join(P8, "ftrace_summary.csv"))
    counts = defaultdict(int)
    for r in fd:
        counts[r["function"]] += int(r["n"])
    if not counts:
        raise SystemExit("no ftrace durations measured; refusing to emit a placeholder table")
    fn = max(counts, key=counts.get)
    fby = {(r["condition"], int(r["rep"]), r["function"]): r for r in fd}
    lines = begin_table(
        f"Phase 8: real guest-kernel observations; ftrace row is {fn.replace('_', r'\_')}",
        "tab:kernel_main", "lcccc",
        r"Condition & Minor faults & Refaults & Toggles & Median/p95 fault ns \\")
    lines.insert(4, r"\setlength{\tabcolsep}{2pt}")
    for r in k:
        f = fby.get((r["condition"], int(r["rep"]), fn))
        dur = "--" if not f else f"${float(f['median_ns']):.1f}/{float(f['p95_ns']):.1f}$"
        lines.append(f"{r['condition'].replace('_', r'\_')} & {int(float(r['minflt'])):,} & {r['refault_delta']} & {r['toggles']} & {dur} \\\\")
    lines += end_table()
    write_all("phase8_kernel_main_table.tex", "\n".join(lines) + "\n")

    full = begin_table(
        "Phase 8: per-function ftrace durations from the guest kernel (all conditions)",
        "tab:kernel_ftrace", "lccccc",
        r"Condition & Rep. & Function & Samples & Median ns & p95 ns \\")
    full.insert(4, r"\setlength{\tabcolsep}{2pt}")
    for r in fd:
        full.append(f"{r['condition'].replace('_', r'\_')} & {r['rep']} & {r['function'].replace('_', r'\_')} & {r['n']} & "
                    f"{float(r['median_ns']):.1f} & {float(r['p95_ns']):.1f} \\\\")
    full += end_table()
    write_all("phase8_kernel_ftrace_table.tex", "\n".join(full) + "\n")


def main():
    phase6()
    phase7()
    phase8()
    print("generated phase tables in both paper trees")


if __name__ == "__main__":
    main()
