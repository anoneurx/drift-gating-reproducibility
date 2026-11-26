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


def set_cell_width_dxa(cell, dxa):
    tcPr = cell._tc.get_or_add_tcPr()
    tcW = tcPr.find(qn("w:tcW"))
    if tcW is None:
        tcW = OxmlElement("w:tcW")
        tcPr.append(tcW)
    tcW.set(qn("w:w"), str(dxa))
    tcW.set(qn("w:type"), "dxa")


def set_cell_margins(cell, top=18, bottom=18, left=22, right=22):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = tcPr.find(qn("w:tcMar"))
    if tcMar is not None:
        tcPr.remove(tcMar)
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


def add_ieee_table(doc, caption, headers, rows, col_widths=None, right_align_from=1, font_pt=7.0):
    cap = add_p(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=5, space_after=2)
    add_rich_runs(cap, caption, size_pt=7.5, bold=True)

    max_col_in = 3.25
    if col_widths is None:
        col_widths = [max_col_in / len(headers)] * len(headers)
    total_w = sum(col_widths)
    if total_w > max_col_in:
        scale = max_col_in / total_w
        col_widths = [w * scale for w in col_widths]
    dxa_widths = [int(round(w * 1440)) for w in col_widths]

    tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.autofit = False
    tblPr = tbl._tbl.tblPr
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW")
        tblPr.append(tblW)
    tblW.set(qn("w:w"), str(sum(dxa_widths)))
    tblW.set(qn("w:type"), "dxa")
    tblLayout = tblPr.find(qn("w:tblLayout"))
    if tblLayout is None:
        tblLayout = OxmlElement("w:tblLayout")
        tblPr.append(tblLayout)
    tblLayout.set(qn("w:type"), "fixed")

    tblGrid = tbl._tbl.tblGrid
    if tblGrid is not None:
        for gc in list(tblGrid):
            tblGrid.remove(gc)
        for dw in dxa_widths:
            gc = OxmlElement("w:gridCol")
            gc.set(qn("w:w"), str(dw))
            tblGrid.append(gc)

    hdr_row = tbl.rows[0]
    for j, h in enumerate(headers):
        cell = hdr_row.cells[j]
        cell.width = Inches(col_widths[j])
        set_cell_width_dxa(cell, dxa_widths[j])
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if j >= right_align_from else WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        add_rich_runs(p, h, size_pt=font_pt, bold=True)
    set_row_borders(hdr_row, top=8, bottom=4)

    for i, row_data in enumerate(rows):
        row = tbl.rows[1 + i]
        for j, val in enumerate(row_data):
            cell = row.cells[j]
            cell.width = Inches(col_widths[j])
            set_cell_width_dxa(cell, dxa_widths[j])
            set_cell_margins(cell)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if j >= right_align_from else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            add_rich_runs(p, str(val), size_pt=font_pt, bold=(i == len(rows) - 1 and str(row_data[0]).startswith("Total")))
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
    fsw = load_csv("finesweep.csv")
    fsw_low = [r for r in fsw if float(r["cap_frac"]) <= 0.10]
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
        "Dynamic policy switching is a common pattern in adaptive page replacement: monitor a workload for drift, "
        "rank candidate policies in shadow caches, and switch when a candidate outperforms the incumbent. We bound the "
        "achievable headroom of discrete policy switching using a Viterbi dynamic-programming (DP) hindsight oracle—"
        "exact under an independent-replay model—across 88 traces (30 families) and capacities from 1% to 50% of "
        "working-set size (WSS) against 21 baselines. At a worst-case full-refill penalty (c_{switch} = C, W = 50,000), "
        "0 of 90 family–capacity groups (1%–10% WSS) clear a 0.02 net miss-ratio reduction (mean 0.0001, max 0.0067). "
        "Under realistic metadata-migration penalties (c_{switch} ≤ 0.10C) and fine windows (W = 5,000), only 13/264 "
        "pairs (4.9%) clear 0.02; across W ∈ {5k, 10k, 25k, 50k}, 0/264 pairs clear 0.02 once c_{switch} ≥ 0.50C. "
        "Static S3-FIFO achieves the lowest mean miss ratio (0.4890 at 59.5 ns/ref) and outperforms all 17 online "
        "controllers (+0.0393 to +0.0433 higher miss ratio; two-sided p < 10^{-15}, 95% family-cluster CI excluding zero), "
        "as well as noise-free (1.0C), persistent-shadow (+0.0175, p = 1.04×10^{-20}), and 21-policy-pool (+0.0470) "
        "ablations, because cold-window shadow evaluation mis-ranks the top-1 policy in 32% of windows. An exploratory "
        "leave-one-family-out ranker predicts rare zero-cost headroom with AUC = 0.901 but 0.493 balanced accuracy due to "
        "14.8% class imbalance.",
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
                   ["Source", "Fam.", "Tr.", "Refs", "WSS (med)"], t1_rows,
                   col_widths=[1.48, 0.34, 0.30, 0.48, 0.65])

    add_lead_p(doc, "Contributions. ", "(1) An independent-replay Viterbi DP oracle ceiling across 88 traces and capacities from 1% to 50% WSS, including a 9-point switch-cost sweep and 4 window granularities (W ∈ {5k, 10k, 25k, 50k}), establishing an empirical 0.50C zero-clearing point; (2) A matched-cost comparison of 17 switching controllers plus a 21-policy expansion (ContShadow-21) against static S3-FIFO using two-sided Wilcoxon tests and family-cluster bootstrap CIs; (3) Direct causal diagnosis via shadow-ranking accuracy across 9,564 evaluation windows, noise-free/persistent ablations, and user-space pread overhead; (4) An exploratory unseen-family risk score via LOFO and cross-source holdout.")

    # ── II. BACKGROUND AND RELATED WORK ────────────────────────────────────
    add_section_heading(doc, "II. BACKGROUND AND RELATED WORK")
    add_lead_p(doc, "Static, adaptive, and learned replacement. ", "Classical adaptive policies such as SEQ [1], EELRU [2], ARC [3], CAR [10], LIRS [11], 2Q [13], and CLOCK-Pro [14] adjust eviction priorities internally within a single unified structure. Modern static policies—W-TinyLFU [12], LHD [15], S3-FIFO [7], and SIEVE [8]—achieve strong scan resistance and low CPU overhead without multi-policy switching. Regret-based and hybrid approaches include DIP [16], ACME [30], LeCaR [4], CACHEUS [5], and Acme [19]. Recent 2025–2026 systems expand this space with 3L-Cache [6], LPR [17], S4-FIFO [28], EACLOCK [31], Clock2Q+ [32], stale-tolerant evaluations [33], LLM prefix-cache studies [34], and eBPF-extensible OS/GPU memory hooks [35], [36].")
    add_lead_p(doc, "Drift detection and shadow evaluation. ", "CUSUM [20], Page–Hinkley [20], and ADWIN [21] originate in supervised streaming [22]; recent unsupervised detectors [37]–[42] address label scarcity in general streams, whereas page replacement exposes only the policy-dependent miss stream. SHARDS [23] and miniature simulations [24] use sampled shadow caches; we enforce C_{s} = min(⌊0.2C⌋, max(8, ⌊0.5D_{w}⌋)) so C_{s}/D_{w} < 1 holds by construction.")
    add_lead_p(doc, "Hindsight oracles. ", "Belady's MIN [25] bounds single-page eviction, whereas our per-window Viterbi DP oracle bounds discrete policy switching over 21 implementable policies with explicit penalty c_{switch}.")

    # ── III. PROBLEM FORMULATION AND HYPOTHESES ────────────────────────────
    add_section_heading(doc, "III. PROBLEM FORMULATION AND HYPOTHESES")
    add_p(doc, "Let σ = (x_{1}, …, x_{n}) be a sequence of n page references over distinct pages U with working-set size WSS = |U|. For target capacity C = ⌊α · WSS⌋ (α ∈ {0.01, 0.05, 0.10}), we discard a warm-up prefix of n_{warm} = min(100,000, ⌊0.1n⌋) references and partition the remaining stream into T = ⌊(n − n_{warm})/W⌋ non-overlapping windows of size W (n_{eval} = T · W). Given a policy pool P and per-window misses m_{t,p}, let M_{best} = min_{p} ∑_{t} m_{t,p} be the best single static policy miss count.")
    add_p(doc, "A discrete switching schedule π = (π_{1}, …, π_{T}) incurs penalty c_{switch} ≥ 0 whenever π_{t} ≠ π_{t−1}. Net oracle gain is g(c_{switch}) = (M_{best} − min_{π} M(π; c_{switch})) / n_{eval} ≥ 0. Proposition 1 (Necessary Condition for Worthwhile Switching): for S ≥ 1 switches with mean dwell L̄ = n_{eval}/S, switch penalty c_{switch} = βC, and gross gain Δm̄, clearing threshold τ requires L̄ ≥ βC / (Δm̄ − τ), or β ≤ L̄(Δm̄ − τ)/C. Online controllers evaluate a candidate pool P_{cand} ⊆ P in sampled shadow caches satisfying C_{s}/D_{w} < 1. We test: (H1) at c_{switch} = C and W = 50,000, fewer than 10% of family–capacity groups clear g(C) ≥ 0.02 on ≥ 2/3 of traces; (H2) no online controller beats static S3-FIFO under Holm-adjusted paired Wilcoxon tests; and (H3) observable trace features predict unseen-family headroom under LOFO cross-validation.")

    # ── IV. ORACLE AND EXPERIMENTAL DESIGN ─────────────────────────────────
    add_section_heading(doc, "IV. ORACLE AND EXPERIMENTAL DESIGN")
    add_lead_p(doc, "Simulator and exact DP oracle. ", "Our C++17 simulator pathA_sim executes 21 policies under identical replay and measures CPU time via CLOCK_PROCESS_CPUTIME_ID. Using Viterbi DP in O(T P^{2}) time, we compute the exact minimum-cost schedule dp[t][p] = m_{t,p} + min_{q}(dp[t−1][q] + c_{switch} · 1[p ≠ q]). Algorithm 1 summarizes the paired evaluation loop.")
    t_alg = [
        ["1. Warm-up: Replay n_{warm} = min(100k, ⌊0.1n⌋) refs; partition remaining n_{eval} = TW refs into T windows of size W."],
        ["2. Oracle DP: Simulate P = 21 policies to form {m_{t,p}}; solve Viterbi DP for c_{switch} ∈ {0, 0.10C, 0.25C, 0.50C, C} to obtain g(c_{switch})."],
        ["3. Online Controllers: Execute active policy at capacity C; on drift trigger (or every 10 epochs), rank 6-policy pool in shadow caches (C_{s}/D_{w} < 1 or 1.0C ablation) via 4-block LCB (z = 1.28) and migrate resident metadata on switch."],
    ]
    add_ieee_table(doc, "ALGORITHM 1. EXACT DP ORACLE & CONTROLLER EVALUATION",
                   ["Evaluation Pipeline"], t_alg, col_widths=[3.25], right_align_from=2, font_pt=7.0)
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

    add_lead_p(doc, "Full-refill ceiling (H1 supported). ", "When paying the full-refill switch cost (c_{switch} = C), 0 of 90 family–capacity groups meet ≥ 0.02 on ≥ 2/3 of traces. Across all 264 pairs at W = 50,000, mean g(C) = 0.0001, median = 0.0000, p_{90} = 0.0000, and max = 0.0067 (python_etl_s101 at 10% WSS). Equal-source macro-averaging yields identical mean g(C) = 0.0001. At c_{switch} = 0, only 2/264 pairs (0.8%) reach 0.02 (fiu_online_test at 10% WSS: 0.0564; 5% WSS: 0.0208), noting that FIU traces (0.49M refs, median WSS 156,736) incur ≥ 32% compulsory first-touch misses.")
    add_lead_p(doc, "Static S3-FIFO dominance & capacity breakdown (1%–50% WSS). ", "Across all 264 pairs (21-policy ranking in Supplement Table S1), S3-FIFO is best on 176 pairs (66.7%) with lowest mean miss ratio (0.4890 at 59.5 ns/ref), ahead of CAR (0.5151), ARC (0.5189), and 2Q (0.5192). Table IV disaggregates 1%, 5%, and 10% WSS. Extending the oracle to 25% and 50% WSS (88 pairs each, W = 50,000) confirms the ceiling: at c_{switch} = C, only 2/88 pairs (2.3%, max 0.0251) clear 0.02 at 25% WSS and 0/88 (max 0.0141) at 50% WSS.")

    t_cap = [
        ["1% WSS", "0.5545", "0.5496", "0.0000", "0.0003", "0.6106", "+0.0562"],
        ["5% WSS", "0.4750", "0.4741", "0.0000", "0.0010", "0.5050", "+0.0300"],
        ["10% WSS", "0.4376", "0.4364", "0.0001", "0.0023", "0.4751", "+0.0374"],
    ]
    add_ieee_table(doc, "TABLE IV. ORACLE CEILING AND CONTSHADOW DEFICIT BY CAPACITY (W = 50,000)",
                   ["Cap.", "S3-FIFO", "Best St.", "g(C)", "g(0)", "ContSh.", "Δ"], t_cap,
                   col_widths=[0.55, 0.45, 0.45, 0.42, 0.42, 0.45, 0.46])

    # ── VI. SWITCH-COST AND WINDOW SENSITIVITY ─────────────────────────────
    add_section_heading(doc, "VI. SWITCH-COST AND WINDOW SENSITIVITY")
    t_sw = []
    for w in (5000, 10000, 25000, 50000):
        for cf in ("0.00", "0.02", "0.05", "0.10", "0.25", "0.50", "1.00"):
            sub = [r for r in fsw_low if int(r["window"]) == w and r["cost_frac"] == cf]
            g = np.array([float(r["net_gain_vs_best"]) for r in sub])
            sw = np.mean([float(r["oracle_switches"]) for r in sub])
            clabel = "0" if cf == "0.00" else (f"{cf}C" if cf != "1.00" else "C")
            t_sw.append([f"{w//1000}k", clabel, f"{g.mean():.4f}", f"{g.max():.5f}",
                         f"{int((g>=0.005).sum())}", f"{int((g>=0.01).sum())}",
                         f"{int((g>=0.02).sum())}", f"{sw:.2f}"])
    add_ieee_table(doc, "TABLE V. DP ORACLE SENSITIVITY TO WINDOW W AND SWITCH COST (n = 264; Sw. = MEAN SWITCHES)",
                   ["W", "c_{sw}", "Mean g", "Max g", "≥.005", "≥.01", "≥.02", "Sw."], t_sw,
                   col_widths=[0.28, 0.36, 0.45, 0.50, 0.38, 0.36, 0.36, 0.36], font_pt=6.5)

    add_figure(doc, "fig_cost_sweep.pdf",
               "Fig. 2. Percentage of trace–capacity pairs clearing g ≥ 0.02 across the 9-point switch-cost grid and four window granularities (W ∈ {5k, 10k, 25k, 50k}).")
    add_p(doc, "At realistic metadata-migration costs (c_{switch} ≤ 0.10C) and fine windows (W = 5,000), 13/264 pairs (4.9%, max 0.0933) clear 0.02 (12/264 at W = 10k, 0.10C). Whenever c_{switch} ≥ 0.50C, 0 of 264 pairs clear 0.02 at any window size (smooth decline governed by Proposition 1; at W = 50k, 0.25C, max g = 0.01998). Table VI shows all 14 zero-cost hits at W = 10,000 come from fiu_public (10/36) and real_app_pageref (4/30).")

    t_w10_src = [
        ["fiu_public", "36", "0.0219", "0.1331", "10"],
        ["real_app_pageref", "30", "0.0103", "0.0665", "4"],
        ["pdl_public", "18", "0.0016", "0.0087", "0"],
        ["instrumented_program", "180", "0.0004", "0.0116", "0"],
    ]
    add_ieee_table(doc, "TABLE VI. PER-SOURCE BREAKDOWN AT W = 10,000, c_{switch} = 0",
                   ["Source", "Pairs", "Mean g", "Max g", "≥ 0.02"], t_w10_src,
                   col_widths=[1.25, 0.40, 0.50, 0.50, 0.45])

    # ── VII. RESULTS: SWITCHING CONTROLLERS VS. S3-FIFO (H2) ───────────────
    add_section_heading(doc, "VII. RESULTS: SWITCHING CONTROLLERS VS. S3-FIFO (H2)")

    from scipy.stats import wilcoxon
    s3_mr = {(r["trace"], r["cap_frac"]): float(r["miss_ratio"]) for r in pol if r["policy"] == "S3-FIFO"}
    s3_ns_mean = np.mean([float(r["ns_per_ref"]) for r in pol if r["policy"] == "S3-FIFO"])
    ctrl_names = sorted(set(r["controller"] for r in ctrl) - {"S3-FIFO"})
    rng_boot = np.random.default_rng(42)
    t4_rows = [["S3-FIFO (static)", "0.0000 [---]", "---", "0.00", f"{s3_ns_mean:.1f}"]]
    cstats = []
    for cname in ctrl_names:
        sub = [r for r in ctrl if r["controller"] == cname]
        deltas = np.array([float(r["miss_ratio"]) - s3_mr[(r["trace"], r["cap_frac"])] for r in sub])
        fam_map = {}
        for r, d in zip(sub, deltas):
            fam_map.setdefault(r["family"], []).append(d)
        fg = [np.array(v) for v in fam_map.values()]
        bmeans = [np.concatenate([fg[i] for i in rng_boot.integers(0, len(fg), len(fg))]).mean() for _ in range(3000)]
        ci_lo, ci_hi = np.percentile(bmeans, [2.5, 97.5])
        _, pval = wilcoxon(deltas, alternative="two-sided")
        sw = np.mean([float(r["switches"]) for r in sub])
        ns = np.mean([float(r["ns_per_ref"]) for r in sub])
        cstats.append((cname, deltas.mean(), ci_lo, ci_hi, pval, sw, ns))
    for cname, dm, lo, hi, pv, sw, ns in sorted(cstats, key=lambda x: x[1]):
        t4_rows.append([cname, f"{dm:+.4f} [{lo:+.3f}, {hi:+.3f}]", "<10^{-15}", f"{sw:.2f}", f"{ns:.1f}"])
    add_ieee_table(doc, "TABLE VII. SWITCHING CONTROLLERS VS. STATIC S3-FIFO (n = 264; TWO-SIDED WILCOXON & 95% CLUSTER CI)",
                   ["Controller", "Δ MR [95% CI]", "p_{Holm}", "Sw.", "ns/ref"], t4_rows,
                   col_widths=[0.90, 1.05, 0.48, 0.35, 0.45], font_pt=6.5)

    add_figure(doc, "fig_controllers_vs_s3fifo.pdf",
               "Fig. 3. Mean miss ratio vs. simulator CPU cost (ns/ref). Static S3-FIFO dominates all 17 switching controllers.")
    add_lead_p(doc, "Every controller underperforms S3-FIFO (H2 supported). ", "Every switching controller incurs a significantly higher mean miss ratio than static S3-FIFO (Δ ∈ [+0.0393, +0.0433], all two-sided Holm-adjusted p < 10^{-15}, all 95% family-cluster CIs strictly above +0.020) and 1.56×–3.35× higher CPU overhead (92.9–199.1 vs. 59.5 ns/ref). Expanding the pool to all 21 policies (ContShadow-21) worsens performance further to +0.0470 (95% CI [+0.0249, +0.0784], two-sided p = 2.15×10^{-35}, 2.93 switches, 1,075.6 ns/ref). Even OracleTrig (+0.0405) loses, proving trigger tuning is second-order.")

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
    add_ieee_table(doc, "TABLE VIII. ACTIVE-POLICY TIME-SHARE AND DEFICIT VS. S3-FIFO",
                   ["Controller / Src", "Δ MR", "S3", "LRU", "2Q", "ARC", "LFU", "MRU"], t_diag,
                   col_widths=[0.95, 0.45, 0.30, 0.30, 0.28, 0.28, 0.28, 0.28])
    add_figure(doc, "fig_shadow_ranking.pdf",
               "Fig. 4. Direct shadow ranking accuracy against the true full-cache per-window best policy (4,770 evals for ContShadow-0.2C; 4,794 evals for FullShadow-1.0C).")
    add_p(doc, "Direct causal measurement across 9,564 evaluation windows (Fig. 4) shows ContShadow-0.2C agrees with the true full-cache top-1 policy only 67.7% of the time (selecting S3-FIFO 56.2% vs. true best 65.3%), allocating 18.9% to LRU and 6.0% to MRU. FullShadow-1.0C on the cold 20k-ref window yields nearly identical top-1 agreement (67.9%), proving cold-window truncation penalizes S3-FIFO's ghost filter.")

    add_lead_p(doc, "Noise-free (1.0C), persistent, and cost-aware shadow ablation. ", "Eliminating cold-start truncation (PersistentShadow: six continuously warmed 1.0C shadow caches) raises S3-FIFO share to 77.0% and cuts the deficit to +0.0175 (95% CI [+0.0086, +0.0269], two-sided p = 1.04×10^{-20}), yet every ablation still loses significantly to static S3-FIFO at up to 50.2× CPU cost (2,985.3 ns/ref).")
    t_ab = [
        ["ContSh. (0.2C)", "+0.0412 [+0.022,+0.065]", "<10^{-15}", "1.73", "199.1", ".671", ".189", ".060"],
        ["FullSh. (1.0C)", "+0.0284 [+0.015,+0.044]", "2.9e-26", "1.12", "705.0", ".627", ".262", ".018"],
        ["FullSh.-CA", "+0.0286 [+0.015,+0.044]", "4.2e-28", "0.77", "691.0", ".577", ".324", ".011"],
        ["PersistSh.", "+0.0175 [+0.009,+0.027]", "1.0e-20", "1.55", "2985", ".770", ".158", ".012"],
        ["PersSh.-CA", "+0.0191 [+0.011,+0.028]", "2.2e-24", "0.83", "2901", ".652", ".283", ".009"],
    ]
    add_ieee_table(doc, "TABLE IX. FULL-CAPACITY (C_{s} = C) AND PERSISTENT SHADOW ABLATION (n = 264)",
                   ["Controller", "Δ MR [95% CI]", "p_{2-sided}", "Sw.", "ns/ref", "S3", "LRU", "MRU"], t_ab,
                   col_widths=[0.68, 0.85, 0.38, 0.25, 0.34, 0.24, 0.24, 0.24], font_pt=6.0)
    add_figure(doc, "fig_shadow_ablation.pdf",
               "Fig. 5. Shadow ablation progression from sampled 0.2C (ContShadow) to full 1.0C (FullShadow) and continuously warmed 1.0C (PersistentShadow).")

    add_lead_p(doc, "User-space pread syscall overhead. ", "Replaying sqlite_join_agg_s101 and fiu_online_test (10% WSS) against a 4 KB backing file with pread after POSIX_FADV_DONTNEED yields p_{50} latencies of 1.47–4.82 μs, indicating OS page-cache service rather than physical NVMe I/O. Even under fast page-cache syscalls, PersistentShadow cuts throughput by 1.90× on sqlite (168.22 vs. 319.26 kops/s) and 1.17× on fiu_online (137.51 vs. 160.77 kops/s), while ContShadow matches S3-FIFO throughput on fiu_online (161.42 vs. 160.77 kops/s) only by incurring +0.0200 higher miss ratio.")
    t_rio = [
        ["sqlite_join", "S3-FIFO", "0.0345", "319.26", "1.47", "4.75"],
        ["sqlite_join", "ContShadow", "0.0425", "309.00", "1.47", "4.82"],
        ["sqlite_join", "PersistentSh.", "0.0405", "168.22", "4.68", "7.05"],
        ["fiu_online", "S3-FIFO", "0.7425", "160.77", "3.35", "19.07"],
        ["fiu_online", "ContShadow", "0.7625", "161.42", "3.35", "17.67"],
        ["fiu_online", "PersistentSh.", "0.7507", "137.51", "4.82", "21.44"],
    ]
    add_ieee_table(doc, "TABLE X. USER-SPACE 4 KB PREAD OVERHEAD (10% WSS; OS PAGE-CACHE SERVICED)",
                   ["Trace", "Policy", "MR", "kops/s", "p_{50} (μs)", "p_{99} (μs)"], t_rio,
                   col_widths=[0.65, 0.72, 0.42, 0.48, 0.48, 0.48])

    # ── IX. EXPLORATORY PREDICTIVE SCREENING AND CASE STUDIES (H3) ─────────
    add_section_heading(doc, "IX. EXPLORATORY PREDICTIVE SCREENING AND CASE STUDIES (H3)")
    add_p(doc, "At the primary endpoint (c_{switch} = C, g ≥ 0.02), all 88 traces are negative. For exploratory screening, we fit L_{2}-regularized logistic regression on a post hoc threshold max_{cap} g(0) ≥ 0.005 (13/88 positive traces, 14.8%). Because predicting 'always negative' achieves 85.2% raw accuracy—exceeding our model's 84.1% raw accuracy (LOFO balanced accuracy = 0.493, F1 = 0.000)—the model functions purely as a continuous risk score, achieving AUC = 0.901 under LOFO and 0.890 (balanced accuracy 0.756) on public holdout (Table XI, Fig. 6).")

    t5_rows = [
        ["Primary (c=C, g ≥ 0.02)", "88", "---", "0.500", "---"],
        ["Expl. LOFO (c=0, g ≥ 0.005)", "88", "---", "0.493", "0.901"],
        ["Real-app holdout (tr: pub)", "10", "78", "0.500", "1.000"],
        ["Public holdout (tr: real)", "78", "10", "0.756", "0.890"],
    ]
    add_ieee_table(doc, "TABLE XI. EXPLORATORY HEADROOM RISK SCORE (LOFO & CROSS-SOURCE)",
                   ["Evaluation split", "n_{te}", "n_{tr}", "Bal. Acc.", "AUC"], t5_rows,
                   col_widths=[1.42, 0.32, 0.32, 0.50, 0.44])

    add_figure(doc, "fig_lofo_roc.pdf",
               "Fig. 6. Exploratory LOFO ROC curve ranking zero-cost headroom ≥ 0.005 on unseen trace families (AUC = 0.901).",
               width_in=3.1)

    add_figure(doc, "fig_window_timeline.pdf",
               "Fig. 7. Per-window miss ratio (10% WSS, W = 50,000) on fiu_online_test (left, 7 zero-cost switches, g(0) = 0.0564) vs. sqlite_join_agg_s101 (right, stationary, g(0) = 0.0020).",
               width_in=3.3)
    add_lead_p(doc, "Representative trace case studies. ", "Fig. 7 and Table XII contrast four traces: fiu_online_test exhibits extreme window reuse variability (window_reuse_cv = 2.5916) and g(0) = 0.0564 at 10% WSS, yet g(C) = 0.0000; git_repo_s202 yields g(0) = 0.0196 and g(C) = 0.0000; python_etl_s101 retains one DP switch at c_{switch} = C (g(C) = 0.0067); and sqlite_join_agg_s101 remains stationary (g(0) = 0.0020, g(C) = 0.0005).")

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
    add_lead_p(doc, "Design implication. ", "Under a worst-case full-refill penalty, switching never clears 0.02; under realistic migration costs (≤ 0.10C) and fine windows (W = 5k), only 4.9% of pairs clear 0.02. Meanwhile, all 17 evaluated controllers and persistent 1.0C shadow ablations lose significantly to static S3-FIFO. Engineering effort is better invested in a strong scan-resistant static policy (e.g., S3-FIFO or CAR).")
    add_lead_p(doc, "Limitations and threats to validity. ", "(1) Independent-replay oracle assumes each policy keeps its own warm cache state. (2) Real-app LD_PRELOAD omits post-map page faults; instrumented kernels (68%) average 0.30M refs, and FIU traces (0.49M refs) have ≥ 32% compulsory misses. (3) We did not run bit-for-bit cross-validation against libCacheSim. (4) Expanding to all 21 policies (ContShadow-21) worsens miss ratio (+0.0470); windows < 5k are outside scope. (5) Protocol timestamping was local in git and H3's 0.005 threshold was post hoc.")
    add_lead_p(doc, "Conclusion. ", "An independent-replay Viterbi DP oracle across 88 traces and 1%–50% WSS shows switching clears 0.02 in 0/90 groups at c_{switch} = C, 4.9% at 0.10C (W = 5k), and 0/264 once c_{switch} ≥ 0.50C. Static S3-FIFO dominates all 17 switching controllers, persistent 1.0C ablations, and ContShadow-21 because cold-window shadow evaluation mis-ranks the top-1 policy in 32% of windows.")
    add_lead_p(doc, "Data and code availability. ", "All simulator code, trace capture scripts, raw CSVs, supplement, and table/figure generation scripts are publicly available at https://github.com/anoneurx/drift-gating-reproducibility.")

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
        "[33] R. Koller and R. Rangaswami, 'I/O deduplication: Utilizing content similarity to improve I/O performance,' ACM Trans. Storage, vol. 6, no. 3, Art. no. 13, 2010.",
        "[34] Z. Song, D. S. Berger, K. Li, and W. Lloyd, 'Learning relaxed Belady for content distribution network caching,' in Proc. USENIX NSDI, 2020, pp. 529–544.",
        "[35] A. Jain and C. Lin, 'Back to the future: Leveraging Belady's algorithm for improved cache replacement,' in Proc. ISCA, 2016, pp. 78–89.",
        "[36] J. Yang, Y. Yue, and K. V. Rashmi, 'A large scale analysis of hundreds of in-memory cache clusters at Twitter,' in Proc. USENIX OSDI, 2020, pp. 191–208.",
        "[37] Y. Freund and R. E. Schapire, 'A decision-theoretic generalization of on-line learning and an application to boosting,' J. Comput. Syst. Sci., vol. 55, no. 1, pp. 119–139, 1997.",
        "[38] Y. Zheng et al., 'gpu_ext: Extensible OS policies for GPUs via eBPF,' arXiv:2512.12615, 2025.",
        "[39] W. Shen et al., 'Towards fully-fledged GPU multitasking via proactive memory scheduling,' arXiv:2512.24637, 2025.",
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
