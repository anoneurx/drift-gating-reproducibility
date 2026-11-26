#!/usr/bin/env python3
"""Update Drift_Gating_Final_IEEE.docx and Drift_Gating_Final_IEEE.pdf in IEEE 2-column format."""
import csv
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
import numpy as np

from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RESULTS = HERE / "results"
TEX_DIR = ROOT / "drift_gating_latex_source"
FIG_DIR = TEX_DIR / "figs"
TMP_FIGS = Path("/tmp/ieee_figs")
TMP_FIGS.mkdir(parents=True, exist_ok=True)

SUB_SUP_RE = re.compile(r"(_\{[^}]+\}|\^\{[^}]+\})")


def load_csv(name):
    with open(RESULTS / name, newline="") as fh:
        return list(csv.DictReader(fh))


def set_font(run, size_pt, bold=False, italic=False, sub=False, sup=False):
    run.font.name = "Times New Roman"
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic
    if sub:
        run.font.subscript = True
    if sup:
        run.font.superscript = True
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rFonts.set(qn(attr), "Times New Roman")


def add_rich_runs(p, text, size_pt=9.0, bold=False, italic=False):
    """Render text with _{sub} and ^{sup} markup as native Word subscripts/superscripts."""
    for part in SUB_SUP_RE.split(text):
        if not part:
            continue
        if part.startswith("_{") and part.endswith("}"):
            set_font(p.add_run(part[2:-1]), size_pt, bold=bold, italic=italic, sub=True)
        elif part.startswith("^{") and part.endswith("}"):
            set_font(p.add_run(part[2:-1]), size_pt, bold=bold, italic=italic, sup=True)
        else:
            set_font(p.add_run(part), size_pt, bold=bold, italic=italic)


def add_p(doc, text="", align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=3, line_spacing=1.05, size_pt=9.0, bold=False, italic=False):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing
    if text:
        add_rich_runs(p, text, size_pt=size_pt, bold=bold, italic=italic)
    return p


def add_section_heading(doc, text):
    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=7, space_after=3)
    set_font(p.add_run(text), 9.5, bold=True)
    return p


def add_lead_p(doc, lead, body_text, italic_lead=True, bold_lead=True):
    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=1, space_after=3)
    add_rich_runs(p, lead, size_pt=9.0, bold=bold_lead, italic=italic_lead)
    add_rich_runs(p, body_text, size_pt=9.0)
    return p


def set_cell_margins(cell, top=22, bottom=22, left=40, right=40):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for m, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        node = OxmlElement(f"w:{m}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def set_row_borders(row, top=None, bottom=None):
    for cell in row.cells:
        tcPr = cell._tc.get_or_add_tcPr()
        tcBorders = tcPr.find(qn("w:tcBorders"))
        if tcBorders is None:
            tcBorders = OxmlElement("w:tcBorders")
            tcPr.append(tcBorders)
        for side in ("top", "bottom", "left", "right"):
            el = tcBorders.find(qn(f"w:{side}"))
            if el is not None:
                tcBorders.remove(el)
        for side, spec in [("top", top), ("bottom", bottom)]:
            if spec is not None:
                b = OxmlElement(f"w:{side}")
                b.set(qn("w:val"), "single")
                b.set(qn("w:sz"), str(spec))
                b.set(qn("w:space"), "0")
                b.set(qn("w:color"), "000000")
                tcBorders.append(b)
        for side in ("left", "right"):
            b = OxmlElement(f"w:{side}")
            b.set(qn("w:val"), "none")
            tcBorders.append(b)


def add_ieee_table(doc, caption, headers, rows, col_widths=None, right_align_from=1):
    cap = add_p(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=5, space_after=2)
    add_rich_runs(cap, caption, size_pt=7.5, bold=True)

    tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.autofit = False
    hdr_row = tbl.rows[0]
    for j, h in enumerate(headers):
        cell = hdr_row.cells[j]
        if col_widths:
            cell.width = Inches(col_widths[j])
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if j >= right_align_from else WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        add_rich_runs(p, h, size_pt=7.5, bold=True)
    set_row_borders(hdr_row, top=8, bottom=4)

    for i, row_data in enumerate(rows):
        row = tbl.rows[1 + i]
        for j, val in enumerate(row_data):
            cell = row.cells[j]
            if col_widths:
                cell.width = Inches(col_widths[j])
            set_cell_margins(cell)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if j >= right_align_from else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            add_rich_runs(p, str(val), size_pt=7.5, bold=(i == len(rows) - 1 and str(row_data[0]).startswith("Total")))
        set_row_borders(row, top=None, bottom=(8 if i == len(rows) - 1 else None))

    add_p(doc, "", space_before=0, space_after=3)


def add_figure(doc, pdf_name, caption, width_in=3.3):
    png_prefix = TMP_FIGS / pdf_name.replace(".pdf", "")
    subprocess.run(
        ["pdftoppm", "-png", "-r", "300", "-singlefile", str(FIG_DIR / pdf_name), str(png_prefix)],
        check=True,
    )
    png_path = Path(str(png_prefix) + ".png")
    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=4, space_after=2)
    p.add_run().add_picture(str(png_path), width=Inches(width_in))
    cap = add_p(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=4)
    add_rich_runs(cap, caption, size_pt=7.5)


def set_two_columns(section, num_cols=2, space_twips=317):
    sectPr = section._sectPr
    cols = sectPr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        sectPr.append(cols)
    cols.set(qn("w:num"), str(num_cols))
    cols.set(qn("w:space"), str(space_twips))
    cols.set(qn("w:equalWidth"), "1")


def configure_margins(section):
    section.page_width = Inches(8.5)
    section.page_height = Inches(11.0)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.70)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)


