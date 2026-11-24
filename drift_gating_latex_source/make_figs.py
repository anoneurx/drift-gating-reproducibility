import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams.update({
    "font.family": "Liberation Serif",
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 7,
    "axes.linewidth": 0.6,
    "pdf.fonttype": 42,
})
BLUE, ORANGE, GREEN, RED, SKY, PURPLE, GRAY = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7", "#8c8c8c"
OUT = "figs/"

# ---------------------------------------------------------------- Fig: workflow
def box(ax, x, y, w, h, text, fc, ec="#333333", fs=7):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                       fc=fc, ec=ec, lw=0.7)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.15)

def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=8,
                                 lw=0.7, color="#333333"))

fig, ax = plt.subplots(figsize=(3.45, 4.35))
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
steps = [
    ("Trace generation (seeded)\n5 primitives, 5 kernel models", "#eeeeee"),
    ("Training (seed 100)\n15 stable + 32 non-stable traces\n48-configuration sweep", "#cfe3f3"),
    ("Frozen configuration A0\nlowest training miss ratio,\n0 stable-trace false confirmations", "#cfe3f3"),
    ("Round 1 test (110 traces, seeds 1001+)\nDA worse than S3-FIFO and LPR-style", "#f9dcb4"),
    ("Amendment A1\nrecency-filtered migration;\nvalidated on training traces only", "#cfe3f3"),
    ("Round 2 held-out test\n110 fresh traces (seed 5001)\nevaluated once, no re-tuning", "#f9dcb4"),
    ("Analysis: Wilcoxon + Holm, bootstrap CIs,\nablation, sensitivity, cost model", "#eeeeee"),
]
n = len(steps); h = 0.098; gap = (1 - n * h) / (n - 1)
ys = [1 - (i + 1) * h - i * gap for i in range(n)]
for (t, c), y in zip(steps, ys):
    box(ax, 0.06, y, 0.88, h, t, c)
for i in range(n - 1):
    arrow(ax, 0.5, ys[i] - 0.004, 0.5, ys[i + 1] + h + 0.004)
