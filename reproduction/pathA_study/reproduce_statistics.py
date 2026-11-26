#!/usr/bin/env python3
"""
reproduction/pathA_study/reproduce_statistics.py
Independent reproduction of all primary, sensitivity, and controller statistics
directly from results/raw/*.csv into results/reproduced_statistics/.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import scipy.stats as stats

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "results" / "raw"
OUT = ROOT / "results" / "reproduced_statistics"
OUT.mkdir(parents=True, exist_ok=True)


def holm_correction(pvals):
    n = len(pvals)
    indexed = sorted(enumerate(pvals), key=lambda x: x[1])
    corrected = [0.0] * n
    for rank, (orig_i, p) in enumerate(indexed):
        corrected[orig_i] = min(1.0, p * (n - rank))
    mx = 0.0
    for orig_i, _ in indexed:
        corrected[orig_i] = max(corrected[orig_i], mx)
        mx = corrected[orig_i]
    return corrected


def main():
    ora = pd.read_csv(RAW / "oracle_summary.csv")
    fsw = pd.read_csv(RAW / "finesweep.csv")
    pol = pd.read_csv(RAW / "oracle_policy.csv")
    ctrl = pd.read_csv(RAW / "controllers.csv")
    cdiag = pd.read_csv(RAW / "ctrl_diag.csv")

    # ── 1. Oracle Aggregations (W=50k, 1%-10% WSS) ─────────────────────────
    c_rows = ora[ora["switch_cost"] > 0].copy()
    z_rows = ora[ora["switch_cost"] == 0].copy()

    nonstat_traces = set(z_rows[z_rows["net_gain_vs_best"] > 0.001]["trace"].unique())

    agg_rows = []
    def add_agg(scope, df_c, df_z):
        agg_rows.append({
            "scope": scope,
            "n_c": len(df_c),
            "gC_mean": df_c["net_gain_vs_best"].mean(),
            "gC_max": df_c["net_gain_vs_best"].max(),
            "gC_clear02": int((df_c["net_gain_vs_best"] >= 0.02).sum()),
            "g0_mean": df_z["net_gain_vs_best"].mean(),
            "g0_max": df_z["net_gain_vs_best"].max(),
            "g0_clear02": int((df_z["net_gain_vs_best"] >= 0.02).sum()),
        })

    for src in ["real_app_pageref", "instrumented_program", "fiu_public", "pdl_public"]:
        add_agg(f"source:{src}", c_rows[c_rows["source"] == src], z_rows[z_rows["source"] == src])

    add_agg("trace_weighted_all", c_rows, z_rows)

    fam_c = c_rows.groupby("family", as_index=False)["net_gain_vs_best"].mean()
    fam_z = z_rows.groupby("family", as_index=False)["net_gain_vs_best"].mean()
    agg_rows.append({
        "scope": "family_macro_30",
        "n_c": len(fam_c),
        "gC_mean": fam_c["net_gain_vs_best"].mean(),
        "gC_max": c_rows["net_gain_vs_best"].max(),
        "gC_clear02": int((c_rows.groupby(["family", "cap_frac"])["net_gain_vs_best"].apply(lambda s: (s >= 0.02).mean() >= 2/3)).sum()),
        "g0_mean": fam_z["net_gain_vs_best"].mean(),
        "g0_max": z_rows["net_gain_vs_best"].max(),
        "g0_clear02": int((z_rows.groupby(["family", "cap_frac"])["net_gain_vs_best"].apply(lambda s: (s >= 0.02).mean() >= 2/3)).sum()),
    })

    src_c = c_rows.groupby("source", as_index=False)["net_gain_vs_best"].mean()
    src_z = z_rows.groupby("source", as_index=False)["net_gain_vs_best"].mean()
    agg_rows.append({
        "scope": "source_equal_weighted_4",
        "n_c": len(src_c),
        "gC_mean": src_c["net_gain_vs_best"].mean(),
        "gC_max": c_rows["net_gain_vs_best"].max(),
        "gC_clear02": 0,
        "g0_mean": src_z["net_gain_vs_best"].mean(),
        "g0_max": z_rows["net_gain_vs_best"].max(),
        "g0_clear02": 0,
    })

    add_agg(
        f"nonstationary_traces_{len(nonstat_traces)}",
        c_rows[c_rows["trace"].isin(nonstat_traces)],
        z_rows[z_rows["trace"].isin(nonstat_traces)],
    )
    agg_df = pd.DataFrame(agg_rows)
    agg_df.to_csv(OUT / "oracle_aggregations.csv", index=False)
    print("=== 1. Oracle Aggregations (W=50k, 1%-10% WSS) ===")
    print(agg_df.to_string(index=False))

    # ── 2. Family-Level Controller Statistics (n=30) ────────────────────────
    s3 = pol[pol["policy"] == "S3-FIFO"][["trace", "cap_frac", "miss_ratio"]].rename(
        columns={"miss_ratio": "s3_mr"}
    )
    merged = ctrl[ctrl["controller"] != "S3-FIFO"].merge(s3, on=["trace", "cap_frac"], how="inner")
    merged["delta"] = merged["miss_ratio"] - merged["s3_mr"]

    fams = sorted(merged["family"].unique())
    rng = np.random.default_rng(42)

    h2_rows = []
    raw_p_fam = []
    raw_p_pair = []
    for cname, sub in merged.groupby("controller"):
        deltas = sub["delta"].to_numpy()
        fam_arrs = [sub[sub["family"] == f]["delta"].to_numpy() for f in fams]
        fam_means = np.array([fa.mean() for fa in fam_arrs])

        # Pair-weighted cluster bootstrap (matches generate_paper_assets.py)
        boots_pw = [
            np.concatenate([fam_arrs[i] for i in rng.integers(0, len(fams), size=len(fams))]).mean()
            for _ in range(3000)
        ]
        # Family-equal-weighted cluster bootstrap
        boots_fw = [
            fam_means[rng.integers(0, len(fams), size=len(fams))].mean()
            for _ in range(3000)
        ]

        n_zeros_fam = int((fam_means == 0).sum())
        w_stat_fam, p_fam = stats.wilcoxon(fam_means, alternative="two-sided", zero_method="wilcox")
        w_stat_pair, p_pair = stats.wilcoxon(deltas, alternative="two-sided", zero_method="wilcox")

        ranks = stats.rankdata(np.abs(fam_means))
        w_pos = ranks[fam_means > 0].sum()
        w_neg = ranks[fam_means < 0].sum()
        rb_fam = (w_pos - w_neg) / max(1e-12, w_pos + w_neg)

        raw_p_fam.append(float(p_fam))
        raw_p_pair.append(float(p_pair))
        h2_rows.append({
            "controller": cname,
            "n_pairs": len(deltas),
            "n_families": len(fams),
            "n_zeros_fam": n_zeros_fam,
            "pair_mean_delta": deltas.mean(),
            "fam_macro_delta": fam_means.mean(),
            "pw_ci95_lo": np.quantile(boots_pw, 0.025),
            "pw_ci95_hi": np.quantile(boots_pw, 0.975),
            "fw_ci95_lo": np.quantile(boots_fw, 0.025),
            "fw_ci95_hi": np.quantile(boots_fw, 0.975),
            "wilcoxon_W_fam": float(w_stat_fam),
            "p_fam_raw": float(p_fam),
            "p_pair_raw": float(p_pair),
            "rb_fam": float(rb_fam),
            "switches_mean": sub["switches"].mean(),
            "evals_mean": sub["shadow_evals"].mean(),
            "ns_per_ref_mean": sub["ns_per_ref"].mean(),
        })

    holm_fam = holm_correction(raw_p_fam)
    holm_pair = holm_correction(raw_p_pair)
    for row, hf, hp in zip(h2_rows, holm_fam, holm_pair):
        row["p_fam_holm"] = hf
        row["p_pair_holm"] = hp

    h2_df = pd.DataFrame(h2_rows).sort_values("pair_mean_delta")
    h2_df.to_csv(OUT / "h2_family_level_stats.csv", index=False)
    print("\n=== 2. H2 Family-Level Statistics (n=30 families, 17 controllers) ===")
    print(h2_df[["controller", "pair_mean_delta", "fam_macro_delta", "pw_ci95_lo", "pw_ci95_hi", "p_fam_holm", "rb_fam"]].to_string(index=False))

    # ── 3. Controller Diagnosis Time-Shares ─────────────────────────────────
    diag_rows = []
    for cname in ["ContShadow", "CUSUM-med", "OracleTrig"]:
        sub = cdiag[cdiag["controller"] == cname]
        diag_rows.append({
            "group": f"{cname} (all)",
            "n": len(sub),
            "delta_mr": (sub["miss_ratio"] - sub["s3fifo_miss_ratio"]).mean(),
            "s3fifo_frac": sub["s3fifo_frac"].mean(),
            "lru_frac": sub["lru_frac"].mean(),
            "q2_frac": sub["q2_frac"].mean(),
            "arc_frac": sub["arc_frac"].mean(),
            "lfua_frac": sub["lfua_frac"].mean(),
            "mru_frac": sub["mru_frac"].mean(),
        })
    for src in ["real_app_pageref", "fiu_public", "pdl_public", "instrumented_program"]:
        sub = cdiag[(cdiag["controller"] == "ContShadow") & (cdiag["source"] == src)]
        diag_rows.append({
            "group": f"ContShadow ({src})",
            "n": len(sub),
            "delta_mr": (sub["miss_ratio"] - sub["s3fifo_miss_ratio"]).mean(),
            "s3fifo_frac": sub["s3fifo_frac"].mean(),
            "lru_frac": sub["lru_frac"].mean(),
            "q2_frac": sub["q2_frac"].mean(),
            "arc_frac": sub["arc_frac"].mean(),
            "lfua_frac": sub["lfua_frac"].mean(),
            "mru_frac": sub["mru_frac"].mean(),
        })
    diag_df = pd.DataFrame(diag_rows)
    diag_df.to_csv(OUT / "ctrl_diag_reproduced.csv", index=False)
    print("\n=== 3. Controller Diagnosis Time-Shares ===")
    print(diag_df.to_string(index=False))


if __name__ == "__main__":
    main()