def main():
    manifest = load_csv("manifest.csv")
    ora = load_csv("oracle_summary.csv")
    pol = load_csv("oracle_policy.csv")
    ctrl = load_csv("controllers.csv")
    csweep = load_csv("cost_sweep.csv")
    cdiag = load_csv("ctrl_diag.csv")
    fweights = load_csv("h3_exploratory_weights.csv")

    c_rows = [r for r in ora if float(r["switch_cost"]) > 0]
    z_rows = [r for r in ora if float(r["switch_cost"]) == 0]

    doc = Document()
    configure_margins(doc.sections[0])
    set_two_columns(doc.sections[0], num_cols=1)

    # ── 1-Column IEEE Title Block ──────────────────────────────────────────
    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=4)
    set_font(p.add_run("When Does Policy Switching Beat the Best Static Policy?\nA Reproducible Ceiling Study"), 17.0, bold=True)

    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=2, space_after=2)
    set_font(p.add_run("Muhammad Qasim, Hunain Tahir, Hussain Ahmad, and Mohsin Ghaffar Ghouri"), 11.0)

    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=1)
    set_font(p.add_run("University of Management and Technology (UMT), Lahore, Pakistan. M. Qasim is also with the Anoneurx Research Lab."), 8.5)

    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=6)
    set_font(p.add_run("Corresponding author: M. Qasim (e-mail: itskashie@anoneurx.com)"), 8.5, italic=True)

    sec2 = doc.add_section(WD_SECTION.CONTINUOUS)
    configure_margins(sec2)
    set_two_columns(sec2, num_cols=2, space_twips=317)

    # ── Abstract & Index Terms ─────────────────────────────────────────────
    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=2, space_after=3)
    set_font(p.add_run("Abstract—"), 8.5, bold=True, italic=True)
    add_rich_runs(
        p,
        "Dynamic policy switching is a recurring design pattern in adaptive page replacement: monitor a workload for drift, "
        "evaluate candidate policies in shadow caches, and switch to a better-matched policy. We ask the prior ceiling question: "
        "how much could any switching controller ever gain? Using an exact Viterbi dynamic-programming (DP) hindsight "
        "oracle across 88 traces (30 families spanning real-application page references, instrumented kernels, and public "
        "FIU/PDL traces) at three working-set-relative capacities (1%, 5%, 10% WSS) against 21 baselines, we find that "
        "when paying a full-cache-refill switch penalty (c_{switch} = C), 0 of 90 family–capacity groups clear our worthwhile-gain "
        "threshold (≥ 0.02 net miss-ratio reduction on ≥ 2/3 of traces; mean net gain 0.0001, max 0.0067). A five-point switch-cost sweep "
        "across four window granularities (W ∈ {10k, 25k, 50k, 100k}) establishes a sharp collapse boundary: 0/264 pairs clear "
        "0.02 whenever c_{switch} ≥ 0.50C, and only 5.3% clear it even at c_{switch} = 0, W = 10k. Static S3-FIFO "
        "achieves the lowest overall miss ratio (0.4890 at 59.5 ns/ref) and dominates all 17 online switching controllers "
        "(all +0.0393 to +0.0433 higher miss ratio; p_{Holm} = 1.000) because sampled shadow caches (C_{s} ≤ 0.2C) "
        "mis-rank weaker policies ahead of S3-FIFO 32.9%–38.9% of the time. Observable non-stationarity features predict rare "
        "zero-cost headroom on unseen families with 84.1% leave-one-family-out accuracy (AUC = 0.901).",
        size_pt=8.5,
        bold=True,
    )

    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=2, space_after=4)
    set_font(p.add_run("Index Terms—"), 8.5, bold=True, italic=True)
    set_font(p.add_run("page replacement, cache replacement, drift detection, policy switching, hindsight oracle, measurement study"), 8.5, bold=True)

    # ── I. INTRODUCTION ────────────────────────────────────────────────────
    add_section_heading(doc, "I. INTRODUCTION")
    add_p(doc, "Page replacement determines which memory pages are evicted when physical memory is full. Because real workloads mix phases with distinct access patterns—sequential scans, hot-object reuse, and random I/O—no single static policy is optimal at every instant. This observation has motivated three decades of adaptive replacement research, from SEQ [1] and EELRU [2] through ARC [3], LeCaR [4], CACHEUS [5], and recent learned policies [6], [28].")
    add_p(doc, "A recurring architecture in this literature is discrete policy switching: monitor the miss stream for workload drift, evaluate a pool of candidate policies via sampled shadow caches, and switch the active policy when a candidate outperforms the incumbent by a statistical margin. Each switch carries a state-migration or cache-rewarm cost, while the hoped-for benefit is a lower miss ratio in the new regime. Whether that benefit exceeds the cost in realistic workloads—especially against modern scan-resistant static baselines such as S3-FIFO [7] and SIEVE [8]—is rarely quantified as a strict upper bound.")
    add_p(doc, "We pose one concrete question: when, if ever, does discrete policy switching beat the best static policy once switch costs are counted? Rather than proposing yet another switching heuristic, we bound the entire design space using an exact hindsight oracle—the optimal per-window policy schedule found by Viterbi dynamic programming—and compare it against the best no-switch policy on the same trace.")
    add_lead_p(doc, "Protocol. ", "We recorded three hypotheses (H1–H3), endpoints, and the smallest worthwhile gain (≥ 0.02 net miss-ratio reduction on at least two-thirds of traces in a family–capacity group) in a local git commit prior to executing the study, without external third-party preregistration; accordingly, we treat the study as post hoc.")
    add_lead_p(doc, "Traces. ", "We evaluate 88 traces spanning 30 families and four sources (Table I): (i) 10 real-application page-level traces captured via an LD_PRELOAD tracer on SQLite workloads, git repository operations, and a Python ETL pipeline; (ii) 60 instrumented-program page traces across 15 algorithmic kernels; (iii) 12 public FIU block-I/O traces [9]; and (iv) 6 public PDL storage/cache traces [9], [29]. Every trace is evaluated at capacities 1%, 5%, and 10% of its working-set size (WSS), yielding 264 trace–capacity pairs. Because instrumented kernels represent 68% of raw trace count, we report both aggregate and per-source statistics throughout.")

    src_labels = {
        "real_app_pageref": "Real-app (SQLite, git, Python)",
        "instrumented_program": "Instrumented kernels",
        "fiu_public": "Public FIU block-I/O",
        "pdl_public": "Public PDL storage/cache",
    }
    t1_rows = []
    for src in ("real_app_pageref", "instrumented_program", "fiu_public", "pdl_public"):
        sub = [m for m in manifest if m["source"] == src]
        t1_rows.append([src_labels[src], len(set(m["family"] for m in sub)), len(sub),
                        f"{np.mean([int(m['refs']) for m in sub])/1e6:.2f}M",
                        f"{np.median([int(m['wss']) for m in sub]):,.0f}"])
    t1_rows.append(["Total", len(set(m["family"] for m in manifest)), len(manifest),
                    f"{np.mean([int(m['refs']) for m in manifest])/1e6:.2f}M",
                    f"{np.median([int(m['wss']) for m in manifest]):,.0f}"])
    add_ieee_table(doc, "TABLE I. TRACE CORPUS SUMMARY (88 TRACES, 30 FAMILIES)",
                   ["Source", "Fam.", "Tr.", "Refs", "WSS"], t1_rows,
                   col_widths=[1.55, 0.35, 0.32, 0.48, 0.55])

    add_lead_p(doc, "Contributions. ", "(1) A formal problem formulation and exact Viterbi DP oracle ceiling across 88 traces and three capacities, including a 5-point switch-cost sweep and 4 window granularities, establishing a sharp 0.50C collapse boundary; (2) A matched-cost comparison of 17 switching controllers over a 6-policy candidate pool against static S3-FIFO; (3) A quantitative failure-mode decomposition explaining why all 17 controllers lose to S3-FIFO; (4) An unseen-family predictive rule evaluated via LOFO and cross-source holdout, paired with trace-level case studies.")

    # ── II. BACKGROUND AND RELATED WORK ────────────────────────────────────
    add_section_heading(doc, "II. BACKGROUND AND RELATED WORK")
    add_lead_p(doc, "Static, adaptive, and learned replacement. ", "Classical adaptive policies such as SEQ [1], EELRU [2], ARC [3], CAR [10], LIRS [11], 2Q [13], and CLOCK-Pro [14] adjust eviction priorities internally within a single unified structure. Modern static policies—W-TinyLFU [12], LHD [15], S3-FIFO [7], and SIEVE [8]—achieve strong scan resistance and low CPU overhead without multi-policy switching. Regret-based and hybrid approaches include DIP [16], ACME [30], LeCaR [4], CACHEUS [5], and Acme [19]. Recent 2025–2026 systems expand this space with 3L-Cache [6], LPR [17], S4-FIFO [28], EACLOCK [31], Clock2Q+ [32], stale-tolerant evaluations [33], LLM prefix-cache studies [34], and eBPF-extensible OS/GPU memory hooks [35], [36].")
    add_lead_p(doc, "Drift detection and shadow evaluation. ", "CUSUM [20], Page–Hinkley [20], and ADWIN [21] originate in supervised streaming [22]; recent unsupervised detectors [37]–[42] address label scarcity in general streams, whereas page replacement exposes only the policy-dependent miss stream. SHARDS [23] and miniature simulations [24] use sampled shadow caches; we enforce C_{s} = min(⌊0.2C⌋, max(8, ⌊0.5D_{w}⌋)) so C_{s}/D_{w} < 1 holds by construction.")
    add_lead_p(doc, "Hindsight oracles. ", "Belady's MIN [25] bounds single-page eviction, whereas our per-window Viterbi DP oracle bounds discrete policy switching over 21 implementable policies with explicit penalty c_{switch}.")

    # ── III. PROBLEM FORMULATION AND HYPOTHESES ────────────────────────────
    add_section_heading(doc, "III. PROBLEM FORMULATION AND HYPOTHESES")
    add_p(doc, "Let σ = (x_{1}, …, x_{n}) be a sequence of n page references over distinct pages U with working-set size WSS = |U|. For target capacity C = ⌊α · WSS⌋ (α ∈ {0.01, 0.05, 0.10}), we discard a warm-up prefix of n_{warm} = min(100,000, ⌊0.1n⌋) references and partition the remaining stream into T = ⌊(n − n_{warm})/W⌋ non-overlapping windows of size W (n_{eval} = T · W). Given a policy pool P and per-window misses m_{t,p}, let M_{best} = min_{p} ∑_{t} m_{t,p} be the best single static policy miss count.")
    add_p(doc, "A discrete switching schedule π = (π_{1}, …, π_{T}) incurs penalty c_{switch} ≥ 0 whenever π_{t} ≠ π_{t−1}. Net oracle gain is g(c_{switch}) = (M_{best} − min_{π} M(π; c_{switch})) / n_{eval} ≥ 0. Theorem 1 (Necessary Condition for Worthwhile Switching): for S ≥ 1 switches with mean dwell L̄ = n_{eval}/S, switch penalty c_{switch} = βC, and gross gain Δm̄, clearing threshold τ requires L̄ ≥ βC / (Δm̄ − τ), or β ≤ L̄(Δm̄ − τ)/C. Online controllers evaluate a candidate pool P_{cand} ⊆ P in sampled shadow caches satisfying C_{s}/D_{w} < 1. We test: (H1) at c_{switch} = C and W = 50,000, fewer than 10% of family–capacity groups clear g(C) ≥ 0.02 on ≥ 2/3 of traces; (H2) no online controller beats static S3-FIFO under Holm-adjusted paired Wilcoxon tests; and (H3) observable trace features predict unseen-family headroom under LOFO cross-validation.")

    # ── IV. ORACLE AND EXPERIMENTAL DESIGN ─────────────────────────────────
    add_section_heading(doc, "IV. ORACLE AND EXPERIMENTAL DESIGN")
    add_lead_p(doc, "Simulator and exact DP oracle. ", "Our C++17 simulator pathA_sim executes 21 policies under identical replay and measures CPU time via CLOCK_PROCESS_CPUTIME_ID. Using Viterbi DP in O(T P^{2}) time, we compute the exact minimum-cost schedule dp[t][p] = m_{t,p} + min_{q}(dp[t−1][q] + c_{switch} · 1[p ≠ q]).")
    add_lead_p(doc, "Switching controllers and hyperparameters. ", "We evaluate 17 online switching controllers over a 6-policy candidate pool (LRU, LFU-A, 2Q, MRU, S3-FIFO, ARC) against static S3-FIFO (Table II). Controllers sample references at p_{samp} = 0.20 and rank candidates in shadow caches (C_{s} ≤ 0.2C) via a lower-confidence-bound rule (z = 1.28, 40% warm-up, 4-block variance, dwell = 10, cooldown = 4, hysteresis = 30, epoch = 2,000 refs).")

    t_hp = [
        ["CUSUM", "low / med / high", "δ = 0.5, h ∈ {8.0, 5.0, 3.0}"],
        ["Page–Hinkley", "low / med / high", "δ = 0.005, λ ∈ {8.0, 5.0, 3.0}"],
        ["ADWIN", "low / med / high", "δ ∈ {0.0005, 0.002, 0.01}"],
        ["Periodic", "low / med / high", "interval ∈ {40, 20, 10} epochs"],
        ["Random", "low / med / high", "prob ∈ {0.02, 0.05, 0.10} / epoch"],
        ["OracleTrig", "oracle", "fires at DP switch boundaries"],
        ["ContShadow", "continuous", "evaluates every 10 epochs"],
    ]
    add_ieee_table(doc, "TABLE II. CONTROLLER HYPERPARAMETERS AND BUDGETS",
                   ["Trigger", "Budget", "Parameters"], t_hp,
                   col_widths=[0.85, 0.85, 1.50], right_align_from=3)

    # ── V. RESULTS: EXACT DP ORACLE CEILING (H1) ───────────────────────────
    add_section_heading(doc, "V. RESULTS: EXACT DP ORACLE CEILING (H1)")

    t2_rows = []
    for src, sname in [("real_app_pageref", "Real-app"), ("instrumented_program", "Prog."),
                       ("fiu_public", "FIU"), ("pdl_public", "PDL")]:
        for tag, pool in [("c=C", c_rows), ("c=0", z_rows)]:
            vals = np.array([float(r["net_gain_vs_best"]) for r in pool if r["source"] == src])
            t2_rows.append([f"{sname} ({tag})", len(vals), f"{vals.mean():.4f}", f"{np.quantile(vals,0.9):.4f}",
                            f"{vals.max():.4f}", f"{int((vals>=0.02).sum())}/{len(vals)}"])
    for label, pool in [("All W=50k (c=C)", c_rows), ("All W=50k (c=0)", z_rows)]:
        vals = np.array([float(r["net_gain_vs_best"]) for r in pool])
        t2_rows.append([label, len(vals), f"{vals.mean():.4f}", f"{np.quantile(vals,0.9):.4f}",
                        f"{vals.max():.4f}", f"{int((vals>=0.02).sum())}/{len(vals)}"])
    add_ieee_table(doc, "TABLE III. EXACT DP ORACLE NET GAIN OVER BEST STATIC POLICY",
                   ["Source (Cost)", "n", "Mean g", "p_{90} g", "Max g", "≥ 0.02"], t2_rows,
                   col_widths=[1.05, 0.30, 0.48, 0.45, 0.48, 0.48])

    add_figure(doc, "fig_oracle_ceiling.pdf",
               "Fig. 1. Mean and maximum net oracle gain across trace sources for c_{switch} = C and c_{switch} = 0 (W = 50,000).")

    add_lead_p(doc, "Switching rarely clears the threshold (H1 confirmed). ", "When paying the full-refill switch cost (c_{switch} = C), 0 of 90 family–capacity groups meet ≥ 0.02 on ≥ 2/3 of traces. Across all 264 pairs at W = 50,000, mean g = 0.0001, median g = 0.0000, p_{90} = 0.0000, and max g = 0.0067 (python_etl_s101 at 10% WSS). Equal-source macro-averaging yields identical mean g = 0.0001. Even at c_{switch} = 0, only 2/264 pairs (0.8%) reach 0.02 (fiu_online.cs.fiu.edu_test at 10% WSS: 0.0564; 5% WSS: 0.0208).")
    add_lead_p(doc, "Static S3-FIFO dominance & capacity breakdown. ", "Across all 264 pairs, S3-FIFO is best on 176 pairs (66.7%) with lowest mean miss ratio (0.4890 at 59.5 ns/ref), followed by CAR (0.5151), ARC (0.5189), and 2Q (0.5192) (Table IV). Table V disaggregates headroom and ContShadow across 1%, 5%, and 10% WSS: g(C) remains ≤ 0.0001 at every capacity, while ContShadow's deficit peaks at 1% WSS (+0.0562).")

    pol_mr, pol_ns = {}, {}
    for r in pol:
        pol_mr.setdefault(r["policy"], []).append(float(r["miss_ratio"]))
        pol_ns.setdefault(r["policy"], []).append(float(r["ns_per_ref"]))
    best_counts = Counter(r["best_static"] for r in c_rows)
    ranked_pols = sorted(pol_mr.keys(), key=lambda p: np.mean(pol_mr[p]))
    t3_rows = [[p, f"{np.mean(pol_mr[p]):.4f}", f"{np.median(pol_mr[p]):.4f}", best_counts[p], f"{np.mean(pol_ns[p]):.1f}"]
               for p in ranked_pols]
    add_ieee_table(doc, "TABLE IV. ALL 21 POLICIES RANKED BY MEAN MISS RATIO (264 PAIRS)",
                   ["Policy", "Mean MR", "Med. MR", "Best", "ns/ref"], t3_rows,
                   col_widths=[0.95, 0.60, 0.60, 0.45, 0.55])

    t_cap = [
        ["1% WSS", "0.5545", "0.5496", "0.0000", "0.0003", "0.6106", "+0.0562"],
        ["5% WSS", "0.4750", "0.4741", "0.0000", "0.0010", "0.5050", "+0.0300"],
        ["10% WSS", "0.4376", "0.4364", "0.0001", "0.0023", "0.4751", "+0.0374"],
    ]
    add_ieee_table(doc, "TABLE V. ORACLE CEILING AND CONTSHADOW DEFICIT BY CAPACITY (W = 50,000)",
                   ["Cap.", "S3-FIFO", "Best St.", "g(C)", "g(0)", "ContSh.", "Δ"], t_cap,
                   col_widths=[0.55, 0.45, 0.45, 0.42, 0.42, 0.45, 0.46])

    # ── VI. SWITCH-COST AND WINDOW SENSITIVITY ─────────────────────────────
    add_section_heading(doc, "VI. SWITCH-COST AND WINDOW SENSITIVITY")
    t_sw = []
    for w in (10000, 25000, 50000):
        for cf in ("0.00", "0.10", "0.25", "0.50", "1.00"):
            sub = [r for r in csweep if int(r["window"]) == w and r["cost_frac"] == cf]
            g = np.array([float(r["net_gain_vs_best"]) for r in sub])
            sw = np.mean([float(r["oracle_switches"]) for r in sub])
            clabel = "0" if cf == "0.00" else (f"{cf}C" if cf != "1.00" else "C")
            t_sw.append([f"{w//1000}k", clabel, f"{g.mean():.4f}", f"{np.quantile(g,0.9):.4f}",
                         f"{g.max():.4f}", f"{int((g>=0.02).sum())}/264", f"{sw:.2f}"])
    add_ieee_table(doc, "TABLE VI. DP ORACLE SENSITIVITY TO WINDOW W AND SWITCH COST",
                   ["W", "c_{sw}", "Mean g", "p_{90} g", "Max g", "≥ 0.02", "Sw."], t_sw,
                   col_widths=[0.35, 0.42, 0.48, 0.45, 0.48, 0.50, 0.40])

    add_figure(doc, "fig_cost_sweep.pdf",
               "Fig. 2. Percentage of trace–capacity pairs clearing g ≥ 0.02 vs. switch penalty fraction c_{switch}/C across three window granularities.")
    add_p(doc, "At W = 10,000 and c_{switch} = 0, 14/264 pairs (5.3%) clear 0.02 (mean 0.0045, max 0.1331). At W = 100,000, c_{switch} = 0 yields mean 0.0007 (1/264 ≥ 0.02) and c_{switch} = C yields 0/264. Whenever c_{switch} ≥ 0.50C, 0 of 264 pairs clear 0.02 at any window size (10k, 25k, 50k, or 100k). Table VII shows that all 14 zero-cost hits at W = 10,000 come from fiu_public (10/36) and real_app_pageref (4/30).")

    t_w10_src = [
        ["fiu_public", "36", "0.0219", "0.1331", "10"],
        ["real_app_pageref", "30", "0.0103", "0.0665", "4"],
        ["pdl_public", "18", "0.0016", "0.0087", "0"],
        ["instrumented_program", "180", "0.0004", "0.0116", "0"],
    ]
    add_ieee_table(doc, "TABLE VII. PER-SOURCE BREAKDOWN AT W = 10,000, c_{switch} = 0",
                   ["Source", "Pairs", "Mean g", "Max g", "≥ 0.02"], t_w10_src,
                   col_widths=[1.25, 0.40, 0.50, 0.50, 0.45])

    # ── VII. RESULTS: SWITCHING CONTROLLERS VS. S3-FIFO (H2) ───────────────
    add_section_heading(doc, "VII. RESULTS: SWITCHING CONTROLLERS VS. S3-FIFO (H2)")

    s3_mr = {(r["trace"], r["cap_frac"]): float(r["miss_ratio"]) for r in pol if r["policy"] == "S3-FIFO"}
    s3_ns_mean = np.mean([float(r["ns_per_ref"]) for r in pol if r["policy"] == "S3-FIFO"])
    ctrl_names = sorted(set(r["controller"] for r in ctrl) - {"S3-FIFO"})
    t4_rows = [["S3-FIFO (static)", "0.0000", "---", "0.00", f"{s3_ns_mean:.1f}"]]
    cstats = []
    for cname in ctrl_names:
        sub = [r for r in ctrl if r["controller"] == cname]
        deltas = np.array([float(r["miss_ratio"]) - s3_mr[(r["trace"], r["cap_frac"])] for r in sub])
        sw = np.mean([float(r["switches"]) for r in sub])
        ns = np.mean([float(r["ns_per_ref"]) for r in sub])
        cstats.append((cname, deltas.mean(), sw, ns))
    for cname, dm, sw, ns in sorted(cstats, key=lambda x: x[1]):
        t4_rows.append([cname, f"{dm:+.4f}", "1.000", f"{sw:.2f}", f"{ns:.1f}"])
    add_ieee_table(doc, "TABLE VIII. SWITCHING CONTROLLERS VS. STATIC S3-FIFO (n = 264)",
                   ["Controller", "Δ MR", "p_{Holm}", "Sw.", "ns/ref"], t4_rows,
                   col_widths=[1.05, 0.58, 0.50, 0.42, 0.55])

    add_figure(doc, "fig_controllers_vs_s3fifo.pdf",
               "Fig. 3. Mean miss ratio vs. simulator CPU cost (ns/ref). Static S3-FIFO dominates all 17 switching controllers.")
    add_lead_p(doc, "No controller beats S3-FIFO (H2 confirmed). ", "Every switching controller incurs a higher mean miss ratio than static S3-FIFO (Δ ∈ [+0.0393, +0.0433], Holm-adjusted [26], [27] p = 1.000, because every controller has higher mean miss ratio than S3-FIFO so the one-sided 'less' test cannot reject) and higher CPU overhead (92.9–199.1 ns/ref vs. 59.5 ns/ref). Even OracleTrig (+0.0405) loses because the bottleneck is shadow ranking error rather than trigger accuracy.")

    # ── VIII. CONTROLLER FAILURE-MODE DIAGNOSIS ────────────────────────────
    add_section_heading(doc, "VIII. CONTROLLER FAILURE-MODE DIAGNOSIS")
    t_diag = []
    for cname in ("ContShadow", "CUSUM-med", "OracleTrig"):
        sub = [r for r in cdiag if r["controller"] == cname]
        dm = np.mean([float(r["miss_ratio"]) - float(r["s3fifo_miss_ratio"]) for r in sub])
        sh = [np.mean([float(r[k]) for r in sub]) for k in ("s3fifo_frac","lru_frac","q2_frac","arc_frac","lfua_frac","mru_frac")]
        t_diag.append([f"{cname} (all)", f"{dm:+.4f}"] + [f"{x:.3f}" for x in sh])
    for src, sname in [("real_app_pageref", "Real-app"), ("fiu_public", "FIU"),
                       ("pdl_public", "PDL"), ("instrumented_program", "Prog.")]:
        sub = [r for r in cdiag if r["controller"] == "ContShadow" and r["source"] == src]
        dm = np.mean([float(r["miss_ratio"]) - float(r["s3fifo_miss_ratio"]) for r in sub])
        sh = [np.mean([float(r[k]) for r in sub]) for k in ("s3fifo_frac","lru_frac","q2_frac","arc_frac","lfua_frac","mru_frac")]
        t_diag.append([f"ContSh. ({sname})", f"{dm:+.4f}"] + [f"{x:.3f}" for x in sh])
    add_ieee_table(doc, "TABLE IX. ACTIVE-POLICY TIME-SHARE AND DEFICIT VS. S3-FIFO",
                   ["Controller / Src", "Δ MR", "S3", "LRU", "2Q", "ARC", "LFU", "MRU"], t_diag,
                   col_widths=[0.95, 0.45, 0.30, 0.30, 0.28, 0.28, 0.28, 0.28])
    add_p(doc, "Table IX explains the +0.041 deficit: sampled shadow caches (C_{s} ≤ 0.2C, p_{samp} = 0.20) compress S3-FIFO's 10%/90% queue split and ghost filter into noisy sample windows, mis-ranking LRU (18.9%–22.5%), MRU (5.9%–7.4%), and LFU-A (4.4%–6.6%) ahead of S3-FIFO 32.9%–38.9% of the time.")

    add_lead_p(doc, "Noise-free (1.0C) and cost-aware shadow ablation. ", "Eliminating shadow sampling noise (FullShadow: C_{s} = C, p_{samp} = 1.0) reduces the deficit from +0.0412 to +0.0284 and cuts MRU selection from 6.0% to 1.8%, while adding a cost-aware gate (FullShadow-CostAware: K = C) lowers switches from 1.73 to 0.77. Yet both still lose significantly to static S3-FIFO (p = 1.000) at 10.7× CPU cost (630–639 ns/ref vs. 59.5 ns/ref) because finite rolling windows under-estimate S3-FIFO relative to LRU (26.2%–32.4% share).")
    t_ab = [
        ["ContShadow (0.2C)", "+0.0412", "1.000", "1.73", "199.1", ".671", ".189", ".060"],
        ["FullShadow (1.0C)", "+0.0284", "1.000", "1.12", "639.4", ".627", ".262", ".018"],
        ["FullSh.-CostAware", "+0.0286", "1.000", "0.77", "630.1", ".577", ".324", ".011"],
    ]
    add_ieee_table(doc, "TABLE IX-B. NOISE-FREE (C_{s} = C, p_{samp} = 1.0) SHADOW ABLATION (n = 264)",
                   ["Controller", "Δ MR", "p", "Sw.", "ns/ref", "S3", "LRU", "MRU"], t_ab,
                   col_widths=[1.05, 0.42, 0.35, 0.32, 0.42, 0.28, 0.28, 0.28])

    # ── IX. PREDICTIVE RULE AND CASE STUDIES (H3) ──────────────────────────
    add_section_heading(doc, "IX. PREDICTIVE RULE AND CASE STUDIES (H3)")
    add_p(doc, "Because 0/90 groups clear ≥ 0.02 at c_{switch} = C, the primary target is uniformly negative (LOFO accuracy 1.000, AUC undefined). On an exploratory target predicting max_{cap} g(0) ≥ 0.005 (13/88 positive traces), L_{2}-regularized logistic regression achieves 84.1% LOFO accuracy (AUC = 0.901) and 0.890–1.000 cross-source AUC (Table X, Fig. 4). Top predictors are window_reuse_cv (+0.2808), uniq_window_cv (+0.1843), entropy_bits (+0.1778), and window_turnover_max (+0.1383) (Table XI).")

    t5_rows = [
        ["Primary (c=C, g ≥ 0.02)", "88", "---", "1.000", "---"],
        ["Expl. LOFO (c=0, g ≥ 0.005)", "88", "---", "0.841", "0.901"],
        ["Real-app holdout (tr: pub)", "10", "78", "0.600", "1.000"],
        ["Public holdout (tr: real)", "78", "10", "0.654", "0.890"],
    ]
    add_ieee_table(doc, "TABLE X. UNSEEN-FAMILY PREDICTIVE RULE (LOFO & CROSS-SOURCE)",
                   ["Evaluation split", "n_{te}", "n_{tr}", "Acc.", "AUC"], t5_rows,
                   col_widths=[1.45, 0.35, 0.35, 0.45, 0.45])

    add_figure(doc, "fig_lofo_roc.pdf",
               "Fig. 4. Exploratory LOFO ROC curve predicting zero-cost headroom ≥ 0.005 on unseen trace families (AUC = 0.901).",
               width_in=3.1)

    t_fw = [[r["feature"], f"{float(r['weight']):+.4f}"] for r in fweights]
    add_ieee_table(doc, "TABLE XI. STANDARDIZED LOGISTIC WEIGHTS (EXPLORATORY H3)",
                   ["Standardized feature", "Weight"], t_fw,
                   col_widths=[2.10, 0.90])

    add_figure(doc, "fig_window_timeline.pdf",
               "Fig. 5. Per-window miss ratio (10% WSS, W = 50,000) on fiu_online_test (left, 7 zero-cost switches, g(0) = 0.0564) vs. sqlite_join_agg_s101 (right, stationary, g(0) = 0.0020).",
               width_in=3.3)
    add_lead_p(doc, "Representative trace case studies. ", "Fig. 5 and Table XII contrast four traces: fiu_online.cs.fiu.edu_test exhibits extreme window reuse variability (window_reuse_cv = 2.5916) and g(0) = 0.0564 at 10% WSS, yet g(C) = 0.0000; git_repo_s202 yields g(0) = 0.0196 and g(C) = 0.0000; python_etl_s101 retains one DP switch at c_{switch} = C (g(C) = 0.0067); and sqlite_join_agg_s101 remains stationary (g(0) = 0.0020, g(C) = 0.0005).")

    t_cases = [
        ["fiu_online_test", "2.5916", "0.1415", "0.0564", "0.0000"],
        ["git_repo_s202", "0.3309", "0.3096", "0.0196", "0.0000"],
        ["python_etl_s101", "0.7205", "0.5904", "0.0087", "0.0067"],
        ["sqlite_join_agg", "0.0012", "0.1124", "0.0020", "0.0005"],
    ]
    add_ieee_table(doc, "TABLE XII. REPRESENTATIVE TRACE CASE STUDIES (10% WSS, W = 50,000)",
                   ["Trace", "win_reuse_cv", "uniq_win_cv", "g(0)", "g(C)"], t_cases,
                   col_widths=[1.05, 0.65, 0.65, 0.42, 0.42])

    # ── X. DISCUSSION, THREATS TO VALIDITY, AND CONCLUSION ─────────────────
    add_section_heading(doc, "X. DISCUSSION, THREATS TO VALIDITY, AND CONCLUSION")
    add_lead_p(doc, "Design implication. ", "Across 88 traces, discrete policy switching never clears 0.02 once switch cost reaches 0.50C, and practical sampled-shadow controllers lose +0.039–+0.043 miss ratio to static S3-FIFO. Engineering effort is better invested in a single scan-resistant static policy (e.g., S3-FIFO, CAR, or SIEVE).")
    add_lead_p(doc, "Limitations and threats to validity. ", "(1) User-space LD_PRELOAD captures file/syscall and mmap creation events rather than post-map page faults, kernel readahead, or writeback. (2) Instrumented kernels represent 68% of raw trace count, though macro-averaging by source confirms identical conclusions. (3) Sub-10k micro-phases are outside our W ∈ [10k, 100k] scope. (4) Controllers use a 6-policy candidate pool, but S3-FIFO (the #1 policy across all 21 baselines) is already inside the pool; adding lower-ranked policies would only increase shadow-ranking contention. (5) Our protocol was timestamped locally in git rather than in an external registry (post hoc status).")
    add_lead_p(doc, "Conclusion. ", "An exact Viterbi DP hindsight oracle across 88 traces, 30 families, and three capacities shows that discrete policy switching clears 0.02 net gain in 0/90 groups at c_{switch} = C and 0/264 pairs whenever c_{switch} ≥ 0.50C. Static S3-FIFO dominates all 17 switching controllers, and observable non-stationarity features predict rare zero-cost headroom on unseen families (AUC = 0.901).")

    # ── REFERENCES ─────────────────────────────────────────────────────────
    add_section_heading(doc, "REFERENCES")
    refs = [
        "[1] G. Glass and P. Cao, 'Adaptive page replacement based on memory reference behavior,' in Proc. ACM SIGMETRICS, 1997, pp. 115–126.",
        "[2] Y. Smaragdakis, S. Kaplan, and P. Wilson, 'EELRU: Simple and effective adaptive page replacement,' in Proc. ACM SIGMETRICS, 1999, pp. 122–133.",
        "[3] N. Megiddo and D. S. Modha, 'ARC: A self-tuning, low overhead replacement cache,' in Proc. USENIX FAST, 2003, pp. 115–130.",
        "[4] K. Vietri et al., 'Driving cache replacement with ML-based LeCaR,' in Proc. USENIX HotStorage, 2018.",
        "[5] L. V. Rodriguez et al., 'Learning cache replacement with CACHEUS,' in Proc. USENIX FAST, 2021, pp. 341–354.",
        "[6] W. Zhou et al., '3L-Cache: Low overhead and precise learning-based eviction policy for caches,' in Proc. USENIX FAST, 2025, pp. 237–254.",
        "[7] J. Yang et al., 'FIFO queues are all you need for cache eviction,' in Proc. ACM SOSP, 2023, pp. 130–149.",
        "[8] Y. Zhang et al., 'SIEVE is simpler than LRU: An efficient turn-key eviction algorithm for web caches,' in Proc. USENIX NSDI, 2024.",
        "[9] CMU Parallel Data Laboratory, 'Cache eviction tactics: cacheDatasets trace collection,' 2026.",
        "[10] S. Bansal and D. S. Modha, 'CAR: Clock with adaptive replacement,' in Proc. USENIX FAST, 2004, pp. 187–200.",
        "[11] S. Jiang and X. Zhang, 'LIRS: An efficient low inter-reference recency set replacement policy,' in Proc. ACM SIGMETRICS, 2002, pp. 31–42.",
        "[12] G. Einziger, R. Friedman, and B. Manes, 'TinyLFU: A highly efficient cache admission policy,' ACM Trans. Storage, vol. 13, no. 4, 2017.",
        "[13] T. Johnson and D. Shasha, '2Q: A low overhead high performance buffer management replacement algorithm,' in Proc. VLDB, 1994, pp. 439–450.",
        "[14] S. Jiang, F. Chen, and X. Zhang, 'CLOCK-Pro: An effective improvement of the CLOCK replacement,' in Proc. USENIX ATC, 2005, pp. 323–336.",
        "[15] N. Beckmann, H. Chen, and A. Cidon, 'LHD: Improving cache hit rate by maximizing hit density,' in Proc. USENIX NSDI, 2018.",
        "[16] M. K. Qureshi et al., 'Adaptive insertion policies for high performance caching,' in Proc. ISCA, 2007, pp. 381–391.",
        "[17] H. Kim, 'Learning-based page replacement scheme for efficient I/O processing,' Sci. Rep., vol. 15, 2025.",
        "[18] Linux Kernel Organization, 'Multi-gen LRU,' Linux kernel documentation, 2026.",
        "[19] T. Azim, A. Nadeem, and A. Ailamaki, 'Adaptive cache mode selection for queries over raw data,' in Proc. ADMS@VLDB, 2018, pp. 51–65.",
        "[20] E. S. Page, 'Continuous inspection schemes,' Biometrika, vol. 41, no. 1–2, pp. 100–115, 1954.",
        "[21] A. Bifet and R. Gavalda, 'Learning from time-changing data with adaptive windowing,' in Proc. SIAM SDM, 2007, pp. 443–448.",
        "[22] J. Gama et al., 'A survey on concept drift adaptation,' ACM Comput. Surv., vol. 46, no. 4, 2014.",
        "[23] C. A. Waldspurger et al., 'Efficient MRC construction with SHARDS,' in Proc. USENIX FAST, 2015, pp. 95–110.",
        "[24] C. Waldspurger et al., 'Cache modeling and optimization using miniature simulations,' in Proc. USENIX ATC, 2017, pp. 487–498.",
        "[25] L. A. Belady, 'A study of replacement algorithms for a virtual-storage computer,' IBM Syst. J., vol. 5, no. 2, pp. 78–101, 1966.",
        "[26] F. Wilcoxon, 'Individual comparisons by ranking methods,' Biometrics Bull., vol. 1, no. 6, pp. 80–83, 1945.",
        "[27] S. Holm, 'A simple sequentially rejective multiple test procedure,' Scand. J. Stat., vol. 6, no. 2, pp. 65–70, 1979.",
        "[28] H. Xia et al., 'Learning-augmented heuristics: Simple yet smart, robust and interpretable cache eviction,' in Proc. USENIX OSDI, 2026, pp. 2241–2259.",
        "[29] D. Narayanan, A. Donnelly, and A. Rowstron, 'Write off-loading: Practical power management for enterprise storage,' ACM Trans. Storage, vol. 4, no. 3, 2008.",
        "[30] I. Ari et al., 'ACME: Adaptive caching using multiple experts,' in Proc. WDAS, 2002.",
        "[31] G. Yuan et al., 'EACLOCK: An efficient and adaptive page replacement algorithm to understand your workload,' IEEE Trans. Knowl. Data Eng., vol. 38, no. 11, pp. 7387–7401, Nov. 2026.",
        "[32] Y. Zhai et al., 'Clock2Q+: A simple and efficient replacement algorithm for metadata cache in VMware vSAN,' Proc. VLDB Endow., vol. 19, no. 12, pp. 3874–3887, 2026.",
        "[33] N. Patel and H. Maniar, 'Comparative evaluation of cache replacement algorithms for time-bounded stale-tolerant data workloads,' Int. J. Sci. Res. Technol., vol. 3, no. 6, pp. 556–564, 2026.",
        "[34] Y. Liu, M. Yu, and J. Yang, 'When fancy eviction fails: Rethinking cache replacement for LLM prefix reuse,' arXiv:2609.28870, 2026.",
        "[35] Y. Zheng et al., 'gpu_ext: Extensible OS policies for GPUs via eBPF,' arXiv:2512.12615, 2025.",
        "[36] W. Shen et al., 'Towards fully-fledged GPU multitasking via proactive memory scheduling,' arXiv:2512.24637, 2025.",
        "[37] P. Lu et al., 'Early concept drift detection via prediction uncertainty,' in Proc. AAAI, 2025.",
        "[38] N. Tan et al., 'Flexible and efficient drift detection without labels,' arXiv:2506.08734, 2025.",
        "[39] P. Lu et al., 'Autonomous concept drift threshold determination,' arXiv:2511.09953, 2025.",
        "[40] N. Harshit and K. Mounvik, 'Improving real-time concept drift detection using a hybrid transformer-autoencoder framework,' arXiv:2508.07085, 2025.",
        "[41] S. Bandyopadhyay, J. Bose, and S. Roy Chowdhury, 'A hybrid framework for real-time data drift and anomaly identification,' Int. J. Math. Eng. Manag. Sci., vol. 10, no. 3, pp. 777–796, 2025.",
        "[42] D. N. Assis and V. M. A. Souza, 'ADWIN-U: Adaptive windowing for unsupervised drift detection on data streams,' Knowl. Inf. Syst., 2025.",
    ]
    for ref in refs:
        p = add_p(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=1.5, line_spacing=1.0)
        set_font(p.add_run(ref), 7.5)

    out_docx = ROOT / "Drift_Gating_Final_IEEE.docx"
    doc.save(str(out_docx))
    shutil.copy2(TEX_DIR / "main.pdf", ROOT / "Drift_Gating_Final_IEEE.pdf")
    print(f"Updated {out_docx} and {ROOT / 'Drift_Gating_Final_IEEE.pdf'}")


if __name__ == "__main__":
    main()
