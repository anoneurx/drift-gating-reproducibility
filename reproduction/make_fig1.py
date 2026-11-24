#!/usr/bin/env python3
"""Regenerate Fig. 1 as a clean controller diagram.

The previous figure carried a 'future work: real traces' annotation that
contradicted the appendix. The diagram below contains only the components of
the evaluated controller; the generated-trace main study and the exploratory
real-program appendix are described in the paper text and Fig. 2.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(4.3, 6.3))
ax.set_xlim(0, 10); ax.set_ylim(0, 14.6); ax.axis("off")

FAST = "#dbeafe"; CTRL = "#fef3c7"; DEC = "#dcfce7"; WARN = "#fee2e2"
edge = "#334155"


def box(x, y, w, h, text, fc, fs=8.4):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                       linewidth=1.0, edgecolor=edge, facecolor=fc)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color="#111827", linespacing=1.25)
    return (x, y, w, h)


def arrow(a, b, label="", dx=0.0, dy=0.0):
    ax.add_patch(FancyArrowPatch((a[0] + a[2] / 2, a[1]), (b[0] + b[2] / 2, b[1] + b[3]),
                                 arrowstyle="-|>", mutation_scale=10,
                                 linewidth=0.9, color=edge))
    if label:
        ax.text((a[0] + b[0]) / 2 + dx, (a[1] + b[1] + b[3]) / 2 + dy, label,
                fontsize=7.0, color="#475569", ha="center")


ax.text(5, 14.25, "Drift-aware controller", ha="center", va="center",
        fontsize=11, fontweight="bold")
ax.text(5, 13.75, "per-reference fast path  /  per-epoch control path",
        ha="center", fontsize=7.6, color="#64748b")

ref = box(3.4, 12.65, 3.2, 0.6, "page reference", FAST)
pol = box(3.0, 11.35, 4.0, 0.8, "active policy (LRU / LFU-A / 2Q / MRU)\nhit or miss", FAST)
arrow(ref, pol)
miss = box(0.5, 10.0, 3.9, 0.85, "eviction on miss\nupdate last-access + aged count", FAST)
samp = box(6.0, 10.0, 3.6, 0.85, "hash sample (p = 0.2)\nreuse-time + window buffers", CTRL)
arrow(pol, miss); arrow(pol, samp)

mon = box(5.8, 8.35, 4.0, 0.85, "Stage 1: CUSUM on\nepoch miss ratio", CTRL)
ks = box(5.8, 6.75, 4.0, 0.95, "Stage 2: KS confirmation\non sampled reuse times", CTRL)
arrow(samp, mon); arrow(mon, ks)

shad = box(1.7, 6.75, 3.4, 0.95, "sampled shadow\nsimulation of candidates", DEC)
arrow(ks, shad, "confirmed")
sw = box(1.7, 4.9, 3.4, 0.95, "cost-margin / LCB rule\ndwell guard", DEC)
arrow(shad, sw)

mig = box(0.7, 3.1, 5.4, 1.0, "policy switch: recency-filtered state migration\n(discard pages unreferenced since confirmation)", WARN)
arrow(sw, mig)
fb = box(0.7, 1.55, 5.4, 0.75, "new active policy  ->  fast path", FAST)
arrow(mig, fb)
ax.add_patch(FancyArrowPatch((0.95, 1.9), (2.6, 11.35), connectionstyle="arc3,rad=-0.55",
                             arrowstyle="-|>", mutation_scale=10, linewidth=0.9,
                             color=edge, linestyle="--"))
ax.text(0.25, 7.1, "feedback", fontsize=7.0, color="#475569", rotation=90, va="center")

ax.text(5, 0.75, "KS stage gave no measurable benefit in the ablation;\n"
                 "the effective gate is CUSUM plus a cost margin.",
        ha="center", va="center", fontsize=7.2, color="#64748b", linespacing=1.3)

fig.tight_layout(pad=0.4)
out = "/home/kashie/Sem 5/research/latex/figs/fig1_arch.png"
fig.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
print("wrote", out)
