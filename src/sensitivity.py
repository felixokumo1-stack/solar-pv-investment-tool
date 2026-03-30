# src/sensitivity.py
#
# PURPOSE: Sensitivity and scenario analysis for the 500 kWp PV investment.
#
# TWO TYPES OF ANALYSIS:
#
# 1. ONE-WAY SENSITIVITY — vary one parameter at a time, hold others constant
#    Shows which assumptions have the most impact on NPV/IRR
#    Visualised as a Tornado Chart
#
# 2. SCENARIO ANALYSIS — combine assumptions into coherent Bear/Base/Bull cases
#    Shows the range of plausible outcomes
#    Visualised as a scenario comparison table + chart

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os
import sys

# Import our financial model functions
sys.path.insert(0, os.path.dirname(__file__))
from financial_model import (
    calculate_capex, build_cashflow_model, calculate_kpis,
    CAPEX, OPEX, ENERGY, SYSTEM_KWP
)

# ── PLOT STYLE ─────────────────────────────────────────────────────────────

COLORS = {
    "positive":   "#16A34A",
    "negative":   "#DC2626",
    "base":       "#2563EB",
    "bull":       "#16A34A",
    "bear":       "#DC2626",
    "neutral":    "#94A3B8",
    "light_grey": "#F1F5F9",
    "dark":       "#1E293B",
}

plt.rcParams.update({
    "font.family":       "sans-serif",
    "font.size":         11,
    "axes.titlesize":    13,
    "axes.titleweight":  "bold",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "figure.dpi":        150,
})

DISCOUNT_RATE = 0.06


def run_base_case() -> tuple:
    """Run the base case and return (capex_result, df_cf, kpis)."""
    capex_result = calculate_capex(CAPEX, SYSTEM_KWP)
    df_cf        = build_cashflow_model(capex_result, OPEX, ENERGY,
                                        SYSTEM_KWP, 20, DISCOUNT_RATE)
    kpis         = calculate_kpis(df_cf, capex_result, ENERGY, DISCOUNT_RATE)
    return capex_result, df_cf, kpis


def run_variant(capex_override=None, energy_override=None) -> dict:
    """
    Run a single model variant with overridden parameters.
    Returns KPIs dict.
    """
    # Merge overrides with base parameters
    capex_params  = {**CAPEX,   **(capex_override  or {})}
    energy_params = {**ENERGY,  **(energy_override or {})}

    capex_result  = calculate_capex(capex_params, SYSTEM_KWP)
    df_cf         = build_cashflow_model(capex_result, OPEX, energy_params,
                                         SYSTEM_KWP, 20, DISCOUNT_RATE)
    kpis          = calculate_kpis(df_cf, capex_result, energy_params,
                                   DISCOUNT_RATE)
    return kpis


