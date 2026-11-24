#!/usr/bin/env python3
"""Cross-check the numbers printed in latex/main.tex against raw outputs.

This script does not create data.  It reads the released CSV/text outputs and
compares them with the values written in the manuscript.  Run:

    python3 check_paper_numbers.py

A line prefixed FAIL is a mismatch between the manuscript and a raw artifact.
"""
import csv
import glob
import os
from collections import defaultdict
from statistics import mean

HERE = os.path.dirname(os.path.abspath(__file__))
NONSTABLE = {"abrupt", "gradual", "recurring", "composite"}


def load(name):
    with open(os.path.join(HERE, name)) as fh:
        return list(csv.DictReader(fh))


def latex_fragment(name):
    with open(os.path.join(HERE, "..", "latex", name)) as fh:
        return fh.read()


def drift_fragment(name):
    with open(os.path.join(HERE, "..", "drift_gating_latex_source", name)) as fh:
        return fh.read()


def nonstable(rows):
    return [r for r in rows if r["scenario"] in NONSTABLE]


def mval(rows, method, col="miss_ratio"):
    return mean(float(r[col]) for r in rows if r["method"] == method)


CHECKS = []


def check(claim, expected, actual, tol=0.0006, unit=""):
    if isinstance(expected, str) or isinstance(actual, str):
        ok = str(expected) == str(actual)
    else:
        ok = abs(float(expected) - float(actual)) <= tol
    CHECKS.append((ok, claim, expected, actual, unit))


