#!/usr/bin/env python3
"""Update Drift_Gating_Final_IEEE.docx and Drift_Gating_Final_IEEE.pdf in IEEE 2-column format."""
import csv
import shutil
import subprocess
from collections import Counter
from pathlib import Path
import numpy as np
import scipy.stats as stats

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RESULTS = HERE / "results"
TEX_DIR = ROOT / "drift_gating_latex_source"
FIG_DIR = TEX_DIR / "figs"
TMP_FIGS = Path("/tmp/ieee_figs")
TMP_FIGS.mkdir(parents=True, exist_ok=True)


def load_csv(name):
    with open(RESULTS / name, newline="") as fh:
        return list(csv.DictReader(fh))


def set_font(run, size_pt, bold=False, italic=False, color=None):
    run.font.name = "Times New Roman"
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic
    if color is not None:
        run.font.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rFonts.set(qn(attr), "Times New Roman")


def add_p(doc, text="", align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=3,
          line_spacing=1.05, first_indent=0):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing
    if first_indent:
        pf.first_line_indent = Pt(first_indent)
    if text:
        r = p.add_run(text)
        set_font(r, 9.0)
    return p


def add_section_heading(doc, text):
    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=7, space_after=3)
    r = p.add_run(text)
    set_font(r, 9.5, bold=True)
    return p


def add_lead_p(doc, lead, body_text, italic_lead=True, bold_lead=True):
    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=1, space_after=3)
    r1 = p.add_run(lead)
    set_font(r1, 9.0, bold=bold_lead, italic=italic_lead)
    r2 = p.add_run(body_text)
    set_font(r2, 9.0)
    return p