# ══════════════════════════════════════════════════════════════════════════════
# ONE-WAY SENSITIVITY ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def run_one_way_sensitivity(base_npv: float) -> pd.DataFrame:
    """
    Vary each key parameter one at a time across its range.
    Record the resulting NPV swing relative to base case.

    Returns DataFrame suitable for tornado chart.
    """

    # Define parameters to test and their ranges
    # Format: (label, parameter_type, key, low_value, high_value)
    tests = [
        # CAPEX variations ±20%
        ("CAPEX (+20%)",
         "capex", "modules_eur_wp",
         CAPEX["modules_eur_wp"] * 1.20, None),

        ("CAPEX (-20%)",
         "capex", "modules_eur_wp",
         CAPEX["modules_eur_wp"] * 0.80, None),

        # Electricity price ±15%
        ("Electricity Price (+15%)",
         "energy", "elec_price_yr1_ct_kwh",
         ENERGY["elec_price_yr1_ct_kwh"] * 1.15, None),

        ("Electricity Price (-15%)",
         "energy", "elec_price_yr1_ct_kwh",
         ENERGY["elec_price_yr1_ct_kwh"] * 0.85, None),

        # Self-consumption ratio
        ("Self-Consumption (70%)",
         "energy", "self_consumption_ratio", 0.70, None),

        ("Self-Consumption (50%)",
         "energy", "self_consumption_ratio", 0.50, None),

        # Degradation rate
        ("Degradation (0.2%/yr)",
         "energy", "degradation_rate", 0.002, None),

        ("Degradation (0.6%/yr)",
         "energy", "degradation_rate", 0.006, None),

        # Discount rate
        ("Discount Rate (4%)",
         "discount", None, 0.04, None),

        ("Discount Rate (8%)",
         "discount", None, 0.08, None),
    ]

    rows = []
    for label, param_type, key, value, _ in tests:

        if param_type == "capex":
            # Scale all CAPEX components proportionally
            scale = value / CAPEX[key]
            capex_override = {
                k: v * scale for k, v in CAPEX.items()
                if k.endswith("_wp")
            }
            kpis = run_variant(capex_override=capex_override)

        elif param_type == "energy":
            kpis = run_variant(energy_override={key: value})

        elif param_type == "discount":
            capex_result = calculate_capex(CAPEX, SYSTEM_KWP)
            df_cf = build_cashflow_model(capex_result, OPEX, ENERGY,
                                          SYSTEM_KWP, 20, value)
            kpis  = calculate_kpis(df_cf, capex_result, ENERGY, value)

        npv_delta = kpis["npv_eur"] - base_npv

        rows.append({
            "parameter":  label,
            "npv_eur":    kpis["npv_eur"],
            "npv_delta":  round(npv_delta, 0),
            "irr_pct":    kpis["irr_pct"],
            "payback_yr": kpis["payback_years"],
            "go_verdict": kpis["npv_eur"] > 0,
        })

    return pd.DataFrame(rows)