def main():
    r = nonstable(load("main_study_results.csv"))
    stable = [x for x in load("main_study_results.csv") if x["scenario"] == "stable"]

    # Table VI / abstract / text (main study means).
    for m, exp in [("DA", 0.453), ("LRU", 0.570), ("S3-FIFO", 0.468),
                   ("ContShadow", 0.423), ("OPT", 0.302)]:
        check(f"main-study mean miss, {m}", exp, mval(r, m))
    check("20.5% below LRU", 20.5, 100 * (1 - mval(r, "DA") / mval(r, "LRU")), 0.1, "%")
    check("DA-S3 mean difference", -0.0154, mval(r, "DA") - mval(r, "S3-FIFO"))
    check("DA-ContShadow mean difference", 0.0301,
          mval(r, "DA") - mval(r, "ContShadow"))

    # Table VI per-scenario values.
    for scen in sorted(NONSTABLE):
        sub = [x for x in r if x["scenario"] == scen]
        check(f"{scen} DA miss", {"abrupt": 0.370, "gradual": 0.439,
                                  "recurring": 0.398, "composite": 0.604}[scen],
              mval(sub, "DA"))
        check(f"{scen} ContShadow miss", {"abrupt": 0.365, "gradual": 0.401,
                                          "recurring": 0.384, "composite": 0.541}[scen],
              mval(sub, "ContShadow"))

    # Stable traces: start-up selection, not drift handling.
    for m, exp in [("DA", 0.3071), ("LRU", 0.5186), ("S3-FIFO", 0.3301),
                   ("ContShadow", 0.3065)]:
        check(f"stable mean miss, {m}", exp, mval(stable, m))
    check("stable DA switches", 0.80,
          mean(float(x["switches"]) for x in stable if x["method"] == "DA"), 0.01)
    check("stable DA shadow evals", 1.73,
          mean(float(x["shadow_evals"]) for x in stable if x["method"] == "DA"), 0.01)

    # Ablation (Table VIII).
    abl = {"DA": (0.453, 2.36, 6.47, 67.4),
           "DA-noPurge": (0.453, 2.36, 6.47, 68.5),
           "DA-noS2": (0.456, 2.27, 6.76, 67.9),
           "DA-noShadow": (0.619, 5.05, 0.00, 77.3),
           "DA-noCost": (0.453, 2.36, 6.47, 66.9),
           "DA-noDwell": (0.453, 2.36, 6.47, 67.9),
           "S3-FIFO": (0.468, 0.00, 0.00, 28.5),
           "ContShadow": (0.423, 3.15, 27.39, 133.4)}
    cols = ["miss_ratio", "switches", "shadow_evals", "ns_per_ref"]
    for m, vals in abl.items():
        for col, exp in zip(cols, vals):
            check(f"ablation {m} {col}", exp, mval(r, m, col), 0.06)
    da_ev = mval(r, "DA", "shadow_evals")
    cs_ev = mval(r, "ContShadow", "shadow_evals")
    check("76.4% shadow-eval reduction", 76.4, 100 * (1 - da_ev / cs_ev), 0.1, "%")

    # Repaired synthetic (post hoc design correction): identical to original.
    rep = nonstable(load("main_study_repaired_results.csv"))
    for m in ["DA","LRU","S3-FIFO","ContShadow","OPT"]:
        check(f"repaired synthetic mean miss, {m}", mval(r,m), mval(rep,m))
    check("repaired synthetic DA switches", mval(r,"DA","switches"), mval(rep,"DA","switches"), 0.01)
    check("repaired synthetic DA shadow evals", mval(r,"DA","shadow_evals"), mval(rep,"DA","shadow_evals"), 0.01)

    # Repaired public held-out suffixes: identical to original reselected.
    pub_o = load("public_test_reselected.csv")
    pub_r = load("public_test_reselected_repaired.csv")
    for m in ["LRU","S3-FIFO","DA"]:
        check(f"public repaired held-out miss, {m}", mval(pub_o,m), mval(pub_r,m))
    check("public repaired held-out DA switches",
          mean(int(x['switches']) for x in pub_o if x['method']=='DA'),
          mean(int(x['switches']) for x in pub_r if x['method']=='DA'), 0.01)

    # Repaired holdout: identical means.
    hold_o = load("whole_program_holdout_results.csv")
    hold_r = load("whole_program_holdout_repaired_results.csv")
    for m in ["DA","S3-FIFO","ContShadow","LRU","OPT"]:
        check(f"holdout repaired mean, {m}", mean(float(x[m]) for x in hold_o), mean(float(x[m]) for x in hold_r))

    # Cost comparison (Section V-F).
    for m, exp in [("LRU", 25.1), ("CLOCK", 8.9), ("S3-FIFO", 28.5),
                   ("2Q", 36.8), ("LPR-style", 50.2), ("DA", 67.4),
                   ("ContShadow", 133.4)]:
        check(f"ns/ref, {m}", exp, mval(r, m, "ns_per_ref"), 0.06)
    check("DA/LRU cost ratio", 2.7, mval(r, "DA", "ns_per_ref") /
          mval(r, "LRU", "ns_per_ref"), 0.05, "x")
    check("DA/S3 cost ratio", 2.4, mval(r, "DA", "ns_per_ref") /
          mval(r, "S3-FIFO", "ns_per_ref"), 0.05, "x")

    # Capacity sensitivity (Table IX).
    c500 = nonstable(load("main_study_C500.csv"))
    for m, exp in [("LRU", 0.693), ("2Q", 0.654), ("S3-FIFO", 0.590),
                   ("ContShadow", 0.555), ("DA", 0.580), ("OPT", 0.434)]:
        check(f"C=500 miss, {m}", exp, mval(c500, m))

    # Detection (main study and boundary offsets).
    det = load("main_study_detection.csv")
    det_ns = [x for x in det if x["scenario"] in NONSTABLE]
    bounds = sum(int(x["n_bounds"]) for x in det_ns)
    detected = sum(int(x["detected"]) for x in det_ns)
    spurious = sum(int(x["spurious"]) for x in det_ns)
    check("detected boundaries", 278, detected, 0)
    check("total boundaries", 380, bounds, 0)
    check("detection rate", 73.2, 100 * detected / bounds, 0.05, "%")
    check("non-stable spurious confirmations", 169, spurious, 0)
    check("stable false confirmations after 100k", 1,
          sum(int(x["false_after_100k"]) for x in det), 0)
    check("stable spurious confirmations total", 23,
          sum(int(x["spurious"]) for x in det if x["scenario"] == "stable"), 0)
    for scen, exp_d, exp_s in [("abrupt", 97, 16), ("gradual", 24, 109),
                               ("recurring", 96, 14), ("composite", 61, 30)]:
        sub = [x for x in det_ns if x["scenario"] == scen]
        check(f"{scen} detected", exp_d, sum(int(x["detected"]) for x in sub), 0)
        check(f"{scen} spurious", exp_s, sum(int(x["spurious"]) for x in sub), 0)
    for off, exp_d, exp_s in [(0, 278, 169), (250, 274, 171),
                              (333, 274, 171), (500, 274, 171),
                              (1000, 279, 173), (1370, 281, 173),
                              (1501, 276, 171)]:
        src = "main_study_detection.csv" if off == 0 else f"detection_offset{off}.csv"
        rows = [x for x in load(src) if x["scenario"] in NONSTABLE]
        check(f"offset {off} detected", exp_d,
              sum(int(x["detected"]) for x in rows), 0)
        check(f"offset {off} spurious", exp_s,
              sum(int(x["spurious"]) for x in rows), 0)

    # Diagnostic component activations (Section V-G).
    comp = {x["field"]: int(x["total"])
            for x in load("diag_component_totals.csv")}
    for f, exp in [("purge_active", 47), ("purge_dropped", 39405),
                   ("cost_active", 0), ("dwell_blocked", 0),
                   ("ks_active", 643), ("ks_rejected", 173),
                   ("alarms", 643), ("evals", 570)]:
        check(f"component {f}", exp, comp[f], 0)
    allrows = load("main_study_results.csv")
    check("DA total switches (213, all 110 traces)", 213,
          sum(int(x["switches"]) for x in allrows if x["method"] == "DA"), 0)

    # Public traces (Section V-I, Table X).
    pub = load("public_trace_results.csv")
    for m, exp_miss, exp_ns in [
        ("OPT", 0.4595, 0.0), ("S3-FIFO", 0.5772, 31.7),
        ("2Q", 0.6209, 38.3), ("ARC", 0.6580, 37.0),
        ("LRU", 0.6753, 25.5), ("DA", 0.6753, 82.5),
        ("ContShadow", 0.6753, 180.1), ("FIFO", 0.6808, 17.6)]:
        check(f"public miss, {m}", exp_miss, mval(pub, m))
        check(f"public ns/ref, {m}", exp_ns, mval(pub, m, "ns_per_ref"), 0.06)
    check("public DA shadow evals", 13.50, mval(pub, "DA", "shadow_evals"), 0.01)
    check("public ContShadow shadow evals", 48.33,
          mval(pub, "ContShadow", "shadow_evals"), 0.01)
    check("public shadow saving", 72.0,
          100 * (1 - mval(pub, "DA", "shadow_evals") /
                 mval(pub, "ContShadow", "shadow_evals")), 0.5, "%")
    check("public DA switches", 0,
          sum(int(x["switches"]) for x in pub if x["method"] == "DA"), 0)
    pd = load("public_diagnostic_summary.csv")
    check("public diagnostics traces", 6, len(pd), 0)
    check("public all initial picks LRU", 6,
          sum(1 for x in pd if int(x["initial_pick"]) == 0), 0)
    for x in pd:
        tots = [float(x[f"first_eval_tot{i}"]) for i in range(5)]
        check(f"{x['scenario'][:18]} tied shadow tots", 0,
              max(tots) - min(tots), 0)
        check(f"{x['scenario'][:18]} CUSUM alarm", 1,
              int(float(x["max_Sp"]) > 5 or float(x["max_Sn"]) > 5), 0)
    frozen = load("public_test_frozen.csv")
    rese = load("public_test_reselected.csv")
    check("public frozen held-out miss", 0.66834,
          mean(float(x["miss_ratio"]) for x in frozen if x["method"] == "DA"))
    check("public reselected held-out miss", 0.66834,
          mean(float(x["miss_ratio"]) for x in rese if x["method"] == "DA"))
    check("public held-out switches frozen", 0,
          sum(int(x["switches"]) for x in frozen if x["method"] == "DA"), 0)
    check("public held-out switches reselected", 0,
          sum(int(x["switches"]) for x in rese if x["method"] == "DA"), 0)

    # Cost model and fault calibration.
    cm = {x["quantity"]: x["value"] for x in load("cost_model.csv")}
    check("break-even ratio R", 783.28, float(cm["break_even_ratio_R"]), 0.01)
    check("direct break-even (ns)", 2196.2,
          float(cm["direct_break_even_miss_cost"]), 0.1)
    check("S3/DA total-time crossover (us)", 2.52,
          float(cm["S3_vs_DA_total_time_crossover_us"]), 0.01)
    bs = {x["quantity"]: x for x in load("cost_model_bootstrap.csv")}
    check("R bootstrap point", 783.28,
          float(bs["break_even_ratio_R"]["point"]), 0.01)
    check("R bootstrap CI low", 426.3,
          float(bs["break_even_ratio_R"]["ci95_low"]), 0.5)
    check("R bootstrap CI high", 1186.7,
          float(bs["break_even_ratio_R"]["ci95_high"]), 0.5)
    check("break-even us bootstrap point", 2.1962,
          float(bs["direct_break_even_miss_cost_us"]["point"]), 0.0001)
    check("break-even us CI low", 1.4407,
          float(bs["direct_break_even_miss_cost_us"]["ci95_low"]), 0.0001)
    check("break-even us CI high", 4.0587,
          float(bs["direct_break_even_miss_cost_us"]["ci95_high"]), 0.0001)
    bench = {x["quantity"]: x for x in load("bench_eval_timing.csv")}
    check("direct eval mean ns (2.46 ms)", 2456186.5,
          float(bench["mean_ns_per_eval"]["value"]), 1)
    check("direct eval median ns (2.33 ms)", 2333017.3,
          float(bench["median_ns_per_eval"]["value"]), 1)
    check("implied eval ns (1.72 ms)", 1720219.4,
          float(cm["implied_shadow_eval_cost"]), 0.5)
    fl = open(os.path.join(HERE, "fault_latency_results.txt")).read()
    check("first-touch minor fault (us)", 1.980,
          float([l for l in fl.splitlines() if l.startswith("first_touch_minor_fault_us=")][0].split("=")[1]), 0.001)
    check("refault minor fault (us)", 2.057,
          float([l for l in fl.splitlines() if l.startswith("refault_minor_fault_us=")][0].split("=")[1]), 0.001)

    # Total-time envelope (re-analysis of the same frozen seed-5001 results).
    env = {x["quantity"]: x["value"] for x in load("phase5/envelope_summary.csv")}
    check("envelope CLOCK end (us)", 0.215539,
          float(env["lower_envelope_CLOCK_end"]), 1e-6)
    check("envelope S3 start (us)", 0.215539,
          float(env["lower_envelope_S3-FIFO_start"]), 1e-6)
    check("envelope S3 end (us)", 2.304942,
          float(env["lower_envelope_S3-FIFO_end"]), 1e-6)
    check("envelope ContShadow start (us)", 2.304942,
          float(env["lower_envelope_ContShadow_start"]), 1e-6)
    check("envelope ContShadow end", "inf", env["lower_envelope_ContShadow_end"])
    check("DA on lower envelope", "false", env["da_on_lower_envelope"])
    check("DA minimum excess (ns)", 3.268673,
          float(env["da_min_excess"]), 1e-6)
    check("DA minimum excess at (us)", 2.304942,
          float(env["da_min_excess_at"]), 1e-6)

    ttb = {x["quantity"]: x for x in load("phase5/total_time_bootstrap.csv")}
    for q, point, lo, hi in [
        ("crossing_clock_s3", 0.215539, 0.170596, 0.274219),
        ("crossing_s3_cs", 2.304942, 1.659945, 3.678437),
        ("crossing_da_cs", 2.196187, 1.449376, 4.105260),
        ("crossing_da_s3", 2.516878, 1.085631, 22.051195),
        ("min_da_gap_ns", 3.268673, -28.597766, 40.231357),
        ("min_da_gap_cm_us", 2.304942, 0.194380, 3.413206),
    ]:
        check(f"bootstrap {q} point", point, float(ttb[q]["point"]), 1e-6)
        check(f"bootstrap {q} CI low", lo, float(ttb[q]["ci95_low"]), 1e-6)
        check(f"bootstrap {q} CI high", hi, float(ttb[q]["ci95_high"]), 1e-6)
    check("bootstrap DA/S3 valid reps", "9394", ttb["crossing_da_s3"]["valid_reps"])
    check("bootstrap reps", "10000", ttb["min_da_gap_ns"]["bootstrap_reps"])
    check("bootstrap seed", "20261124", ttb["min_da_gap_ns"]["seed"])

    tt = {x["scenario"]: x for x in load("phase5/total_time_table.csv")}
    minor = tt["Minor-fault calibration (measured)"]
    for m, exp in [("CLOCK_ns", 1239.600), ("S3-FIFO_ns", 1058.821),
                   ("ContShadow_ns", 1063.593), ("DA_ns", 1063.708)]:
        check(f"minor-fault total time {m}", exp, float(minor[m]), 0.01)
    check("minor-fault cheapest", "S3-FIFO", minor["cheapest"])
    check("minor-fault DA-best (ns)", 4.887,
          float(minor["DA_minus_best_ns"]), 0.01)
    for m, ns, miss in [("CLOCK", 8.90, 0.55941), ("S3-FIFO", 28.54, 0.46831),
                        ("ContShadow", 133.36, 0.42283), ("DA", 67.36, 0.45289)]:
        check(f"envelope mean ns/ref {m}", ns, mval(r, m, "ns_per_ref"), 0.01)
        check(f"envelope mean miss {m}", miss, mval(r, m), 1e-5)

    # Post hoc measurement experiments (Section \ref{sec:posthoc}).
    trig = {}
    for name, path, method in [
        ("oracle","trigger_real/oracle.csv","DA-oracle"),
        ("periodic_p40","trigger_real/periodic_p40.csv","DA-periodic"),
        ("random_r04","trigger_real/random_r04.csv","DA-random")]:
        rows = [x for x in load(path) if x["scenario"] in NONSTABLE and x["method"] == method]
        trig[name] = (mean(float(x["miss_ratio"]) for x in rows),
                      mean(float(x["switches"]) for x in rows),
                      mean(float(x["shadow_evals"]) for x in rows))
    check("posthoc trigger oracle miss", 0.4335, trig["oracle"][0])
    check("posthoc trigger oracle switches", 2.19, trig["oracle"][1], 0.01)
    check("posthoc trigger oracle evals", 5.74, trig["oracle"][2], 0.01)
    check("posthoc trigger periodic_p40 miss", 0.4687, trig["periodic_p40"][0])
    check("posthoc trigger periodic_p40 switches", 2.52, trig["periodic_p40"][1], 0.01)
    check("posthoc trigger periodic_p40 evals", 7.22, trig["periodic_p40"][2], 0.01)
    check("posthoc trigger random_r04 miss", 0.4906, trig["random_r04"][0])
    check("posthoc trigger random_r04 switches", 2.60, trig["random_r04"][1], 0.01)
    check("posthoc trigger random_r04 evals", 6.50, trig["random_r04"][2], 0.01)

    # Trigger paired stats computed from raw CSVs (bootstrap seed 0, 10k).
    import random as _random
    from scipy.stats import wilcoxon as _wilcoxon
    da_ns = [x for x in load("main_study_results.csv") if x["scenario"] in NONSTABLE and x["method"] == "DA"]
    trig_cfg = [
        ("DA-oracle","trigger_real/oracle.csv","DA-oracle"),
        ("DA-periodic_p40","trigger_real/periodic_p40.csv","DA-periodic"),
        ("DA-random_r04","trigger_real/random_r04.csv","DA-random"),
        ("DA-ContShadow","main_study_results.csv","ContShadow"),
    ]
    trig_res = []
    for name, path, method in trig_cfg:
        other = [x for x in load(path) if x["scenario"] in NONSTABLE and x["method"] == method]
        diffs = [float(a["miss_ratio"]) - float(b["miss_ratio"]) for a,b in zip(da_ns, other)]
        rnd = _random.Random(0); bs = sorted(mean(rnd.choices(diffs, k=len(diffs))) for _ in range(10000))
        p = float(_wilcoxon(diffs).pvalue)
        trig_res.append([name, mean(diffs), bs[250], bs[9750], p])
    order = sorted(range(len(trig_res)), key=lambda i: trig_res[i][4])
    holm = [0.0]*len(trig_res); prev = 0.0
    for rank,i in enumerate(order,1):
        adj = min(1.0, max(prev, trig_res[i][4]*(len(trig_res)-rank+1))); holm[i]=adj; prev=adj
    for i,(name,md,lo,hi,p) in enumerate(trig_res):
        check(f"posthoc {name} diff", {"DA-oracle":0.0194,"DA-periodic_p40":-0.0158,"DA-random_r04":-0.0377,"DA-ContShadow":0.0301}[name], md)
        check(f"posthoc {name} Holm", {"DA-oracle":0.0177,"DA-periodic_p40":0.0177,"DA-random_r04":0.0004,"DA-ContShadow":2.51e-5}[name], holm[i], 0.0001 if "ContShadow" not in name else 1e-6)

    ps = {r["tag"]: r for r in load("param_sweep/summary.csv")}
    for tag, exp in [("W_1000",0.461442),("W_2000",0.452888),("W_4000",0.500050),
                     ("delta_0.1",0.457896),("delta_0.3",0.455087),("delta_0.5",0.452888),("delta_0.7",0.454430),("delta_1.0",0.453678),
                     ("h_2",0.456338),("h_3",0.453806),("h_5",0.452888),("h_7",0.454700),("h_10",0.456900),
                     ("p_0.05",0.480957),("p_0.1",0.469601),("p_0.2",0.452888),("p_0.4",0.447180)]:
        check(f"param sweep {tag} miss", exp, float(ps[tag]["miss"]))
    fiu_t = {}
    for name, path, method in [
        ("oracle","trigger_real/fiu_oracle.csv","DA-oracle"),
        ("periodic_p40","trigger_real/fiu_periodic_p40.csv","DA-periodic"),
        ("random_r04","trigger_real/fiu_random_r04.csv","DA-random")]:
        rows = [x for x in load(path) if x["method"] == method]
        det = [x for x in load(path.replace('.csv','_det.csv')) if x["method"] == method]
        fiu_t[name] = (mean(float(x["miss_ratio"]) for x in rows),
                       sum(int(x["switches"]) for x in rows),
                       sum(int(x["shadow_evals"]) for x in rows),
                       sum(int(x.get("confirms","0") or 0) for x in det))
    check("posthoc FIU oracle miss", 0.712698, fiu_t["oracle"][0])
    check("posthoc FIU oracle switches", 6, fiu_t["oracle"][1], 0)
    check("posthoc FIU oracle evals", 6, fiu_t["oracle"][2], 0)
    check("posthoc FIU oracle confirms", 0, fiu_t["oracle"][3], 0)
    check("posthoc FIU periodic_p40 miss", 0.713068, fiu_t["periodic_p40"][0])
    check("posthoc FIU random_r04 miss", 0.709742, fiu_t["random_r04"][0])
    base_fiu = [x for x in load("rankability_real/fiu_C1000_p0.2.csv") if x["method"].startswith("DA")]
    check("posthoc FIU C1000 p0.2 baseline miss", 0.706285, mean(float(x["miss_ratio"]) for x in base_fiu))

    synth_rank = { (int(r["C"]),float(r["p"])): r for r in load("rankability_real/synth_sweep.csv") }
    check("synth rank C500 p0.2 miss", 0.580196, float(synth_rank[(500,0.2)]["mean_miss"]))
    check("synth rank C4000 p0.2 miss", 0.180884, float(synth_rank[(4000,0.2)]["mean_miss"]))
    fiu_rank = { (int(r["C"]),float(r["p"])): r for r in load("rankability_real/fiu_sweep.csv") }
    check("FIU rank C20000 p0.2 miss", 0.668337, float(fiu_rank[(20000,0.2)]["mean_miss"]))
    check("FIU rank C20000 p0.2 switches", 0, int(fiu_rank[(20000,0.2)]["total_switches"]), 0)

    # Phase 3 pre-specified detectors (seed 5001, 80 non-stable)
    p3 = load("phase3_detectors/train_summary.csv")
    p3_ph = min([x for x in p3 if x["tag"].startswith("ph_")], key=lambda r:(float(r["miss"]), float(r["shadow_evals"])))
    p3_ad = min([x for x in p3 if x["tag"].startswith("adwin_")], key=lambda r:(float(r["miss"]), float(r["shadow_evals"])))
    check("phase3 PH selected tag", "ph_d0.001_l2", p3_ph["tag"], 0)
    check("phase3 ADWIN selected tag", "adwin_d0.05", p3_ad["tag"], 0)
    def ns_mean(path, method):
        rows=[x for x in load(path) if x["scenario"] in NONSTABLE and x["method"]==method]
        return mean(float(x["miss_ratio"]) for x in rows)
    check("phase3 PH test miss", 0.4552, ns_mean("phase3_detectors/ph_selected_seed5001.csv","DA-ph"))
    check("phase3 PH test evals", 3.52, mean(float(x["shadow_evals"]) for x in load("phase3_detectors/ph_selected_seed5001.csv") if x["scenario"] in NONSTABLE), 0.01)
    check("phase3 ADWIN test miss", 0.4991, ns_mean("phase3_detectors/adwin_selected_seed5001.csv","DA-adwin"))
    check("phase3 ADWIN test evals", 2.64, mean(float(x["shadow_evals"]) for x in load("phase3_detectors/adwin_selected_seed5001.csv") if x["scenario"] in NONSTABLE), 0.01)
    # Phase 4 baselines
    p4s=[x for x in load("phase4_baselines/synth_sieve_wtiny.csv") if x["scenario"] in NONSTABLE]
    check("phase4 synth SIEVE miss", 0.5557, mean(float(x["miss_ratio"]) for x in p4s if x["method"]=="SIEVE"))
    check("phase4 synth W-TinyLFU miss", 0.4913, mean(float(x["miss_ratio"]) for x in p4s if x["method"]=="W-TinyLFU"))
    p4r=load("phase4_baselines/real_summary.csv")
    for m, exp in [("S3-FIFO",0.5162),("W-TinyLFU",0.5317),("ARC",0.5412),("SIEVE",0.5439),("ContShadow",0.5458),("DA-adwin",0.5465),("DA-ph",0.5475),("DA",0.5477),("LRU",0.5496)]:
        check(f"phase4 real {m} miss", exp, mean(float(x["miss"]) for x in p4r if x["method"]==m))
    # Phase 5 robustness/cost
    t3=[x for x in load("phase5/t3_seed5001.csv") if x["scenario"] in NONSTABLE]
    check("phase5 t3 DA miss", 0.4586, mean(float(x["miss_ratio"]) for x in t3))
    bm=list(csv.DictReader(open(os.path.join(HERE,"cost_model.csv"))))
    bm={r["quantity"]:r["value"] for r in bm if r.get("quantity")}
    check("cost R", 783.28, float(bm["break_even_ratio_R"]), 0.1)
    check("cost direct break-even us", 2.1962, float(bm["direct_break_even_miss_cost"])/1000, 0.01)
    # Phase 4b: LHD and external CMU PDL traces
    lhd_synth=[x for x in load("phase4_lhd/synth_lhd.csv") if x["scenario"] in NONSTABLE]
    check("LHD synth miss", 0.6736, mean(float(x["miss_ratio"]) for x in lhd_synth))
    lhd_real=[]
    for path in glob.glob(os.path.join(HERE,"phase4_lhd","*_lhd.csv")):
        lhd_real.append(mean(float(x["miss_ratio"]) for x in load(os.path.relpath(path, HERE)) if x["method"]=="LHD"))
    check("LHD real mean", 0.6979, mean(lhd_real))
    ext = {r["method"]: float(r["mean_miss"]) for r in csv.DictReader(open(os.path.join(HERE,"phase4_external","external_summary.csv")))}
    for m, exp in [("S3-FIFO",0.6188),("ARC",0.6208),("DA",0.6280),("W-TinyLFU",0.6306),
                   ("ContShadow",0.6335),("LRU",0.6412),("SIEVE",0.6538),("LHD",0.9358)]:
        check(f"external PDL {m} miss", exp, ext[m])

    # Appendix (real programs).
    ap = {x["comparison"]: x for x in load("appendix_intervals.csv")}
    check("appendix DA miss", 0.3304,
          mean(float(x["DA"]) for x in load("whole_program_holdout_results.csv")))
    check("appendix S3 miss", 0.3291,
          mean(float(x["S3-FIFO"]) for x in load("whole_program_holdout_results.csv")))
    check("appendix LRU miss", 0.3540,
          mean(float(x["LRU"]) for x in load("whole_program_holdout_results.csv")))
    check("appendix DA-S3 diff", 0.0013,
          float(ap["DA-S3-FIFO"]["mean_DA_minus_method"]))
    check("appendix ContShadow CI", -0.0008,
          float(ap["DA-ContShadow"]["ci_lo"]), 0.0001)
    for name, exp_mean, lo, hi in [
        ("DA-2Q", -0.0165, -0.0304, -0.0051),
        ("DA-ARC", -0.0187, -0.0370, -0.0041),
        ("DA-DIP-set-duel", -0.0194, -0.0390, -0.0030),
        ("DA-LRU", -0.0236, -0.0456, -0.0056),
        ("DA-LPR-style", -0.0236, -0.0458, -0.0055),
        ("DA-MGLRU-style", -0.0244, -0.0475, -0.0052)]:
        check(f"appendix {name} mean", exp_mean,
              float(ap[name]["mean_DA_minus_method"]))
        check(f"appendix {name} CI low", lo, float(ap[name]["ci_lo"]), 0.0001)
        check(f"appendix {name} CI high", hi, float(ap[name]["ci_hi"]), 0.0001)
    check("appendix 2Q Holm p", 0.096,
          float(ap["DA-2Q"]["holm_p"]), 0.001)
    wprog = load("whole_program_holdout_results.csv")
    byprog = defaultdict(list)
    for x in wprog:
        byprog[x["held_out_program"]].append(float(x["DA"]))
    pmean = {k: mean(v) for k, v in byprog.items()}
    check("kernels below 0.02", 6,
          sum(1 for v in pmean.values() if v < 0.02), 0)
    check("five high-miss kernels", 5,
          sum(1 for v in pmean.values() if v > 0.70), 0)
    for k, exp in [("sparse", 0.72), ("pagerank", 0.83), ("hashmap", 0.71),
                   ("linkedlist", 0.94), ("unionfind", 0.73)]:
        check(f"high-miss kernel {k}", exp, pmean[k], 0.006)
    cost15 = load("real_trace_cost_15prog.csv")
    for m, exp in [("DA", 59.5), ("LRU", 27.5), ("S3-FIFO", 24.7)]:
        check(f"appendix ns/ref, {m}", exp, mval(cost15, m, "ns_per_ref"), 0.06)
    check("sweep configurations", 48, len(load("sweep_results.csv")), 0)

    # Phase 6: six-family PDL prefixes (all numbers read from generated CSVs).
    p6 = {r["method"]: r for r in load("phase6_pdl/summary.csv")}
    for m, exp in [("S3-FIFO", 0.4683), ("ContShadow", 0.4739), ("DA", 0.4742),
                   ("CLOCK", 0.4973), ("LRU", 0.4987)]:
        check(f"phase6 PDL mean miss, {m}", exp, float(p6[m]["mean_miss"]))
    p6p = {r["baseline"]: r for r in load("phase6_pdl/paired_da_minus_baseline.csv")}
    check("phase6 DA-S3 paired diff", 0.0059, float(p6p["S3-FIFO"]["mean_diff"]))
    check("phase6 DA-S3 Holm p", 0.0192, float(p6p["S3-FIFO"]["holm_p"]), 0.0002)
    check("phase6 family-capacity points", 18, p6["DA"]["n"], 0)

    # Phase 7: real async-shadow prototype (three measured repetitions).
    p7 = {r["repetition"]: r for r in load("phase7_async/summary.csv")}
    p7p = {r["repetition"]: r for r in load("phase7_async/paired.csv")}
    for rep, exp in [("1", 0.5611), ("2", 0.5676), ("3", 0.5599)]:
        check(f"phase7 async rep {rep} miss", exp, float(p7[rep]["mean_miss"]))
    for rep, exp in [("1", 0.1082), ("2", 0.1147), ("3", 0.1070)]:
        check(f"phase7 async rep {rep} DA-minus-sync", exp,
              float(p7p[rep]["mean_async_minus_sync"]))

    # Phase 8: real guest-kernel measurements (read from the generated CSVs).
    k8 = load("phase8_kernel/kernel_summary.csv")
    check("phase8 real guest runs", 9, len(k8), 0)
    for row in k8:
        tag = f"phase8 {row['condition']} rep {row['rep']}"
        check(f"{tag} minor faults", 131138, int(float(row["minflt"])), 0)
        check(f"{tag} major faults", 0, int(float(row["majflt"])), 0)
        check(f"{tag} refault delta", 0, int(row["refault_delta"]), 0)
        check(f"{tag} pgscan delta", 0, int(row["pgscan_delta"]), 0)
        check(f"{tag} pgsteal delta", 0, int(row["pgsteal_delta"]), 0)
        check(f"{tag} controller toggles", 0, int(row["toggles"]), 0)
    p8f = load("phase8_kernel/ftrace_summary.csv")
    check("phase8 ftrace total samples", 191370, sum(int(r["n"]) for r in p8f), 0)
    check("phase8 ftrace function groups", 18, len(p8f), 0)
    check("phase8 ftrace distinct functions", 2, len({r["function"] for r in p8f}), 0)
    check("phase8 raw ftrace duration rows", 191370,
          len(load("phase8_kernel/ftrace_durations.csv")), 0)
    for cond, rep, median, p95 in [
            ("fixed_lru", "1", 761.0, 1593.0),
            ("fixed_lru", "2", 671.0, 1522.0),
            ("fixed_lru", "3", 752.0, 1643.9),
            ("fixed_mglru", "1", 641.0, 1532.0),
            ("fixed_mglru", "2", 711.5, 1573.0),
            ("fixed_mglru", "3", 741.0, 1643.0),
            ("coupled", "1", 731.0, 1673.0),
            ("coupled", "2", 741.0, 1693.0),
            ("coupled", "3", 701.0, 1583.0)]:
        row = next(r for r in p8f if r["condition"] == cond and r["rep"] == rep
                   and r["function"] == "handle_mm_fault")
        check(f"phase8 {cond} rep {rep} fault median ns", median,
              float(row["median_ns"]), 0.05)
        check(f"phase8 {cond} rep {rep} fault p95 ns", p95,
              float(row["p95_ns"]), 0.05)

    # The printed LaTeX fragments must carry the same CSV-derived numbers.
    main_frag = latex_fragment("phase8_kernel_main_table.tex")
    ftrace_frag = latex_fragment("phase8_kernel_ftrace_table.tex")
    check("phase8 main fragment minor-fault rows", 9, main_frag.count("131,138"), 0)
    check("phase8 main fragment first fault duration", True, "$761.0/1593.0$" in main_frag)
    check("phase8 main fragment exact p95 display", True, "$752.0/1643.9$" in main_frag)
    check("phase8 ftrace fragment fault rows", 9, ftrace_frag.count("handle\\_mm\\_fault"), 0)
    check("phase8 ftrace fragment WP rows", 9, ftrace_frag.count("do\\_wp\\_page"), 0)
    check("phase8 ftrace fragment no reclaim rows", False,
          any(name in ftrace_frag for name in ("shrink", "reclaim_pages", "do_swap_page")))

    # Phase 10: independent capacity pilot replacing webresearch-only provenance.
    p10man = load("phase10_capacity_pilot/manifest.csv")
    check("phase10 pilot traces", 1, len(p10man), 0)
    check("phase10 pilot records", 1000000, int(p10man[0]["records"]), 0)
    check("phase10 pilot WSS", 72539, int(p10man[0]["wss"]), 0)
    check("phase10 pilot sha256", "f09a2450a1b9dc7eb521191dfbeea1213d1a7fd63cbec5cb601dffec46c85403",
          p10man[0]["sha256_bin"])
    check("phase10 grid commands", 7, len(load("phase10_capacity_pilot/commands.csv")), 0)
    p10 = {int(r["C"]): r for r in load("phase10_capacity_pilot/selection.csv")}
    for c, lru, s3, sep in [
            (1000, 0.79277, 0.74659, 0.04618),
            (5000, 0.74918, 0.73289, 0.01629),
            (10000, 0.74182, 0.73317, 0.00865),
            (15000, 0.73861, 0.73198, 0.00663),
            (20000, 0.73590, 0.52726, 0.20864),
            (25000, 0.73472, 0.45401, 0.28071),
            (50000, 0.18981, 0.03674, 0.15307)]:
        check(f"phase10 pilot C={c} LRU miss", lru, float(p10[c]["lru_miss"]))
        check(f"phase10 pilot C={c} S3-FIFO miss", s3, float(p10[c]["s3_miss"]))
        check(f"phase10 pilot C={c} separation", sep, float(p10[c]["separation"]))
    check("phase10 selected capacity", 20000,
          int([r for r in p10.values() if r["selected"] == "1"][0]["C"]), 0)
    check("phase10 C=10000 not qualifying", False, p10[10000]["primary_ok"] == "True")
    check("phase10 C=20000 qualifying", True, p10[20000]["primary_ok"] == "True")
    raw10 = {r["method"]: r for r in load("phase10_capacity_pilot/C20000.csv")}
    check("phase10 raw C=20000 LRU", 0.73590, float(raw10["LRU"]["miss_ratio"]))
    check("phase10 raw C=20000 S3-FIFO", 0.52726, float(raw10["S3-FIFO"]["miss_ratio"]))
    supp = latex_fragment("supplement.tex")
    drift_supp = drift_fragment("supplement.tex")
    for label, txt in [("latex", supp), ("drift", drift_supp)]:
        check(f"{label} supplement pilot C=10000 LRU", True, "0.74182" in txt)
        check(f"{label} supplement pilot C=10000 S3", True, "0.73317" in txt)
        check(f"{label} supplement pilot C=10000 gap", True, "0.00865" in txt)
        check(f"{label} supplement pilot C=20000 LRU", True, "0.73590" in txt)
        check(f"{label} supplement pilot C=20000 S3", True, "0.52726" in txt)
        check(f"{label} supplement pilot C=20000 gap", True, "0.20864" in txt)
        check(f"{label} supplement cites independent pilot", True, "webusers" in txt)
        check(f"{label} supplement cites pilot artifacts", True,
              ("phase10_capacity_pilot" in txt or "phase10\\_capacity\\_pilot" in txt))
        check(f"{label} supplement drops stale test-trace pilot claim", False,
              "chosen by a pilot on one" in txt)
    stale_phrases = [
        "chosen by a pilot on one",
        "capacity chosen by a pilot on a test trace",
        "FIU capacity came from a test trace",
        "FIU capacity was chosen on a test trace",
    ]
    for rel in ["latex/main.tex", "latex/supplement.tex", "paper_final.tex",
                "drift_gating_latex_source/main_template.tex",
                "drift_gating_latex_source/main.tex",
                "drift_gating_latex_source/supplement.tex"]:
        with open(os.path.join(HERE, "..", rel)) as fh:
            txt = fh.read()
        for phrase in stale_phrases:
            check(f"{rel} no stale '{phrase}'", False, phrase in txt)
    drift_main = drift_fragment("main.tex")
    check("drift main cites independent capacity pilot", True,
          "capacity selected on an independent pilot trace" in drift_main)

    fails = [c for c in CHECKS if not c[0]]
    for ok, claim, exp, act, unit in CHECKS:
        if isinstance(exp, str) or isinstance(act, str):
            print(f"{'PASS' if ok else 'FAIL'}  {claim:44} paper={exp}{unit}  raw={act}{unit}")
        else:
            print(f"{'PASS' if ok else 'FAIL'}  {claim:44} paper={exp}{unit}  raw={act:.5g}{unit}")
    print(f"\n{len(CHECKS) - len(fails)}/{len(CHECKS)} checks passed.")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