def set_cell_margins(cell, top=25, bottom=25, left=45, right=45):
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
    r = cap.add_run(caption)
    set_font(r, 7.5, bold=True)

    tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.autofit = False
    # Header
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
        run = p.add_run(h)
        set_font(run, 7.5, bold=True)
    set_row_borders(hdr_row, top=8, bottom=4)

    # Data rows
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
            run = p.add_run(str(val))
            set_font(run, 7.5, bold=(i == len(rows) - 1 and str(row_data[0]).startswith("Total")))
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
    r = cap.add_run(caption)
    set_font(r, 7.5)


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

    # Continuous section break to 2-column IEEE body
    sec2 = doc.add_section(WD_SECTION.CONTINUOUS)
    configure_margins(sec2)
    set_two_columns(sec2, num_cols=2, space_twips=317)

    # ── Abstract & Index Terms ─────────────────────────────────────────────
    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=2, space_after=3)
    set_font(p.add_run("Abstract—"), 8.5, bold=True, italic=True)
    set_font(p.add_run(
        "Dynamic policy switching is a recurring design pattern in adaptive page replacement: detect a workload shift, "
        "then switch to a better-matched policy. We ask the prior ceiling question: how much could any switching controller "
        "ever gain? We answer it with an exact Viterbi dynamic-programming (DP) hindsight oracle across 88 traces "
        "(30 trace families across real-application page references, instrumented kernels, and public FIU/PDL traces) at "
        "three working-set-relative capacities (1%, 5%, 10% WSS) against 21 static and adaptive baselines. When paying a "
        "full-cache-refill switch penalty (c_switch = C), 0 of 90 family–capacity groups clear our worthwhile-gain threshold "
        "(>= 0.02 net miss-ratio reduction on at least two-thirds of traces); the mean net oracle gain over the best static "
        "policy is 0.0001 (median 0.0000, maximum 0.0067), and even with zero switch penalty only 2 of 264 trace–capacity "
        "pairs (0.8%) clear 0.02. Static S3-FIFO achieves the lowest overall miss ratio (0.4890 at 59.5 ns/ref) and is never "
        "beaten by any of 17 switching controllers across CUSUM, Page–Hinkley, ADWIN, periodic, random, oracle-window, or "
        "continuous-shadow designs (all +0.0393 to +0.0433 higher miss ratio; Holm-adjusted p = 1.000; 92.9–199.1 ns/ref). "
        "In an exploratory analysis of zero-cost headroom (>= 0.005), a logistic rule using observable trace features predicts "
        "unseen-family headroom with 84.1% leave-one-family-out accuracy (AUC = 0.901). For adaptive cache designers, discrete "
        "policy switching rarely pays once switch costs and strong static baselines are accounted for."
    ), 8.5, bold=True)

    p = add_p(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=2, space_after=4)
    set_font(p.add_run("Index Terms—"), 8.5, bold=True, italic=True)
    set_font(p.add_run("page replacement, cache replacement, drift detection, policy switching, hindsight oracle, measurement study"), 8.5, bold=True)

    # ── I. INTRODUCTION ────────────────────────────────────────────────────
    add_section_heading(doc, "I. INTRODUCTION")
    add_p(doc, "Page replacement determines which memory pages are evicted when physical memory is full. Because workloads mix phases with distinct access patterns—sequential scans, hot-object reuse, and random I/O—a single static policy is not optimal at every instant. This observation has motivated decades of adaptive replacement work, from SEQ [1] and EELRU [2] through ARC [3], LeCaR [4], CACHEUS [5], and recent learned policies [6].")
    add_p(doc, "A recurring architecture in this literature is discrete policy switching: monitor the workload, detect a drift or phase boundary, evaluate candidate policies, and switch to a better-matched policy. Each switch carries a state-migration or cache-rewarm cost, while the hoped-for benefit is a lower miss ratio in the new regime. Whether that benefit exceeds the cost in realistic workloads—especially against modern static baselines such as S3-FIFO [7] and SIEVE [8]—is rarely quantified as an upper bound.")
    add_p(doc, "We pose one concrete question: when, if ever, does switching policies beat the best static policy once switch costs are counted? We answer it by computing an exact hindsight oracle—the optimal per-window policy schedule found by dynamic programming—and comparing it against the best no-switch policy on the same trace. The oracle upper-bounds every possible online switching controller; if the oracle does not clear a worthwhile threshold, no online controller can.")
    add_lead_p(doc, "Protocol. ", "We recorded three hypotheses (H1–H3), endpoints, and the smallest worthwhile gain (>= 0.02 net miss-ratio reduction on at least two-thirds of traces in a family–capacity group) in a local git commit prior to executing the study, without external third-party preregistration; accordingly, we treat the study as post hoc.")
    add_lead_p(doc, "Traces. ", "We evaluate 88 traces spanning 30 families and four sources (Table I): (i) 10 real-application page-level traces captured via an LD_PRELOAD tracer on SQLite workloads, git repository operations, and a Python ETL pipeline; (ii) 60 instrumented-program page traces across 15 algorithmic kernels; (iii) 12 public FIU block-I/O traces [9]; and (iv) 6 public PDL storage/cache traces [9]. Every trace is evaluated at capacities 1%, 5%, and 10% of its working-set size (WSS), yielding 264 trace–capacity pairs.")

    # Table I: Sources
    src_labels = {
        "real_app_pageref": "Real-app (SQLite, git, Python)",
        "instrumented_program": "Instrumented kernels",
        "fiu_public": "Public FIU block-I/O",
        "pdl_public": "Public PDL storage/cache",
    }
    t1_rows = []
    for src in ("real_app_pageref", "instrumented_program", "fiu_public", "pdl_public"):
        sub = [m for m in manifest if m["source"] == src]
        fams = len(set(m["family"] for m in sub))
        refs_m = np.mean([int(m["refs"]) for m in sub]) / 1e6
        wss_med = np.median([int(m["wss"]) for m in sub])
        t1_rows.append([src_labels[src], fams, len(sub), f"{refs_m:.2f}M", f"{wss_med:,.0f}"])
    t1_rows.append([
        "Total",
        len(set(m["family"] for m in manifest)),
        len(manifest),
        f"{np.mean([int(m['refs']) for m in manifest])/1e6:.2f}M",
        f"{np.median([int(m['wss']) for m in manifest]):,.0f}",
    ])
    add_ieee_table(doc, "TABLE I. TRACE CORPUS SUMMARY (88 TRACES, 30 FAMILIES)",
                   ["Source", "Fam.", "Tr.", "Refs", "WSS"], t1_rows,
                   col_widths=[1.55, 0.35, 0.32, 0.48, 0.55])

    add_lead_p(doc, "Baselines. ", "We implement 21 policies in a single C++ simulator: S3-FIFO [7], SIEVE [8], ARC [3], CAR [10], LIRS [11], W-TinyLFU [12], 2Q [13], CLOCK-Pro [14], LeCaR [4], CACHEUS [5], LHD [15], DIP [16], LPR-style [17], 3L-style [6], MGLRU-style [18], LRB-style (online SGD), LRU, FIFO, CLOCK, LFU-aging, and MRU.")
    add_lead_p(doc, "Contributions. ", "(1) An exact DP oracle ceiling across 88 traces and three capacities with both full-refill (c_switch = C) and zero-cost (c_switch = 0) switch penalties; (2) A matched-cost comparison of 17 switching controllers against static S3-FIFO; (3) An unseen-family predictive rule evaluated via leave-one-family-out (LOFO) and cross-source holdout; (4) A fully reproducible artifact package.")

    # ── II. BACKGROUND AND RELATED WORK ────────────────────────────────────
    add_section_heading(doc, "II. BACKGROUND AND RELATED WORK")
    add_lead_p(doc, "Adaptive and learned replacement. ", "Classical adaptive policies such as SEQ [1], EELRU [2], ARC [3], CAR [10], and CLOCK-Pro [14] adjust eviction priorities internally within a single algorithm rather than switching among heterogeneous policies. LeCaR [4] and CACHEUS [5] blend or switch between recency and frequency experts via online learning, while DIP [16] duels insertion policies using set sampling. Acme [19] maintains a shadow cache for an alternative mode and switches on significance tests. Modern static designs such as S3-FIFO [7] and SIEVE [8] achieve scan resistance and low overhead without multi-policy switching.")
    add_lead_p(doc, "Drift detection and shadow evaluation. ", "Sequential detectors such as CUSUM [20], Page–Hinkley [20], and ADWIN [21] originate in supervised streaming [22], where true labels exist. In page replacement, only the policy-dependent miss stream is observable. To rank candidate policies without full simulation, SHARDS [23] and miniature simulations [24] use sampled shadow caches. We enforce C_s = min(floor(0.2 C), max(8, floor(0.5 D_w))) where D_w is the per-window sampled distinct-page count, guaranteeing C_s / D_w < 1.")
    add_lead_p(doc, "Hindsight oracles. ", "Belady's MIN [25] bounds single-page eviction. By contrast, our per-window Viterbi DP oracle bounds policy-switching controllers over a fixed candidate pool, accounting for explicit switching penalties.")

    # ── III. ORACLE AND EXPERIMENTAL DESIGN ────────────────────────────────
    add_section_heading(doc, "III. ORACLE AND EXPERIMENTAL DESIGN")
    add_lead_p(doc, "Simulator and exact DP oracle. ", "Our standalone simulator pathA_sim executes all 21 policies under identical trace-driven replay and measures CPU time via CLOCK_PROCESS_CPUTIME_ID. After warming up for min(100,000, floor(0.1 n)) references, the remaining trace is partitioned into non-overlapping windows of W = 50,000 references (with W = 100,000 sensitivity on long traces). Using Viterbi DP in O(T P^2) time, we find the policy sequence minimizing total misses plus c_switch per switch, for both c_switch = C (one full cache refill) and c_switch = 0 (ideal zero-cost ceiling). Net oracle gain is g = (M_best - M_oracle) / n_eval.")
    add_lead_p(doc, "Switching controllers. ", "We evaluate 17 switching controllers against static S3-FIFO: CUSUM, Page–Hinkley, ADWIN, Periodic, and Random at three shadow-evaluation budgets (low, med, high), plus OracleTrig (window boundaries) and ContShadow (all 21 shadow caches continuously). Controllers incur natural re-warming misses whenever the active policy changes.")

    # ── IV. RESULTS: EXACT DP ORACLE CEILING (H1) ──────────────────────────
    add_section_heading(doc, "IV. RESULTS: EXACT DP ORACLE CEILING (H1)")

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
    add_ieee_table(doc, "TABLE II. EXACT DP ORACLE NET GAIN OVER BEST STATIC POLICY",
                   ["Source (Cost)", "n", "Mean g", "p90 g", "Max g", ">=0.02"], t2_rows,
                   col_widths=[1.05, 0.30, 0.48, 0.45, 0.48, 0.48])

    add_figure(doc, "fig_oracle_ceiling.pdf",
               "Fig. 1. Mean and maximum net oracle gain across trace sources for c_switch = C and c_switch = 0 (W = 50,000). Even the zero-cost ceiling rarely exceeds the 0.02 worthwhile-gain threshold.")

    add_lead_p(doc, "Switching rarely clears the threshold (H1 confirmed). ", "When paying the full-refill switch cost (c_switch = C), 0 of 90 family–capacity groups meet the worthwhile-gain criterion (>= 0.02 on >= 2/3 of traces). Across all 264 pairs at W = 50,000, mean g = 0.0001, median g = 0.0000, p90 = 0.0000, and the single largest net gain is 0.0067 (python_etl_s101 at 10% WSS). Only 4 of 264 pairs exhibit non-zero net gain; on the remaining 260 pairs, the optimal DP schedule makes zero switches. Results at W = 100,000 are identical (mean 0.0001, max 0.0067, 0/264 >= 0.02).")
    add_lead_p(doc, "Zero-cost ceiling and static dominance. ", "Removing the switch penalty (c_switch = 0) yields mean g = 0.0012, median 0.0000, p90 = 0.0020, with only 2 of 264 pairs (0.8%) reaching 0.02 (fiu_online.cs.fiu.edu_test at 10% WSS: 0.0564, and 5% WSS: 0.0208). Across all 264 pairs, S3-FIFO is the single best static policy on 176 pairs (66.7%) and achieves the lowest mean miss ratio (0.4890 at 59.5 ns/ref), followed by CAR (0.5151), ARC (0.5189), and 2Q (0.5192) (Table III).")

    pol_mr, pol_ns = {}, {}
    for r in pol:
        pol_mr.setdefault(r["policy"], []).append(float(r["miss_ratio"]))
        pol_ns.setdefault(r["policy"], []).append(float(r["ns_per_ref"]))
    best_counts = Counter(r["best_static"] for r in c_rows)
    sel_pols = ["S3-FIFO", "CAR", "ARC", "2Q", "W-TinyLFU", "LIRS", "LeCaR", "CLOCK", "CACHEUS", "LRU", "SIEVE"]
    t3_rows = [[p, f"{np.mean(pol_mr[p]):.4f}", f"{np.median(pol_mr[p]):.4f}", best_counts[p], f"{np.mean(pol_ns[p]):.1f}"]
               for p in sel_pols]
    add_ieee_table(doc, "TABLE III. SELECTED STATIC POLICIES ACROSS 264 PAIRS",
                   ["Policy", "Mean MR", "Med. MR", "Best", "ns/ref"], t3_rows,
                   col_widths=[0.95, 0.60, 0.60, 0.45, 0.55])

    # ── V. RESULTS: SWITCHING CONTROLLERS VS. S3-FIFO (H2) ─────────────────
    add_section_heading(doc, "V. RESULTS: SWITCHING CONTROLLERS VS. S3-FIFO (H2)")

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
    add_ieee_table(doc, "TABLE IV. SWITCHING CONTROLLERS VS. STATIC S3-FIFO (n = 264)",
                   ["Controller", "Delta MR", "p_Holm", "Sw.", "ns/ref"], t4_rows,
                   col_widths=[1.05, 0.58, 0.50, 0.42, 0.55])

    add_figure(doc, "fig_controllers_vs_s3fifo.pdf",
               "Fig. 2. Mean miss ratio vs. simulator CPU cost (ns/ref). Static S3-FIFO dominates all 17 switching controllers on both accuracy and CPU overhead.")

    add_lead_p(doc, "No controller beats S3-FIFO (H2 confirmed). ", "Every switching controller incurs a higher mean miss ratio than static S3-FIFO (Delta in [+0.0393, +0.0433], Holm-adjusted [26], [27] p = 1.000 for all 17) and higher CPU overhead (92.9–199.1 ns/ref vs. 59.5 ns/ref for S3-FIFO). Even ContShadow, which evaluates all 21 shadow caches continuously (199.1 ns/ref, 3.35x S3-FIFO's CPU cost), loses by +0.0412 miss ratio due to imperfect shadow ranking and switch-induced re-warming.")

    # ── VI. PREDICTIVE RULE FOR UNSEEN FAMILIES (H3) ───────────────────────
    add_section_heading(doc, "VI. PREDICTIVE RULE FOR UNSEEN FAMILIES (H3)")
    add_p(doc, "We extract 11 purely observable trace features prior to cache simulation: working-set density (wss_per_ref, top1_share, top10_share, entropy_bits), reuse-distance dispersion (reuse_cv), and temporal non-stationarity across 50,000-reference windows (uniq_window_cv, window_turnover_mean, window_turnover_max, window_reuse_cv, half_unique_diff, prefix20_turnover).")
    add_lead_p(doc, "Primary and exploratory endpoints. ", "Because 0/90 family–capacity groups clear the >= 0.02 threshold at c_switch = C, the primary binary target is uniformly negative (trivial LOFO accuracy 1.000, AUC undefined). To test whether observable features predict the rare traces with any zero-cost headroom, we fit an L2-regularized logistic regression to predict max_cap g_(c=0) >= 0.005 (13/88 positive traces). Under strict leave-one-family-out (LOFO) cross-validation, the model achieves 84.1% accuracy and AUC = 0.901 (Table V, Fig. 3), and 0.890–1.000 AUC on cross-source holdouts.")

    t5_rows = [
        ["Primary (c=C, g>=0.02)", "88", "---", "1.000", "---"],
        ["Expl. LOFO (c=0, g>=0.005)", "88", "---", "0.841", "0.901"],
        ["Real-app holdout (tr: pub)", "10", "78", "0.600", "1.000"],
        ["Public holdout (tr: real)", "78", "10", "0.654", "0.890"],
    ]
    add_ieee_table(doc, "TABLE V. UNSEEN-FAMILY PREDICTIVE RULE (LOFO & CROSS-SOURCE)",
                   ["Evaluation split", "n_te", "n_tr", "Acc.", "AUC"], t5_rows,
                   col_widths=[1.45, 0.35, 0.35, 0.45, 0.45])

    add_figure(doc, "fig_lofo_roc.pdf",
               "Fig. 3. Exploratory LOFO ROC curve predicting zero-cost headroom >= 0.005 on unseen trace families (AUC = 0.901).",
               width_in=3.1)

    add_p(doc, "The strongest standardized predictors are window_reuse_cv (+0.2808), uniq_window_cv (+0.1843), entropy_bits (+0.1778), and window_turnover_max (+0.1383). Traces with stable working sets and skewed hot-object reuse have negligible headroom.")

    # ── VII. DISCUSSION AND THREATS TO VALIDITY ────────────────────────────
    add_section_heading(doc, "VII. DISCUSSION AND THREATS TO VALIDITY")
    add_lead_p(doc, "Design implication. ", "Across 88 traces, discrete policy switching never pays off against S3-FIFO once switch costs are counted, and even zero-cost switching helps in fewer than 1% of configurations. Engineering effort is better invested in a single scan-resistant, low-overhead policy (e.g., S3-FIFO, CAR, or SIEVE) than in drift detectors and multi-policy switching controllers.")
    add_lead_p(doc, "Limitations. ", "(1) Our real-application traces cover SQLite, git, and Python ETL; production kernel page-cache workloads could behave differently. (2) Trace replay omits kernel lock contention and prefetching. (3) Although c_switch = C is conservative, our c_switch = 0 bound proves the null ceiling is not an artifact of the penalty model. (4) Our protocol was timestamped locally in git rather than in an external registry.")

    # ── VIII. CONCLUSION ───────────────────────────────────────────────────
    add_section_heading(doc, "VIII. CONCLUSION")
    add_p(doc, "An exact DP hindsight oracle across 88 traces, 30 families, and three capacities shows that discrete policy switching clears a 0.02 net miss-ratio gain in 0 of 90 family–capacity groups when paying switch costs, and in only 0.8% of trace–capacity pairs even at zero switch cost. Static S3-FIFO (0.4890 mean miss ratio, 59.5 ns/ref) dominates all 17 switching controllers on both accuracy and CPU overhead. Observable temporal non-stationarity features predict the small pockets of zero-cost headroom on unseen families (AUC = 0.901).")

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