def build_tornado_data(df_sensitivity: pd.DataFrame) -> pd.DataFrame:
    """
    Restructure sensitivity results into tornado chart format.
    Pairs low/high variants of each parameter into a single row.
    """

    # Group paired parameters (CAPEX +20% / -20% etc.)
    parameter_pairs = [
        ("CAPEX",              "CAPEX (-20%)",              "CAPEX (+20%)"),
        ("Electricity Price",  "Electricity Price (-15%)",  "Electricity Price (+15%)"),
        ("Self-Consumption",   "Self-Consumption (50%)",    "Self-Consumption (70%)"),
        ("Degradation Rate",   "Degradation (0.6%/yr)",     "Degradation (0.2%/yr)"),
        ("Discount Rate",      "Discount Rate (8%)",        "Discount Rate (4%)"),
    ]

    rows = []
    for param, low_label, high_label in parameter_pairs:
        low_row  = df_sensitivity[df_sensitivity["parameter"] == low_label]
        high_row = df_sensitivity[df_sensitivity["parameter"] == high_label]

        if not low_row.empty and not high_row.empty:
            rows.append({
                "parameter":  param,
                "npv_low":    low_row["npv_eur"].values[0],
                "npv_high":   high_row["npv_eur"].values[0],
                "swing":      abs(high_row["npv_eur"].values[0] -
                                  low_row["npv_eur"].values[0]),
            })

    df_tornado = pd.DataFrame(rows).sort_values("swing", ascending=True)
    return df_tornado


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def run_scenario_analysis() -> pd.DataFrame:
    """
    Run Bear / Base / Bull scenarios with coherent assumption sets.

    Bear  = everything goes slightly wrong
    Base  = central estimates (our primary model)
    Bull  = everything goes slightly right
    """

    scenarios = {
        "Bear Case": {
            "capex_scale":          1.15,   # 15% over budget
            "elec_price_yr1":       ENERGY["elec_price_yr1_ct_kwh"] * 0.85,
            "self_consumption":     0.50,   # lower on-site usage
            "degradation":          0.006,  # faster degradation
            "discount_rate":        0.08,   # higher cost of capital
            "description": "Higher costs, lower prices, conservative yield"
        },
        "Base Case": {
            "capex_scale":          1.00,
            "elec_price_yr1":       ENERGY["elec_price_yr1_ct_kwh"],
            "self_consumption":     0.60,
            "degradation":          0.004,
            "discount_rate":        0.06,
            "description": "Central estimates — primary model"
        },
        "Bull Case": {
            "capex_scale":          0.90,   # 10% under budget
            "elec_price_yr1":       ENERGY["elec_price_yr1_ct_kwh"] * 1.15,
            "self_consumption":     0.70,   # higher on-site usage
            "degradation":          0.003,  # slower degradation
            "discount_rate":        0.05,   # lower cost of capital
            "description": "Lower costs, higher prices, optimistic yield"
        },
    }

    rows = []
    for name, params in scenarios.items():

        # Scale all per-Wp CAPEX items
        capex_override = {
            k: v * params["capex_scale"]
            for k, v in CAPEX.items() if k.endswith("_wp")
        }

        energy_override = {
            "elec_price_yr1_ct_kwh": params["elec_price_yr1"],
            "self_consumption_ratio": params["self_consumption"],
            "degradation_rate":       params["degradation"],
        }

        capex_result = calculate_capex(
            {**CAPEX, **capex_override}, SYSTEM_KWP
        )
        df_cf = build_cashflow_model(
            capex_result, OPEX,
            {**ENERGY, **energy_override},
            SYSTEM_KWP, 20, params["discount_rate"]
        )
        kpis = calculate_kpis(
            df_cf, capex_result,
            {**ENERGY, **energy_override},
            params["discount_rate"]
        )

        rows.append({
            "scenario":       name,
            "description":    params["description"],
            "capex_eur":      capex_result["total_capex_eur"],
            "npv_eur":        kpis["npv_eur"],
            "irr_pct":        kpis["irr_pct"],
            "lcoe_ct_kwh":    kpis["lcoe_ct_kwh"],
            "payback_years":  kpis["payback_years"],
            "verdict":        "GO" if kpis["npv_eur"] > 0 and
                              (kpis["irr_pct"] or 0) > 8 else "NO-GO",
        })

    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# VISUALISATION
# ══════════════════════════════════════════════════════════════════════════════

def plot_tornado(df_tornado: pd.DataFrame, base_npv: float,
                 output_dir: str) -> None:
    """Chart 5: Tornado chart — one-way sensitivity on NPV."""

    fig, ax = plt.subplots(figsize=(11, 6))

    y_pos = range(len(df_tornado))

    for i, (_, row) in enumerate(df_tornado.iterrows()):
        low  = min(row["npv_low"],  row["npv_high"])
        high = max(row["npv_low"],  row["npv_high"])
        ax.barh(i, high - low, left=low,
                color=COLORS["base"], alpha=0.75, height=0.6)
        ax.text(high + 5000, i, f"EUR {high/1000:.0f}k",
                va="center", fontsize=8.5)
        ax.text(low  - 5000, i, f"EUR {low/1000:.0f}k",
                va="center", ha="right", fontsize=8.5)

    # Base case line
    ax.axvline(base_npv, color=COLORS["dark"], linewidth=1.5,
               linestyle="--", label=f"Base NPV: EUR {base_npv/1000:.0f}k")
    ax.axvline(0, color=COLORS["negative"], linewidth=1,
               linestyle=":", alpha=0.7, label="NPV = 0")

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(df_tornado["parameter"].tolist())
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f"EUR {x/1000:.0f}k"))
    ax.set_title("Tornado Chart — NPV Sensitivity Analysis (500 kWp, Bochum)")
    ax.set_xlabel("Net Present Value (EUR)")
    ax.legend(fontsize=9)
    ax.set_facecolor(COLORS["light_grey"])
    ax.grid(axis="x", color="white", linewidth=1.2)

    plt.tight_layout()
    path = os.path.join(output_dir, "05_tornado_chart.png")
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"✓ Saved: {path}")


