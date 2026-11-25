#!/usr/bin/env python3
"""Regenerate the Section V figures from the reproducible main-study CSVs."""
import csv, math, os, random
from collections import defaultdict
from statistics import mean
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

random.seed(7)
OUT = os.path.join(os.path.dirname(__file__), "..", "latex", "figs")
NONSTABLE = ["abrupt", "gradual", "recurring", "composite"]
ORDER = ["LRU", "FIFO", "CLOCK", "LFU-A", "2Q", "ARC", "S3-FIFO", "LeCaR",
         "LPR-style", "ContShadow", "DA", "OPT"]
ABL = ["DA", "DA-noPurge", "DA-noS2", "DA-noShadow", "DA-noCost", "DA-noDwell", "S3-FIFO", "ContShadow"]


def load(name):
    with open(os.path.join(os.path.dirname(__file__), name)) as f:
        return list(csv.DictReader(f))


def ns(rows):
    return [r for r in rows if r["scenario"] in NONSTABLE]


def bym(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["method"]].append(r)
    return d


def ci(xs, n=5000):
    bs = sorted(mean(random.choices(xs, k=len(xs))) for _ in range(n))
    return bs[125], bs[4874]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name), dpi=150)
    plt.close(fig)
    print("wrote", name)


def main():
    rows = ns(load("main_study_results.csv"))
    d = bym(rows)

    # Fig 3: overall miss ratio
    vals = [mean(float(r["miss_ratio"]) for r in d[m]) for m in ORDER]
    errs = []
    for m in ORDER:
        xs = [float(r["miss_ratio"]) for r in d[m]]
        lo, hi = ci(xs)
        mu = mean(xs)
        errs.append([mu - lo, hi - mu])
    fig, ax = plt.subplots(figsize=(7, 3.2))
    lo_err = [e[0] for e in errs]
    hi_err = [e[1] for e in errs]
    ax.bar(range(len(ORDER)), vals, yerr=[lo_err, hi_err],
           color=["#999"] * (len(ORDER) - 2) + ["#c60", "#c00"], capsize=2)
    ax.set_xticks(range(len(ORDER)), ORDER, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("Mean miss ratio")
    ax.set_title("Non-stable traces (reproducible main study)")
    save(fig, "fig3_overall.png")

    # Fig 4: by scenario
    scen = ["abrupt", "gradual", "recurring", "composite"]
    sel = ["LRU", "2Q", "S3-FIFO", "LPR-style", "ContShadow", "DA"]
    x = range(len(scen)); w = 0.13
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for i, m in enumerate(sel):
        v = [mean(float(r["miss_ratio"]) for r in d[m] if r["scenario"] == s) for s in scen]
        ax.bar([k + (i - 2.5) * w for k in x], v, w, label=m)
    ax.set_xticks(list(x), scen, fontsize=8)
    ax.set_ylabel("Mean miss ratio"); ax.legend(fontsize=6, ncol=3)
    save(fig, "fig4_scenario.png")

    # Fig 5: paired differences
    base = ["LRU", "FIFO", "CLOCK", "LFU-A", "2Q", "ARC", "S3-FIFO", "LeCaR", "LPR-style", "ContShadow"]
    da = {r["seed"]: float(r["miss_ratio"]) for r in d["DA"]}
    diffs = []
    for m in base:
        o = {r["seed"]: float(r["miss_ratio"]) for r in d[m]}
        diffs.append(mean(da[s] - o[s] for s in da if s in o))
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.barh(base, diffs, color=["#2a7" if v < 0 else "#c44" for v in diffs])
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("DA minus baseline (negative favours DA)")
    save(fig, "fig5_paired.png")

    # Fig 6: ablation
    miss = [mean(float(r["miss_ratio"]) for r in d[m]) for m in ABL]
    ev = [mean(float(r["shadow_evals"]) for r in d[m]) for m in ABL]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.bar(range(len(ABL)), miss, color="#48a")
    ax.set_xticks(range(len(ABL)), ABL, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("Mean miss ratio")
    ax2 = ax.twinx(); ax2.plot(range(len(ABL)), ev, "o-", color="#c60")
    ax2.set_ylabel("Shadow evals/trace", color="#c60")
    save(fig, "fig6_ablation.png")

    # Fig 7: cost vs miss
    fig, ax = plt.subplots(figsize=(6, 4))
    for m in ["LRU", "2Q", "S3-FIFO", "LPR-style", "ContShadow", "DA"]:
        r = d[m]
        ax.scatter(mean(float(x["ns_per_ref"]) for x in r), mean(float(x["miss_ratio"]) for x in r), s=40)
        ax.annotate(m, (mean(float(x["ns_per_ref"]) for x in r), mean(float(x["miss_ratio"]) for x in r)),
                    fontsize=7, xytext=(4, 3), textcoords="offset points")
    ax.set_xlabel("Simulated ns/reference"); ax.set_ylabel("Mean miss ratio")
    save(fig, "fig7_cost.png")

    # Fig 8: sampling rate
    rates = [("0.05", "main_study_p005.csv"), ("0.1", "main_study_p01.csv"), ("0.2", "main_study_results.csv")]
    xs, ys = [], []
    for lab, f in rates:
        try:
            r = bym(ns(load(f)))["DA"]
            xs.append(lab); ys.append(mean(float(v["miss_ratio"]) for v in r))
        except FileNotFoundError:
            pass
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.plot(xs, ys, "o-"); ax.set_xlabel("Sampling rate p"); ax.set_ylabel("DA mean miss ratio")
    save(fig, "fig8_sensitivity.png")

    # Fig 9: capacity
    caps = [("500", "main_study_C500.csv"), ("1000", "main_study_results.csv"), ("2000", "main_study_C2000.csv")]
    fig, ax = plt.subplots(figsize=(5, 3))
    for m, style in [("LRU", "o-"), ("S3-FIFO", "s-"), ("DA", "^-"), ("ContShadow", "d-")]:
        ys = []
        for lab, f in caps:
            try:
                r = bym(ns(load(f)))[m]
                ys.append(mean(float(v["miss_ratio"]) for v in r))
            except (FileNotFoundError, KeyError):
                ys.append(float("nan"))
        ax.plot([c for c, _ in caps], ys, style, label=m)
    ax.set_xlabel("Capacity C"); ax.set_ylabel("Mean miss ratio"); ax.legend(fontsize=7)
    save(fig, "fig9_capacity.png")


if __name__ == "__main__":
    main()
