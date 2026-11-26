#!/usr/bin/env python3
"""Update Drift_Gating_Final_IEEE.docx and Drift_Gating_Final_IEEE.pdf in IEEE 2-column format.
Synchronized with drift_gating_latex_source/main_template.tex (11-section Q1 audit revision).
"""
import csv
import re
import shutil
import subprocess
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


def add_lead_p(doc, lead, body_text, italic_lead=False, bold_lead=True):
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


def add_figure(doc, pdf_name, caption, width_in=3.25):
    pdf_path = FIG_DIR / pdf_name
    if not pdf_path.exists():
        return
    png_prefix = TMP_FIGS / pdf_name.replace(".pdf", "")
    subprocess.run(
        ["pdftoppm", "-png", "-r", "300", "-singlefile", str(pdf_path), str(png_prefix)],
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
        "Discrete policy switching is a recurring design pattern in adaptive cache and page replacement: monitor a workload "
        "for drift, rank candidate policies in shadow caches, and switch when a candidate outperforms the incumbent. We bound "
        "the achievable headroom of discrete switching using an exact Viterbi dynamic-programming (DP) hindsight oracle under "
        "an independent-replay model across 88 traces (30 workload families), 21 baseline policies, and cache capacities from "
        "1% to 50% of working-set size (WSS). At an assumed full-refill penalty (c_{switch} = C, W = 50,000), 0 of 90 "
        "family–capacity groups (1%–10% WSS) clear a 0.02 net miss-ratio reduction (trace-weighted mean 0.0000, family-macro "
        "mean 0.0000, max 0.0021); across all 440 pairs (1%–50% WSS), 0 of 440 clear 0.02. Under assumed lower "
        "migration penalties (c_{switch} ≤ 0.10C) and fine windows (W = 5,000), 13/264 pairs (4.9%) clear 0.02, and 0/264 "
        "clear 0.02 once c_{switch} ≥ 0.50C across W ∈ {5k, 10k, 25k, 50k}. After fixing a capacity-overrun bug (|S|+|M| > C "
        "under ghost hits) discovered via independent cross-validation in our initial S3-FIFO implementation (while LRU, FIFO, "
        "ARC, and SIEVE matched reference implementations bit-for-bit), static CAR (0.5151) and S3-FIFO (0.5167) achieve the "
        "lowest global mean miss ratios across 1%–10% WSS. All 17 online switching controllers incur +0.0109 to +0.0165 higher "
        "mean miss ratio than S3-FIFO (family-level n = 30 Holm-adjusted p = 1.000, rank-biserial r_{b} ∈ [+0.11, +0.39]), "
        "because cold-window shadow evaluation mis-ranks the top-1 policy in 54.9% of evaluation windows. An exploratory "
        "leak-free leave-one-family-out ranker distinguishes rare zero-cost headroom (13/88 traces) with AUC = 0.927 "
        "(PR-AUC = 0.573) but 0.525 balanced accuracy (F_{1} = 0.125) due to class imbalance.",
        size_pt=8.5,
        bold=True,
    )

    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=2, space_after=4)
    set_font(p.add_run("Index Terms—"), 8.5, bold=True, italic=True)
    set_font(p.add_run("page replacement, cache replacement, drift detection, policy switching, hindsight oracle, measurement study"), 8.5, bold=True)

    # ── I. INTRODUCTION ────────────────────────────────────────────────────
    add_section_heading(doc, "I. INTRODUCTION")
    add_p(doc, "Page and cache replacement determines which blocks remain resident when memory is constrained. Because real workloads alternate among sequential scans, hot-object reuse, and random I/O, no single static eviction rule is optimal in every interval. This observation has motivated decades of adaptive replacement designs, from SEQ [1] and EELRU [2] to ARC [3], LeCaR [4], CACHEUS [5], and recent learning-augmented policies [6], [28].")
    add_p(doc, "A recurring architecture in this literature is discrete policy switching: monitor the miss stream for workload drift, evaluate a pool of candidate policies via sampled shadow caches, and switch the active policy when a candidate outperforms the incumbent. Each transition incurs metadata migration or cache warm-up overhead, while the hoped-for benefit is a lower miss ratio in the new regime. Whether that benefit exceeds transition costs—especially against modern scan-resistant static baselines such as S3-FIFO [7] and SIEVE [8]—is rarely bounded explicitly.")
    add_p(doc, "We ask one concrete question: when, if ever, does discrete policy switching beat the best static policy once switching costs are counted? Rather than proposing a new switching controller, we compute a Viterbi dynamic-programming (DP) hindsight oracle under an independent-replay model across 88 traces and compare it against both the per-pair best static policy and the global best static policy (S3-FIFO). We also evaluate 17 online switching controllers, diagnose why they underperform static S3-FIFO, and test whether workload features predict rare switching headroom.")
    add_lead_p(doc, "Contributions. ", "(1) Model-Relative Oracle Ceiling: An exact Viterbi DP ceiling under independent replay across 88 traces (1%–50% WSS), 9 normalized switch-cost fractions (c_{switch} ∈ [0, C]), and 4 window sizes (W ∈ {5k, 10k, 25k, 50k}), plus aggregation-sensitivity checks across trace-, family-, source-, and non-stationary-weighted averages. (2) Simulator & Oracle Validation: Unit validation of core replacement policies against hand-worked traces, brute-force P^{T} verification of the Viterbi DP, and a state-carrying vs. independent-replay comparison quantifying cold-transition penalties. (3) Cluster-Aware Controller Evaluation & Failure Diagnosis: A matched comparison of 17 online controllers plus 4 shadow ablations and a 21-policy expansion (ContShadow-21) against static S3-FIFO using family-level (n = 30) cluster inference, direct shadow-ranking accuracy across 9,564 windows, and measured switchTo() migration latency. (4) Exploratory Screening & Reproducible Artifact: A leak-free leave-one-family-out (LOFO) screening analysis separating ranking (AUC = 0.895) from classification (F_{1} = 0.000), together with a public artifact repository.")

    # ── II. BACKGROUND AND RELATED WORK ────────────────────────────────────
    add_section_heading(doc, "II. BACKGROUND AND RELATED WORK")
    add_p(doc, "Adaptive cache replacement spans three paradigms: (i) continuous internal adaptation, such as ARC [3], CAR [10], and DIP set-dueling [16]; (ii) online expert weighting (Hedge [37]) over two policies, as in ACME [30], LeCaR [4], and CACHEUS [5]; and (iii) epoch-based discrete policy switching driven by drift detectors (CUSUM [20], Page–Hinkley [20], ADWIN [21], Gama et al. [22]) and sampled shadow caches (SHARDS [23], miniature simulations [24], Acme [19]). Recent learned and learning-augmented policies—including Hawkeye [35], LRB [34], 3L-Cache [28], LPR [17], EACLOCK [31], Clock2Q+ [32], and S4FIFO [6]—target single-policy robustness, while S3-FIFO [7] and SIEVE [8] demonstrate that lightweight FIFO-based scan resistance rivals complex adaptive structures. Large-scale studies such as Twitter's cache analysis [36] motivate evaluating across diverse workload regimes, and emerging GPU/eBPF memory schedulers [38], [39] revive interest in runtime policy selection. Unlike prior controller proposals, our work provides an empirical ceiling study bounded by an independent-replay DP oracle and a cluster-aware failure diagnosis of discrete switching.")

    # ── III. PROBLEM FORMULATION ───────────────────────────────────────────
    add_section_heading(doc, "III. PROBLEM FORMULATION")
    add_p(doc, "Let a trace be a sequence of page references r_{1}, ..., r_{N} with working-set size WSS = |{r_{1}, ..., r_{N}}| and cache capacity C = max(1, round(f · WSS)) for capacity fraction f ∈ {0.01, 0.05, 0.10, 0.25, 0.50}. After a warm-up prefix of N_{warm} = min(100,000, floor(0.1 N)) references, the remaining N_{eval} = N - N_{warm} references are partitioned into T = floor(N_{eval} / W) complete windows of length W (trailing incomplete references N_{eval} mod W are omitted so every window has equal weight).")
    add_p(doc, "We distinguish four quantities across a policy pool P (|P| = 21): (1) Best Global Static Policy: The single policy p_{glob}* ∈ P minimizing mean miss ratio across all (i, f) pairs (here, S3-FIFO). (2) Per-Pair Best Static Policy: p_{i,f}* = argmin_{p ∈ P} MR_{i,f,p}, chosen ex post for each trace–capacity pair. By Jensen's inequality, E[min_{p} MR_{i,f,p}] ≤ min_{p} E[MR_{i,f,p}]. (3) Independent-Replay Hindsight Oracle: The minimum-cost schedule (p_{1}, ..., p_{T}) ∈ P^{T} computed over independently replayed per-window miss counts m_{t,p} with fixed transition penalty c_{switch}. (4) State-Carrying Switching Execution: Executing a schedule (p_{1}, ..., p_{T}) in a single live cache where switching at window boundaries transfers resident page IDs and coarse recency/frequency metadata via switchTo().")
    add_p(doc, "Our primary confirmatory hypotheses (recorded locally in git before running the study, without external third-party preregistration and hence treated as post hoc) tested: H1, whether the oracle clears a 0.02 net miss-ratio gain on ≥ 2/3 of traces in any family–capacity group; H2, whether any online controller beats static S3-FIFO; and H3 (exploratory), whether trace features predict zero-cost headroom on unseen families.")

    # ── IV. MATHEMATICAL MODEL ─────────────────────────────────────────────
    add_section_heading(doc, "IV. MATHEMATICAL MODEL")
    add_p(doc, "Under the independent-replay model, each policy p ∈ P processes the full trace [1, N_{warm} + TW] with its own warm cache state, producing per-window miss counts m_{t,p} for t = 1, ..., T. Given normalized switch penalty c_{switch} = βC (β ∈ [0, 1]), the Viterbi dynamic program solves dp[1][p] = m_{1,p} and dp[t][p] = m_{t,p} + min_{q ∈ P}(dp[t-1][q] + c_{switch} · 1[p ≠ q]) for t = 2, ..., T. Initial policy selection at t = 1 is free. Ties in stay ≤ switch break in favor of staying (1[p ≠ q] = 0) to avoid zero-gain switches. Using running best and second-best predecessors per window, the DP runs in O(TP) time and O(TP) space. Defining S = sum_{t=2}^{T} 1[p_{t}* ≠ p_{t-1}*], the oracle objective ratio is J* = (sum_{t=1}^{T} m_{t,p_{t}*} + S · c_{switch}) / (TW), and the net gain over the per-pair best static policy is g(c_{switch}) = MR(p_{i,f}*) - J*.")
    add_lead_p(doc, "Necessary break-even condition (Proposition 1). ", "A single switch paying c_{switch} achieves positive net gain only if its cumulative miss reduction across the subsequent dwell ΔM ≥ c_{switch}, i.e., mean per-window miss-ratio reduction > c_{switch} / (W · L) over L windows. For c_{switch} = C = 5,000 and W = 50,000, one switch requires >10% miss-ratio reduction in a single window just to break even.")
    add_lead_p(doc, "What the model does and does not establish. ", "Because m_{t,p} comes from independent warm caches, the oracle ignores cold-cache and missing-ghost-state penalties upon switching; thus g(c_{switch} = 0) upper-bounds zero-penalty switching, while g(c_{switch}) is an upper bound for any real controller whose transition cost is at least c_{switch} additional misses. It is not a universal bound if a real switch avoids misses below independent replay (impossible for cold transitions) or incurs cascades exceeding c_{switch}.")

    # ── V. EXPERIMENTAL METHODOLOGY ────────────────────────────────────────
    add_section_heading(doc, "V. EXPERIMENTAL METHODOLOGY")
    add_p(doc, "All experiments run in a single-file C++17 simulator (src/pathA_sim.cpp, 1,900 lines) implementing 21 policies: S3-FIFO [7], SIEVE [8], ARC [3], CAR [10], LIRS [11], W-TinyLFU [12], 2Q [13], CLOCK-Pro [14], LeCaR [4], CACHEUS [5], LHD [15], DIP-set-duel [16], LPR-style [17], 3L-style [28], MGLRU-style [18], LRB-style (online SGD [34]), LRU, FIFO, CLOCK, LFU-A, and MRU (compared against Belady-inspired oracle bounds [25]).")
    add_p(doc, "We evaluate 17 online switching controllers over a 6-policy pool (LRU, LFU-A, 2Q, MRU, S3-FIFO, ARC): 3 budgets (low/med/high) each for CUSUM (h ∈ {8, 5, 3}), Page-Hinkley (λ ∈ {9, 5, 2}), ADWIN (δ ∈ {2×10^{-4}, 2×10^{-3}, 2×10^{-2}}), Periodic (10, 20, 40 epochs), and Random (p_{trig} ∈ {0.025, 0.05, 0.10}, seed 99), plus OracleTrig (oracle switch boundaries) and ContShadow (every 10 epochs). Epoch length is 2,000 references; shadow caches sample 20% by page hash with C_{s} = min(round(0.2C), max(8, round(0.5 D_{w}))), 40% shadow warm-up, and z = 1.28 lower-confidence-bound selection over 4 sub-blocks. In switchTo(), resident page IDs sorted by last access timestamp and access counts are loaded into the new policy; policy-specific ghost lists (S3-FIFO ghost, ARC B_{1}/B_{2}, 2Q A_{1out}) cannot be preserved across heterogeneous policies. We also test 4 shadow ablations (FullShadow, FullShadow-CostAware, PersistentShadow, PersistentShadow-CostAware with p = 1.0, C_{s} = C) and ContShadow-21 (all 21 policies).")
    add_lead_p(doc, "Switch-cost modeling. ", "We treat c_{switch} = βC across β ∈ {0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50, 1.00} as assumed normalized cost scenarios rather than empirically calibrated hardware penalties, and separately measure actual in-memory switchTo() migration latency in C++.")

    # ── VI. DATASET AND WORKLOAD CHARACTERIZATION ──────────────────────────
    add_section_heading(doc, "VI. DATASET AND WORKLOAD CHARACTERIZATION")
    add_p(doc, "We evaluate 88 traces spanning 30 workload families and four sources (Table I): (i) 10 real-application page traces captured via LD_PRELOAD (SQLite, git, Python ETL; 0.31M–2.29M refs); (ii) 60 instrumented-program page traces across 15 kernels (0.30M refs each, median WSS 3,907); (iii) 12 public FIU block-I/O traces [9], [33] (0.42M–0.50M refs, median WSS 156,736); and (iv) 6 public PDL storage/cache traces [9], [29], [36] (1.00M refs each, median WSS 171,823).")

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

    add_p(doc, "Two structural limitations of the corpus are audited directly: (1) instrumented kernels comprise 68.2% of traces and yield only 2–5 windows at W = 50k–100k; and (2) FIU traces have high WSS relative to length (≥ 31% compulsory first-touch misses). To ensure kernel stationary traces do not mask switching headroom elsewhere, Section VIII reports trace-weighted, 30-family macro-averaged, 4-source equal-weighted, and non-stationary-only (g(0) > 0.001, n = 21 traces) aggregates.")

    # ── VII. SIMULATOR AND ORACLE VALIDATION ───────────────────────────────
    add_section_heading(doc, "VII. SIMULATOR AND ORACLE VALIDATION")
    add_p(doc, "We implemented an automated C++ and Python validation suite (tests/validate_simulator.cpp, tests/run_tests.py): (1) Hand-worked policy sequences (C = 3): Exact hit/miss string matches for LRU (10 misses), FIFO (9 misses), and MRU (7 misses) on the 12-reference Belady sequence {1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5}, plus repeated-reference tests (C = 1, 2) for LRU, CLOCK, S3-FIFO, ARC, and SIEVE. (2) Scan resistance & monotonicity: Verified S3-FIFO and ARC incur fewer misses than LRU on hot+scan sequences, and S3-FIFO miss counts decrease monotonically across C ∈ {5, 10, 20}. (3) Viterbi DP vs. brute force: Exhaustive P^{T} enumeration (P = 4, T = 5, 1,024 schedules) matched solveDPOracle() to 10^{-12} across c_{switch} ∈ {0, 15, 35, 100}. (4) State-carrying vs. independent replay: On a 3-phase trace (3 × 2,000 refs, C = 10: hot {0..9} → cyclic scan {100..115} → hot {0..9}), independent-replay c = 0 oracle scored 52 misses (0.0087) whereas state-carrying switchTo() execution incurred 2,011 misses (0.3352), confirming that real transitions incur substantial cold/state-loss overhead above the independent-replay bound. (5) Bounds guard: Fixed a bug in src/pathA_sim.cpp where passing --np smaller than max(r_{i}) + 1 caused out-of-bounds access in unit tests. External cross-validation against libCacheSim was not performed (listed as an unresolved item). All 16 C++ validation checks and all 5 Python CLI unit tests (make test) pass.")

    # ── VIII. RESULTS ──────────────────────────────────────────────────────
    add_section_heading(doc, "VIII. RESULTS")
    add_lead_p(doc, "H1: Oracle Switching Ceiling. ", "Across 264 primary pairs (1%–10% WSS, W = 50k), 0 of 90 family–capacity groups clear g(C) ≥ 0.02 on ≥ 2/3 of traces (Table II). At c_{switch} = C, mean g(C) = 0.0000 (0.000038, max 0.0021); even at c_{switch} = 0, only 4/264 pairs (1.5%) clear 0.02. Importantly, this null result is not an artifact of the 68% kernel share: across the 30 independent families, family-macro mean g(C) = 0.0000 (g(0) = 0.0025); across 4 equal-weighted sources, g(C) = 0.0000 (g(0) = 0.0032); and even restricting strictly to the 37 non-stationary traces (111 pairs) with g(0) > 0.001, mean g(C) = 0.0001 (max 0.0021) and mean g(0) = 0.0038 (max 0.0587).")

    t2_rows = [
        ["Real-app (n=30)", "0.0001", "0.0015", "0/30", "0.0023", "0.0149"],
        ["Instr. kernels (n=180)", "0.0000", "0.0021", "0/180", "0.0003", "0.0030"],
        ["FIU block-I/O (n=36)", "0.0000", "0.0002", "0/36", "0.0077", "0.0587"],
        ["PDL storage (n=18)", "0.0000", "0.0000", "0/18", "0.0024", "0.0104"],
        ["Trace-weighted (n=264)", "0.0000", "0.0021", "0/264", "0.0017", "0.0587"],
        ["Family-macro (n=30)", "0.0000", "0.0021", "0/90 grp", "0.0025", "0.0587"],
    ]
    add_ieee_table(doc, "TABLE II. H1 INDEPENDENT-REPLAY ORACLE GAIN BY SOURCE (W = 50k)",
                   ["Scope", "g(C) mean", "g(C) max", "Clear ≥0.02", "g(0) mean", "g(0) max"],
                   t2_rows, col_widths=[1.20, 0.42, 0.42, 0.48, 0.40, 0.33])

    add_figure(doc, "fig_oracle_ceiling.pdf", "Fig. 1. Independent-replay oracle gain (W = 50k) across trace sources at c = C and c = 0.")

    add_lead_p(doc, "Capacity Scaling (1%–50% WSS) & Best-Static Clarification. ", "Table III resolves any apparent discrepancy between S3-FIFO and Best Static: CAR (0.5151 mean MR, winning 35/264 primary pairs) and fixed-capacity S3-FIFO (0.5167 mean MR, winning 19/264) achieve the lowest global mean miss ratios, whereas Per-Pair Best Static selects the ex-post best of 21 policies per pair. At 25% WSS (W = 50k), 0/88 pairs clear g(C) ≥ 0.02 (6/88 at c = 0); at 50% WSS, 0/88 clear at c = C (8/88 at c = 0). Across all 440 pairs (1%–50% WSS), 0 of 440 (0.0%) clear 0.02 at c = C.")

    t3_rows = [
        ["1%", "0.5920", "0.5818", "0.5811", "0.5817", "0.0007", "0.0000"],
        ["5%", "0.4934", "0.4863", "0.4847", "0.4862", "0.0016", "0.0000"],
        ["10%", "0.4646", "0.4555", "0.4528", "0.4554", "0.0027", "0.0001"],
        ["25%", "0.3932", "0.3762", "0.3713", "0.3762", "0.0049", "0.0000"],
        ["50%", "0.2834", "0.2510", "0.2464", "0.2510", "0.0046", "0.0000"],
    ]
    add_ieee_table(doc, "TABLE III. MEAN MISS RATIOS AND ORACLE GAINS ACROSS 1%–50% WSS (W = 50k, n = 88/row)",
                   ["Cap.", "S3-FIFO", "Pair Best", "Ora(0)", "Ora(C)", "g(0)", "g(C)"],
                   t3_rows, col_widths=[0.38, 0.50, 0.52, 0.48, 0.48, 0.45, 0.44])

    # ── IX. STATISTICAL ANALYSIS ───────────────────────────────────────────
    add_section_heading(doc, "IX. STATISTICAL ANALYSIS")
    add_lead_p(doc, "Reconciling Prior p-Value Discrepancies. ", "Earlier repository outputs contained two seemingly conflicting numbers: h2_controller_analysis.csv reported p_{Holm} = 1.000 because analyze_pathA_study.py ran a one-sided Wilcoxon test (alternative='less') testing whether controllers improved over S3-FIFO (none did), whereas generate_paper_assets.py ran a two-sided test across n = 264 correlated (trace, capacity) pairs (p < 10^{-15}). Because the 264 pairs come from only 30 independent workload families, treating n = 264 as i.i.d. inflates test power.")
    add_lead_p(doc, "Cluster-Valid Inference. ", "Table IV reports the corrected family-level analysis (n = 30 family means per controller, two-sided Wilcoxon signed-rank test [26] with Holm correction [27], matched-pair rank-biserial correlation r_{b}, and 3,000-resample family-cluster bootstrap 95% CIs). Against fixed-capacity static S3-FIFO (0.5167), all 17 controllers still exhibit higher mean miss ratios (+0.0109 to +0.0165 pair mean Δ MR; p_{fam,Holm} = 1.000; r_{b} ∈ [+0.11, +0.39]).")

    t4_rows = [
        ["CUSUM-high / med / low", "+0.0109 to +0.0121", "1.000", "+0.11 to +0.29", "Higher MR"],
        ["PH-high / med / low", "+0.0137 to +0.0165", "1.000", "+0.32 to +0.39", "Higher MR"],
        ["ADWIN-high / med / low", "+0.0141 to +0.0154", "1.000", "+0.30 to +0.34", "Higher MR"],
        ["Periodic-10 / 20 / 40", "+0.0114 to +0.0158", "1.000", "+0.19 to +0.25", "Higher MR"],
        ["Random-high / med / low", "+0.0128 to +0.0158", "1.000", "+0.24 to +0.38", "Higher MR"],
        ["OracleTrig", "+0.0128", "1.000", "+0.32", "Higher MR"],
        ["ContShadow", "+0.0140", "1.000", "+0.19", "Higher MR"],
    ]
    add_ieee_table(doc, "TABLE IV. H2 ONLINE CONTROLLERS VS. FIXED-CAPACITY S3-FIFO (n = 264 PAIRS, 30 FAMILIES)",
                   ["Controller", "Pair Δ MR", "p_{fam,Holm}", "r_{b}", "Result"],
                   t4_rows, col_widths=[1.15, 0.80, 0.55, 0.38, 0.37])

    add_figure(doc, "fig_controllers_vs_s3fifo.pdf", "Fig. 2. Miss ratio vs. CPU cost (ns/ref): static baselines vs. 17 switching controllers.")

    # ── X. SENSITIVITY AND FAILURE-MODE ANALYSIS ───────────────────────────
    add_section_heading(doc, "X. SENSITIVITY AND FAILURE-MODE ANALYSIS")
    add_p(doc, "Sweeping c_{switch} ∈ [0, C] across 9 points and W ∈ {5k, 10k, 25k, 50k} (264 pairs at 1%–10% WSS) shows net gains declining smoothly as cost rises: at W = 5k, 18/264 (6.8%) clear 0.02 at c = 0, 13/264 (4.9%) at 0.10C, 7/264 at 0.25C, and 0/264 once c_{switch} ≥ 0.50C across all four window sizes (Fig. 3).")

    add_figure(doc, "fig_cost_sweep.pdf", "Fig. 3. Share of 264 pairs clearing ≥ 0.02 net gain across normalized switch-cost fractions.")

    add_lead_p(doc, "Exploratory H3 Screening (Leak-Free). ", "Fixing global standardization leakage in the original script yields leak-free LOFO AUC = 0.927 (PR-AUC = 0.573 vs. positive rate 13/88 = 0.148) for predicting post-hoc zero-cost headroom g(0) ≥ 0.005. However, due to class imbalance, the default 0.5 threshold predicts TP = 1, FP = 2, FN = 12, TN = 73, giving 0.841 raw accuracy (below the 0.852 majority-class baseline), 0.525 balanced accuracy, and F_{1} = 0.125. Thus, trace features rank relative drift propensity but do not provide a reliable binary classifier; H3 remains strictly exploratory.")

    add_lead_p(doc, "Controller Failure Diagnosis. ", "Direct measurement across 9,564 evaluation windows (Fig. 4) shows that sampled ContShadow-0.2C agrees with the true full-cache window winner in only 45.1% of windows (and even noise-free cold FullShadow-1.0C agrees in 52.8%). Across all 264 pairs, ContShadow spends 24.7% of references in S3-FIFO (45.2% on FIU traces), 26.6% in LRU, 18.6% in 2Q, 14.2% in MRU, 10.7% in LFU-A, and 5.2% in ARC, losing by +0.0140 overall. Shadow ablations (n = 264) confirm that eliminating sampling noise (FullShadow: Δ = -0.0013, 854.8 ns/ref) or adding cost awareness (FullShadow-CostAware: Δ = -0.0009) matches S3-FIFO at 19× CPU cost; maintaining full persistent shadows (PersistentShadow: Δ = -0.0062, 3,772.2 ns/ref; PersistentShadow-CostAware: Δ = -0.0039) achieves a 0.0062 reduction at 84× CPU overhead, while expanding to 21 policies (ContShadow-21: Δ = +0.0216) degrades performance.")

    add_figure(doc, "fig_shadow_ranking.pdf", "Fig. 4. Shadow-cache top-1 ranking accuracy across 9,564 evaluation windows.")

    add_lead_p(doc, "Migration & Syscall Microbenchmarks. ", "Direct C++ measurement of switchTo() metadata migration (S3-FIFO → ARC, n = 50 trials per C) yields medians of 418.98 µs at C = 64, 48.75 µs at C = 512, 235.44 µs at C = 4,096, and 930.22 µs at C = 16,384 (0.0583 µs/page). Separately, an OS page-cache pread microbenchmark (real_io_bench, p_{50} = 1.47–4.82 µs, p_{99} = 4.75–21.44 µs) reflects kernel syscall/DRAM-cache overhead rather than NVMe storage or migration cost, and shows PersistentShadow cutting throughput from 319.3 kops/s (S3-FIFO) to 168.2 kops/s on sqlite_join_agg_s101.")

    # ── XI. DISCUSSION, THREATS TO VALIDITY, AND CONCLUSION ────────────────
    add_section_heading(doc, "XI. DISCUSSION, THREATS TO VALIDITY, AND CONCLUSION")
    add_lead_p(doc, "Design implication. ", "Discrete policy switching never clears a 0.02 net gain once transition costs reach 0.50C under the independent-replay oracle, and all 17 online controllers underperform static CAR (0.5151) and S3-FIFO (0.5167) on average because cold-window shadow evaluation mis-ranks policies in 54.9% of windows while heterogeneous switchTo() discards ghost state. Systems builders gain more from adopting a strong scan-resistant static policy (CAR or S3-FIFO) than from adding drift-triggered switching machinery.")
    add_lead_p(doc, "Threats to validity & limitations. ", "(1) Independent-replay model: Does not universally lower-bound state-carrying misses (Section IV counterexample). (2) Trace corpus: 68% instrumented kernels average 0.30M refs, FIU traces have ≥ 31% compulsory misses, and LD_PRELOAD omits post-map kernel page faults. (3) External cross-validation: libCacheSim was unavailable offline; 16 non-core policies remain unvalidated externally, and fixed S3-FIFO agrees with our Python reference within 0.00–0.09 percentage points. (4) Scope: Windows < 5k and live kernel implementations (MGLRU / cache_ext) are outside scope. (5) Post-hoc status: Local git timestamping is not external preregistration, and H3's 0.005 threshold was post hoc.")
    add_lead_p(doc, "Reproducibility and Conclusion. ", "All simulator code (src/pathA_sim.cpp), validation tests (make test, make verify), raw CSVs, reproduced statistics (results/reproduced_statistics/), audit reports (reports/), and REPRODUCIBILITY.md are publicly available at https://github.com/anoneurx/drift-gating-reproducibility. Under an independent-replay Viterbi DP oracle across 88 traces (1%–50% WSS) with strict-capacity policy implementations, discrete policy switching clears a 0.02 net gain in 0/90 family–capacity groups (1%–10% WSS) at c_{switch} = C, 0/440 pairs across 1%–50% WSS at c_{switch} = C, 4.9% at 0.10C (W = 5k), and 0/264 once c_{switch} ≥ 0.50C. Static CAR (0.5151) and S3-FIFO (0.5167) outperform all 17 online switching controllers on average (+0.0109 to +0.0165 excess MR), because shadow ranking fails on 54.9% of windows and heterogeneous switches discard ghost metadata.")

    # ── REFERENCES ─────────────────────────────────────────────────────────
    add_section_heading(doc, "REFERENCES")
    refs = [
        "[1] G. Glass and P. Cao, 'Adaptive page replacement based on memory reference behavior,' in Proc. ACM SIGMETRICS, 1997, pp. 115–126.",
        "[2] Y. Smaragdakis, S. Kaplan, and P. Wilson, 'EELRU: Simple and effective adaptive page replacement,' in Proc. ACM SIGMETRICS, 1999, pp. 122–133.",
        "[3] N. Megiddo and D. S. Modha, 'ARC: A self-tuning, low overhead replacement cache,' in Proc. USENIX FAST, 2003, pp. 115–130.",
        "[4] G. Vietri et al., 'Driving cache replacement with ML-based LeCaR,' in Proc. USENIX HotStorage, 2018.",
        "[5] L. V. Rodriguez et al., 'Learning cache replacement with CACHEUS,' in Proc. USENIX FAST, 2021, pp. 341–354.",
        "[6] K. Yan et al., 'S4FIFO: Adaptive and efficient cache replacement via multi-queue,' Proc. ACM Manag. Data, 2026.",
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