def plot_scenario_comparison(df_scenarios: pd.DataFrame,
                              output_dir: str) -> None:
    """Chart 6: Bear/Base/Bull scenario comparison."""

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    metrics = [
        ("npv_eur",       "NPV (EUR)",       axes[0],
         lambda v: f"EUR {v/1000:.0f}k"),
        ("irr_pct",       "IRR (%)",         axes[1],
         lambda v: f"{v:.1f}%"),
        ("payback_years", "Payback (years)", axes[2],
         lambda v: f"{v:.1f} yr"),
    ]

    scenario_colors = [COLORS["bear"], COLORS["base"], COLORS["bull"]]
    names = df_scenarios["scenario"].tolist()

    for col, title, ax, fmt in metrics:
        values = df_scenarios[col].tolist()
        bars   = ax.bar(names, values, color=scenario_colors,
                        alpha=0.85, width=0.5, edgecolor="white")
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.02,
                    fmt(val), ha="center", fontsize=9,
                    fontweight="bold", color=COLORS["dark"])
        ax.set_title(title)
        ax.set_facecolor(COLORS["light_grey"])
        ax.grid(axis="y", color="white", linewidth=1.2)
        ax.tick_params(axis="x", labelsize=8.5)

    fig.suptitle("Scenario Analysis — Bear / Base / Bull Cases (500 kWp, Bochum)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(output_dir, "06_scenario_comparison.png")
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"✓ Saved: {path}")