ax.text(0.5, -0.02, "blue = training stages, orange = test rounds", ha="center", fontsize=6.5, color="#444444")
fig.savefig(OUT + "fig_workflow.pdf", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- Fig: architecture
fig, ax = plt.subplots(figsize=(7.1, 2.6))
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
ax.text(0.01, 0.985, "Per-reference fast path", fontsize=7.5, weight="bold", va="top", color=BLUE)
ax.text(0.13, 0.54, "Per-epoch control path (every W = 2,000 references)", fontsize=7.5, weight="bold", va="top", color=RED)
box(ax, 0.01, 0.74, 0.14, 0.17, "Page reference", "#cfe3f3")
box(ax, 0.20, 0.74, 0.20, 0.17, "Active policy\n(LRU / LFU-A / 2Q /\nMRU / S3-FIFO)", "#cfe3f3")
box(ax, 0.45, 0.74, 0.22, 0.17, "On miss: evict;\nupdate last-access\nand aged count", "#cfe3f3")
box(ax, 0.72, 0.74, 0.26, 0.17, "Hash sample (p = 0.2):\nreuse-time and window buffers", "#fdf0c8")
arrow(ax, 0.15, 0.825, 0.20, 0.825); arrow(ax, 0.40, 0.825, 0.45, 0.825); arrow(ax, 0.67, 0.825, 0.72, 0.825)
# sampled buffers feed the control path
ax.plot([0.85, 0.85], [0.74, 0.62], color="#333333", lw=0.7)
ax.plot([0.85, 0.105], [0.62, 0.62], color="#333333", lw=0.7)
arrow(ax, 0.105, 0.62, 0.105, 0.43)
box(ax, 0.01, 0.20, 0.19, 0.23, "Stage 1: CUSUM on\nepoch miss ratio\n(h = 5, $\\delta$ = 0.5)", "#fdf0c8")
box(ax, 0.25, 0.20, 0.19, 0.23, "Stage 2: KS test on\nsampled reuse times\n($\\alpha$ = $10^{-3}$)", "#fdf0c8")
box(ax, 0.49, 0.20, 0.19, 0.23, "Sampled shadow\nevaluation of five\ncandidates (Cs = 200)", "#d8efe6")
box(ax, 0.73, 0.20, 0.25, 0.23, "Switch rule: LCB margin > K,\ndwell and hysteresis guards", "#d8efe6")
arrow(ax, 0.20, 0.315, 0.25, 0.315); arrow(ax, 0.44, 0.315, 0.49, 0.315); arrow(ax, 0.68, 0.315, 0.73, 0.315)
box(ax, 0.25, 0.0, 0.73, 0.12, "Policy switch: rebuild metadata from resident pages, dropping pages unreferenced in the last\n20,000 references; the new policy then serves the fast path", "#f5d0cc")
arrow(ax, 0.855, 0.20, 0.855, 0.125)
fig.savefig(OUT + "fig_architecture.pdf", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- Fig: overall miss ratio
names = ["OPT", "ContShadow", "DA", "S3-FIFO", "2Q", "ARC", "LFU-A", "LeCaR", "LPR-style", "CLOCK", "LRU", "FIFO", "MRU"]
mean = [0.302, 0.423, 0.453, 0.468, 0.522, 0.529, 0.546, 0.551, 0.533, 0.559, 0.570, 0.600, 0.935]
lo = [0.281, 0.400, 0.423, 0.435, 0.493, 0.499, 0.515, 0.520, 0.509, 0.530, 0.540, 0.573, 0.918]
hi = [0.324, 0.446, 0.484, 0.501, 0.551, 0.557, 0.576, 0.582, 0.556, 0.589, 0.598, 0.627, 0.949]
order = np.argsort(mean)
names = [names[i] for i in order]; mean = np.array(mean)[order]; lo = np.array(lo)[order]; hi = np.array(hi)[order]
cols = []
for nme in names:
    cols.append(RED if nme == "DA" else BLUE if nme == "ContShadow" else GREEN if nme == "S3-FIFO" else "#222222" if nme == "OPT" else "#b5b5b5")
fig, ax = plt.subplots(figsize=(3.45, 2.9))
y = np.arange(len(names))[::-1]
ax.barh(y, mean, color=cols, height=0.66, edgecolor="none")
ax.errorbar(mean, y, xerr=[mean - lo, hi - mean], fmt="none", ecolor="black", elinewidth=0.7, capsize=1.6)
ax.set_yticks(y); ax.set_yticklabels(names)
ax.set_xlim(0, 1.0); ax.set_xlabel("Mean miss ratio, 80 non-stable traces (95% bootstrap CI)")
ax.grid(axis="x", lw=0.3, alpha=0.5); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
for yi, m in zip(y, mean):
    ax.text(min(m + 0.075, 0.985) if m < 0.9 else m - 0.17, yi, f"{m:.3f}", va="center", fontsize=6.5,
            color="black" if m < 0.9 else "white")
fig.savefig(OUT + "fig_overall.pdf", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- Fig: scenario + paired differences (two panels)
fig, (a, b) = plt.subplots(1, 2, figsize=(7.1, 2.7), gridspec_kw={"width_ratios": [1.15, 1]})
scen = ["Abrupt", "Gradual", "Recurring", "Composite"]
data = {
    "LRU": [0.500, 0.572, 0.527, 0.682],
    "2Q": [0.457, 0.504, 0.479, 0.648],
    "S3-FIFO": [0.406, 0.441, 0.412, 0.615],
    "LPR-style": [0.477, 0.535, 0.474, 0.646],
    "DA": [0.370, 0.439, 0.398, 0.604],
    "ContShadow": [0.365, 0.401, 0.384, 0.541],
}
colors = {"LRU": "#d0d0d0", "2Q": "#a8a8a8", "S3-FIFO": GREEN, "LPR-style": "#7a7a7a", "DA": RED, "ContShadow": BLUE}
hatch = {"LRU": "", "2Q": "", "S3-FIFO": "//", "LPR-style": "", "DA": "", "ContShadow": "\\\\"}
opt = [0.244, 0.269, 0.242, 0.452]
w = 0.125; x = np.arange(4)
for i, (k, v) in enumerate(data.items()):
    a.bar(x + (i - 2.5) * w, v, w, color=colors[k], hatch=hatch[k], edgecolor="white" if hatch[k] else "none", lw=0.0, label=k)
for xi, o in zip(x, opt):
    a.hlines(o, xi - 0.42, xi + 0.42, color="black", lw=1.0, linestyle=":")
a.plot([], [], color="black", lw=1.0, linestyle=":", label="OPT")
a.set_xticks(x); a.set_xticklabels(scen); a.set_ylabel("Mean miss ratio"); a.set_ylim(0, 0.78)
a.legend(ncol=4, loc="upper left", frameon=False, columnspacing=0.8, handlelength=1.2)
a.grid(axis="y", lw=0.3, alpha=0.5); a.set_axisbelow(True)
a.set_title("(a) Miss ratio by scenario", loc="left", fontsize=8)
for s in ("top", "right"): a.spines[s].set_visible(False)

base = ["LRU", "FIFO", "CLOCK", "LFU-A", "2Q", "ARC", "S3-FIFO", "LeCaR", "LPR-style", "ContShadow"]
diff = [-0.1171, -0.1472, -0.1065, -0.0933, -0.0691, -0.0758, -0.0154, -0.0980, -0.0800, 0.0301]
dlo = [-0.140, -0.171, -0.130, -0.116, -0.090, -0.099, -0.035, -0.121, -0.098, 0.016]
dhi = [-0.094, -0.124, -0.084, -0.071, -0.048, -0.053, 0.004, -0.076, -0.061, 0.045]
idx = np.argsort(diff)
yy = np.arange(len(base))[::-1]
for yi, j in zip(yy, idx):
    c = GREEN if base[j] == "S3-FIFO" else BLUE if base[j] == "ContShadow" else "#444444"
    b.errorbar(diff[j], yi, xerr=[[diff[j] - dlo[j]], [dhi[j] - diff[j]]], fmt="o", color=c, ms=3.5, elinewidth=0.9, capsize=1.8)
b.axvline(0, color="black", lw=0.7)
b.set_yticks(yy); b.set_yticklabels([base[j] for j in idx])
b.set_xlabel("DA minus baseline, mean paired miss-ratio difference")
b.text(-0.17, -1.35, "\u2190 favors DA", fontsize=6.5, color="#444444"); b.text(0.018, -1.35, "favors baseline \u2192", fontsize=6.5, color="#444444")
b.set_ylim(-1.7, len(base) - 0.4)
b.grid(axis="x", lw=0.3, alpha=0.5); b.set_axisbelow(True)
b.set_title("(b) Paired differences (95% CI)", loc="left", fontsize=8)
for s in ("top", "right"): b.spines[s].set_visible(False)
fig.tight_layout(w_pad=1.5)
fig.savefig(OUT + "fig_scenario_paired.pdf", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- Fig: cost vs accuracy
pts = {"CLOCK": (8.9, 0.559), "LRU": (25.1, 0.570), "S3-FIFO": (28.5, 0.468), "2Q": (36.8, 0.522),
       "LPR-style": (50.2, 0.533), "DA": (67.4, 0.453), "ContShadow": (133.4, 0.423)}
fig, ax = plt.subplots(figsize=(3.45, 2.5))
for k, (xv, yv) in pts.items():
    c = RED if k == "DA" else BLUE if k == "ContShadow" else GREEN if k == "S3-FIFO" else "#555555"
    m = "s" if k in ("DA", "ContShadow", "S3-FIFO") else "o"
    ax.scatter(xv, yv, color=c, s=26, marker=m, zorder=3)
    dx, dy, ha = (4, 0.004, "left")
    if k == "CLOCK": dx, dy = 3, 0.0
    if k == "LRU": dx, dy = 3, 0.004
    if k == "S3-FIFO": dx, dy = 3, -0.012
    if k == "ContShadow": dx, dy, ha = (-3, 0.012, "right")
    ax.text(xv + dx, yv + dy, k, fontsize=7, ha=ha, va="center")
ax.set_xlabel("Simulated time per reference (ns)"); ax.set_ylabel("Mean miss ratio (non-stable)")
ax.set_xlim(0, 150); ax.set_ylim(0.40, 0.60)
ax.grid(lw=0.3, alpha=0.5); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.savefig(OUT + "fig_tradeoff.pdf", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- Fig: break-even
cm = np.linspace(0, 6, 200)  # microseconds
dm = 0.4529 - 0.4228
simple = -66.0 + dm * 1000 * cm          # DA - ContShadow, ns per reference, simulator timings
direct = -94.43 + dm * 1000 * cm         # using directly measured 2.46 ms per evaluation
fig, ax = plt.subplots(figsize=(3.45, 2.75))
ax.axhline(0, color="black", lw=0.7)
ax.axvspan(1.98, 2.06, color=ORANGE, alpha=0.55, lw=0, label="measured minor fault (1.98\u20132.06 \u00b5s)")
ax.axvspan(1.44, 4.06, ymin=0.0, ymax=0.045, color=GRAY, alpha=0.8, lw=0)
ax.text(4.1, -86, "95% CI of break-even\n(1.44\u20134.06 \u00b5s)", fontsize=6.3, va="center", color="#444444")
ax.plot(cm, simple, color=BLUE, lw=1.4, label="simulator timings (break-even 2.2 \u00b5s)")
ax.plot(cm, direct, color=RED, lw=1.4, linestyle="--", label="measured 2.46 ms/evaluation (3.1 \u00b5s)")
ax.set_xlim(0, 6); ax.set_ylim(-100, 100)
ax.set_xlabel("Miss cost $c_m$ (\u00b5s)"); ax.set_ylabel("DA minus ContShadow,\ntotal time per reference (ns)")
ax.text(3.3, -55, "DA (gated) cheaper", fontsize=7, color="#333333"); ax.text(0.12, 22, "ContShadow (continuous)\ncheaper", fontsize=7, color="#333333")
ax.legend(loc="upper left", frameon=False, fontsize=6.3, bbox_to_anchor=(0.0, 1.0))
ax.grid(lw=0.3, alpha=0.5); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.savefig(OUT + "fig_breakeven.pdf", bbox_inches="tight")
plt.close(fig)
print("figures ok")