def plot_cumulative_cashflow(output_dir: str) -> None:
    """Chart 7: Cumulative cash flow curves for all three scenarios."""

    fig, ax = plt.subplots(figsize=(12, 6))

    scenario_params = {
        "Bear Case": {
            "capex_scale": 1.15,
            "elec_price_yr1": ENERGY["elec_price_yr1_ct_kwh"] * 0.85,
            "self_consumption": 0.50,
            "degradation": 0.006,
            "discount_rate": 0.08,
            "color": COLORS["bear"],
            "style": "--",
        },
        "Base Case": {
            "capex_scale": 1.00,
            "elec_price_yr1": ENERGY["elec_price_yr1_ct_kwh"],
            "self_consumption": 0.60,
            "degradation": 0.004,
            "discount_rate": 0.06,
            "color": COLORS["base"],
            "style": "-",
        },
        "Bull Case": {
            "capex_scale": 0.90,
            "elec_price_yr1": ENERGY["elec_price_yr1_ct_kwh"] * 1.15,
            "self_consumption": 0.70,
            "degradation": 0.003,
            "discount_rate": 0.05,
            "color": COLORS["bull"],
            "style": "-.",
        },
    }

    for name, params in scenario_params.items():
        capex_override  = {k: v * params["capex_scale"]
                           for k, v in CAPEX.items() if k.endswith("_wp")}
        energy_override = {
            "elec_price_yr1_ct_kwh":  params["elec_price_yr1"],
            "self_consumption_ratio": params["self_consumption"],
            "degradation_rate":       params["degradation"],
        }
        capex_result = calculate_capex({**CAPEX, **capex_override}, SYSTEM_KWP)
        df_cf = build_cashflow_model(
            capex_result, OPEX, {**ENERGY, **energy_override},
            SYSTEM_KWP, 20, params["discount_rate"]
        )

        years      = [0] + df_cf["year"].tolist()
        cumulative = [-capex_result["total_capex_eur"]] + \
                     df_cf["cumulative_cashflow_eur"].tolist()

        ax.plot(years, cumulative,
                color=params["color"],
                linestyle=params["style"],
                linewidth=2.5, label=name, marker="o",
                markersize=3)

    ax.axhline(0, color=COLORS["dark"], linewidth=1, linestyle=":")
    ax.fill_between([0, 20], 0, ax.get_ylim()[0] if ax.get_ylim()[0] < 0 else -50000,
                    alpha=0.05, color=COLORS["negative"])

    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f"EUR {x/1000:.0f}k"))
    ax.set_xlabel("Project Year")
    ax.set_ylabel("Cumulative Cash Flow (EUR)")
    ax.set_title("Cumulative Cash Flow — All Scenarios (500 kWp, Bochum)")
    ax.legend(fontsize=10)
    ax.set_xlim(0, 20)
    ax.set_xticks(range(0, 21, 2))
    ax.grid(axis="y", alpha=0.3)
    ax.set_facecolor(COLORS["light_grey"])

    plt.tight_layout()
    path = os.path.join(output_dir, "07_cumulative_cashflow.png")
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"✓ Saved: {path}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    output_dir = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "outputs", "figures"))
    processed_dir = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "data", "processed"))

    print("=" * 55)
    print("   SENSITIVITY & SCENARIO ANALYSIS — 500 kWp")
    print("=" * 55)

    # 1. Base case
    print("\n[1/4] Running base case...")
    _, _, base_kpis = run_base_case()
    base_npv = base_kpis["npv_eur"]
    print(f"✓ Base NPV: EUR {base_npv:,.0f}")

    # 2. One-way sensitivity
    print("\n[2/4] Running one-way sensitivity analysis...")
    df_sens = run_one_way_sensitivity(base_npv)
    df_tornado = build_tornado_data(df_sens)
    print("✓ Sensitivity complete")
    print(f"\n── NPV remains positive in all variants: "
          f"{'YES ✅' if (df_sens['npv_eur'] > 0).all() else 'NO ⚠️'} ──")

    # 3. Scenario analysis
    print("\n[3/4] Running scenario analysis...")
    df_scenarios = run_scenario_analysis()

    print("\n── Scenario Results ──")
    print(f"  {'Scenario':<14} {'CAPEX':>10} {'NPV':>12} "
          f"{'IRR':>8} {'Payback':>9} {'Verdict':>8}")
    print(f"  {'─'*65}")
    for _, row in df_scenarios.iterrows():
        print(f"  {row['scenario']:<14} "
              f"EUR {row['capex_eur']:>7,.0f} "
              f"EUR {row['npv_eur']:>8,.0f} "
              f"{row['irr_pct']:>7.1f}% "
              f"{str(row['payback_years']):>8} yr "
              f"{'✅ GO' if row['verdict']=='GO' else '❌ NO-GO':>8}")

    # 4. Visualisations
    print("\n[4/4] Generating charts...")
    plot_tornado(df_tornado, base_npv, output_dir)
    plot_scenario_comparison(df_scenarios, output_dir)
    plot_cumulative_cashflow(output_dir)

    # 5. Save
    df_sens.to_csv(os.path.join(processed_dir,
                   "sensitivity_analysis.csv"), index=False)
    df_scenarios.to_csv(os.path.join(processed_dir,
                        "scenario_analysis.csv"), index=False)
    print(f"\n✓ Results saved to data/processed/")

    print("\n" + "=" * 55)
    print("   ROBUSTNESS VERDICT")
    print("=" * 55)
    all_go = (df_scenarios["verdict"] == "GO").all()
    npv_always_positive = (df_sens["npv_eur"] > 0).all()
    print(f"  NPV > 0 across all sensitivity variants: "
          f"{'✅ YES' if npv_always_positive else '⚠️  NO'}")
    print(f"  GO verdict holds across all 3 scenarios: "
          f"{'✅ YES' if all_go else '⚠️  NO — review Bear Case'}")
    if all_go and npv_always_positive:
        print("\n  ✅ INVESTMENT IS ROBUST — GO verdict confirmed")
    else:
        print("\n  ⚠️  CONDITIONAL GO — sensitivity warrants review")
    print("=" * 55)
    print("\n✅ Sensitivity analysis complete — ready for Phase 4 reporting")