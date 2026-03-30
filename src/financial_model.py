# src/financial_model.py
#
# PURPOSE: Build the complete financial model for the 500 kWp commercial
# rooftop PV investment — CAPEX, revenue streams, 20-year cash flow,
# NPV, IRR, LCOE, and payback period.
#
# STRUCTURE:
#   Section 1 — CAPEX Model
#   Section 2 — EEG 2023 Revenue Logic
#   Section 3 — 20-Year Cash Flow Model
#   Section 4 — Investment KPIs (NPV, IRR, LCOE, Payback)
#   Section 5 — Output & Export

import numpy as np
import pandas as pd
import os

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CAPEX MODEL
# ══════════════════════════════════════════════════════════════════════════════
#
# All costs based on 2024 German commercial PV market benchmarks
# Sources: BSW Solar, Bundesnetzagentur, pvXchange market reports

CAPEX = {
    # PV Modules
    # 580 Wp monocrystalline PERC, tier-1 manufacturer
    # Market price 2024: EUR 0.18–0.22/Wp (post-2022 normalisation)
    "modules_eur_wp":          0.20,   # EUR/Wp

    # Inverter(s)
    # String inverters for commercial rooftop — Fronius/SMA/Huawei
    # Typical cost: EUR 0.06–0.09/Wp
    "inverter_eur_wp":         0.07,   # EUR/Wp

    # Mounting System
    # Aerodynamic ballasted flat-roof system (no penetration)
    # Includes racking, ballast, inter-row clips
    "mounting_eur_wp":         0.08,   # EUR/Wp

    # Electrical BOS (Balance of System)
    # DC/AC cabling, combiner boxes, monitoring system, surge protection
    "electrical_bos_eur_wp":   0.10,   # EUR/Wp

    # Grid Connection & Metering
    # 630 kVA transformer upgrade, bidirectional smart meter, grid study
    # Fixed cost — not scaled with system size
    "grid_connection_eur":     35000,  # EUR fixed

    # Installation & Civil Works
    # Labour, crane hire, roof assessment, safety equipment
    "installation_eur_wp":     0.18,   # EUR/Wp

    # Engineering & Project Management
    # System design, structural survey, grid application, permitting
    "engineering_eur_wp":      0.06,   # EUR/Wp

    # Commissioning & Testing
    # Grid operator inspection, performance testing, handover docs
    "commissioning_eur":       8000,   # EUR fixed

    # Contingency
    # Standard 5% contingency on all variable costs — professional practice
    "contingency_pct":         0.05,   # 5%
}

# System size — Base Case from Phase 2
SYSTEM_KWP = 500   # kWp DC

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — OPERATING PARAMETERS
# ══════════════════════════════════════════════════════════════════════════════

OPEX = {
    # Operations & Maintenance
    # Includes inverter service, cleaning, monitoring subscription
    # Industry benchmark: EUR 10–15/kWp/year for commercial systems
    "om_eur_kwp_yr":           12.0,   # EUR/kWp/year

    # Insurance
    # All-risk PV plant insurance — typical German market rate
    "insurance_eur_kwp_yr":    3.5,    # EUR/kWp/year

    # Asset Management / Monitoring
    # Remote monitoring, reporting, grid operator communication
    "asset_mgmt_eur_yr":       2500,   # EUR/year fixed

    # Inverter Replacement Reserve
    # Inverters typically replaced once in 20-year project life (yr 12–15)
    # We accrue a sinking fund annually
    "inverter_reserve_eur_kwp_yr": 2.0,  # EUR/kWp/year

    # Annual OPEX escalation rate
    "escalation_rate":         0.02,   # 2%/year
}

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — ENERGY & REVENUE PARAMETERS
# ══════════════════════════════════════════════════════════════════════════════

ENERGY = {
    # From our pvlib simulation (Phase 2)
    "annual_yield_kwh":        510035,  # kWh/year — Year 1

    # Panel degradation — monocrystalline PERC
    # Manufacturer guarantee: max 0.4%/year linear degradation
    "degradation_rate":        0.004,   # 0.4%/year

    # Self-consumption ratio
    # Fraction of solar generation consumed on-site (not exported)
    # Commercial warehouse: lighting, HVAC, logistics equipment
    # Typical range: 40–70% depending on load profile
    "self_consumption_ratio":  0.60,    # 60% — conservative commercial estimate

    # EEG 2023 feed-in tariff
    "fit_ct_kwh":              8.11,    # ct/kWh — for >100 kWp systems

    # Electricity price (Year 1 — from our price model)
    "elec_price_yr1_ct_kwh":   22.95,  # ct/kWh — 2025 projected

    # Electricity price escalation
    "elec_price_escalation":   0.02,   # 2%/year
}


def calculate_capex(capex: dict, system_kwp: float) -> dict:
    """
    Calculate full CAPEX breakdown for the PV system.

    Parameters:
        capex      : CAPEX parameter dict
        system_kwp : system size in kWp

    Returns:
        result : dict with itemised and total CAPEX figures
    """

    system_wp = system_kwp * 1000   # convert kWp → Wp

    # Variable costs (scaled with system size)
    modules       = capex["modules_eur_wp"]      * system_wp
    inverter      = capex["inverter_eur_wp"]     * system_wp
    mounting      = capex["mounting_eur_wp"]     * system_wp
    elec_bos      = capex["electrical_bos_eur_wp"] * system_wp
    installation  = capex["installation_eur_wp"] * system_wp
    engineering   = capex["engineering_eur_wp"]  * system_wp

    # Fixed costs
    grid_conn     = capex["grid_connection_eur"]
    commissioning = capex["commissioning_eur"]

    # Subtotal before contingency
    subtotal = (modules + inverter + mounting + elec_bos +
                installation + engineering + grid_conn + commissioning)

    # Contingency
    contingency = subtotal * capex["contingency_pct"]

    # Total CAPEX
    total = subtotal + contingency

    # Specific cost (EUR/kWp) — key benchmark metric
    specific_cost = total / system_kwp

    return {
        "modules_eur":        round(modules, 0),
        "inverter_eur":       round(inverter, 0),
        "mounting_eur":       round(mounting, 0),
        "electrical_bos_eur": round(elec_bos, 0),
        "installation_eur":   round(installation, 0),
        "engineering_eur":    round(engineering, 0),
        "grid_connection_eur":round(grid_conn, 0),
        "commissioning_eur":  round(commissioning, 0),
        "subtotal_eur":       round(subtotal, 0),
        "contingency_eur":    round(contingency, 0),
        "total_capex_eur":    round(total, 0),
        "specific_cost_eur_kwp": round(specific_cost, 0),
        "budget_min_eur":     400000,
        "budget_max_eur":     600000,
        "within_budget":      400000 <= total <= 600000,
    }


def calculate_annual_opex(opex: dict, system_kwp: float, year: int) -> float:
    """
    Calculate total OPEX for a given project year, including escalation.

    Parameters:
        opex       : OPEX parameter dict
        system_kwp : system size in kWp
        year       : project year (1 = first year of operation)

    Returns:
        total annual OPEX in EUR
    """

    escalation = (1 + opex["escalation_rate"]) ** (year - 1)

    om          = opex["om_eur_kwp_yr"]          * system_kwp * escalation
    insurance   = opex["insurance_eur_kwp_yr"]   * system_kwp * escalation
    asset_mgmt  = opex["asset_mgmt_eur_yr"]                   * escalation
    inv_reserve = opex["inverter_reserve_eur_kwp_yr"] * system_kwp * escalation

    return round(om + insurance + asset_mgmt + inv_reserve, 0)


def calculate_annual_revenue(energy: dict, year: int) -> dict:
    """
    Calculate annual revenue streams under EEG 2023.

    Two revenue streams:
      1. Self-consumption savings: avoided electricity purchase cost
      2. Feed-in revenue: exported electricity × EEG tariff

    Parameters:
        energy : energy and revenue parameter dict
        year   : project year (1 = first year of operation)

    Returns:
        dict with itemised revenue figures
    """

    # Energy yield with degradation
    # Year 1 yield × (1 - degradation_rate)^(year-1)
    yield_kwh = (energy["annual_yield_kwh"] *
                 (1 - energy["degradation_rate"]) ** (year - 1))

    # Split into self-consumed and exported
    self_consumed_kwh = yield_kwh * energy["self_consumption_ratio"]
    exported_kwh      = yield_kwh * (1 - energy["self_consumption_ratio"])

    # Electricity price with escalation
    elec_price_ct = (energy["elec_price_yr1_ct_kwh"] *
                     (1 + energy["elec_price_escalation"]) ** (year - 1))

    # Revenue stream 1: Self-consumption savings
    # Every kWh self-consumed = avoided grid purchase at retail price
    self_consumption_eur = self_consumed_kwh * (elec_price_ct / 100)

    # Revenue stream 2: Feed-in tariff (EEG 2023)
    # Fixed tariff for 20 years — guaranteed by EEG
    feedin_eur = exported_kwh * (energy["fit_ct_kwh"] / 100)

    total_revenue = self_consumption_eur + feedin_eur

    return {
        "year":                   year,
        "yield_kwh":              round(yield_kwh, 0),
        "self_consumed_kwh":      round(self_consumed_kwh, 0),
        "exported_kwh":           round(exported_kwh, 0),
        "elec_price_ct_kwh":      round(elec_price_ct, 3),
        "self_consumption_eur":   round(self_consumption_eur, 0),
        "feedin_eur":             round(feedin_eur, 0),
        "total_revenue_eur":      round(total_revenue, 0),
    }


def build_cashflow_model(
    capex_result: dict,
    opex: dict,
    energy: dict,
    system_kwp: float,
    project_years: int = 20,
    discount_rate: float = 0.06
) -> pd.DataFrame:
    """
    Build a full 20-year discounted cash flow model.

    Parameters:
        capex_result   : output of calculate_capex()
        opex           : OPEX parameter dict
        energy         : energy parameter dict
        system_kwp     : system size in kWp
        project_years  : number of years (default 20)
        discount_rate  : WACC / discount rate (default 6%)

    Returns:
        df : DataFrame with full annual cash flow statement
    """

    rows = []
    cumulative_cashflow = -capex_result["total_capex_eur"]  # starts negative

    for year in range(1, project_years + 1):

        revenue = calculate_annual_revenue(energy, year)
        opex_yr = calculate_annual_opex(opex, system_kwp, year)

        # Net cash flow before tax
        net_cashflow = revenue["total_revenue_eur"] - opex_yr

        # Discounted cash flow
        # DCF = CF / (1 + r)^t — present value of future cash flow
        discount_factor  = 1 / (1 + discount_rate) ** year
        discounted_cf    = net_cashflow * discount_factor

        cumulative_cashflow += net_cashflow

        rows.append({
            "year":                   year,
            "yield_kwh":              revenue["yield_kwh"],
            "self_consumed_kwh":      revenue["self_consumed_kwh"],
            "exported_kwh":           revenue["exported_kwh"],
            "elec_price_ct_kwh":      revenue["elec_price_ct_kwh"],
            "self_consumption_eur":   revenue["self_consumption_eur"],
            "feedin_eur":             revenue["feedin_eur"],
            "total_revenue_eur":      revenue["total_revenue_eur"],
            "opex_eur":               opex_yr,
            "net_cashflow_eur":       round(net_cashflow, 0),
            "discount_factor":        round(discount_factor, 6),
            "discounted_cf_eur":      round(discounted_cf, 0),
            "cumulative_cashflow_eur":round(cumulative_cashflow, 0),
        })

    return pd.DataFrame(rows)


def calculate_kpis(
    df: pd.DataFrame,
    capex_result: dict,
    energy: dict,
    discount_rate: float = 0.06
) -> dict:
    """
    Calculate investment KPIs from the cash flow model.

    KPIs:
      - NPV    : Net Present Value (EUR)
      - IRR    : Internal Rate of Return (%)
      - LCOE   : Levelised Cost of Energy (ct/kWh)
      - Payback: Simple payback period (years)
      - DPP    : Discounted payback period (years)
    """

    total_capex = capex_result["total_capex_eur"]

    # ── NPV ───────────────────────────────────────────────────────────────
    # NPV = -CAPEX + sum of discounted annual cash flows
    npv = -total_capex + df["discounted_cf_eur"].sum()

    # ── IRR ───────────────────────────────────────────────────────────────
    # IRR = discount rate at which NPV = 0
    # We pass the full cash flow series including Year 0 (negative CAPEX)
    cashflows = [-total_capex] + df["net_cashflow_eur"].tolist()
    irr = np.irr(cashflows) if hasattr(np, 'irr') else _calculate_irr(cashflows)

    # ── LCOE ──────────────────────────────────────────────────────────────
    # LCOE = Total lifecycle cost (NPV) / Total lifetime energy produced
    # = (CAPEX + NPV of OPEX) / (NPV of energy yield)
    #
    # Standard formula:
    # LCOE = (CAPEX + Σ OPEX_t/(1+r)^t) / Σ E_t/(1+r)^t

    pv_opex   = sum(
        row["opex_eur"] / (1 + discount_rate) ** row["year"]
        for _, row in df.iterrows()
    )
    pv_energy = sum(
        row["yield_kwh"] / (1 + discount_rate) ** row["year"]
        for _, row in df.iterrows()
    )

    lcoe_eur_kwh = (total_capex + pv_opex) / pv_energy
    lcoe_ct_kwh  = lcoe_eur_kwh * 100

    # ── Simple Payback Period ─────────────────────────────────────────────
    # Year when cumulative undiscounted cash flow turns positive
    payback_yr = None
    cumulative = 0
    for _, row in df.iterrows():
        cumulative += row["net_cashflow_eur"]
        if cumulative >= total_capex and payback_yr is None:
            # Interpolate within the year
            prev = cumulative - row["net_cashflow_eur"]
            fraction = (total_capex - prev) / row["net_cashflow_eur"]
            payback_yr = row["year"] - 1 + fraction
            break

    # ── Discounted Payback Period ─────────────────────────────────────────
    dpp_yr = None
    cumulative_dcf = 0
    for _, row in df.iterrows():
        cumulative_dcf += row["discounted_cf_eur"]
        if cumulative_dcf >= total_capex and dpp_yr is None:
            prev = cumulative_dcf - row["discounted_cf_eur"]
            fraction = (total_capex - prev) / row["discounted_cf_eur"]
            dpp_yr = row["year"] - 1 + fraction
            break

    return {
        "npv_eur":              round(npv, 0),
        "irr_pct":              round(irr * 100, 2) if irr else None,
        "lcoe_ct_kwh":          round(lcoe_ct_kwh, 2),
        "payback_years":        round(payback_yr, 1) if payback_yr else ">20",
        "discounted_payback_years": round(dpp_yr, 1) if dpp_yr else ">20",
        "total_capex_eur":      total_capex,
        "total_revenue_20yr":   round(df["total_revenue_eur"].sum(), 0),
        "total_opex_20yr":      round(df["opex_eur"].sum(), 0),
        "total_yield_20yr_mwh": round(df["yield_kwh"].sum() / 1000, 0),
        "discount_rate_pct":    discount_rate * 100,
    }


def _calculate_irr(cashflows: list, guess: float = 0.1) -> float:
    """
    Calculate IRR using Newton-Raphson method.
    Fallback for environments where numpy.irr is unavailable.
    """
    rate = guess
    for _ in range(1000):
        npv  = sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows))
        dnpv = sum(-t * cf / (1 + rate) ** (t + 1)
                   for t, cf in enumerate(cashflows))
        if abs(dnpv) < 1e-10:
            break
        rate -= npv / dnpv
        if rate <= -1:
            return None
    return rate


def print_capex_report(result: dict) -> None:
    print("\n" + "=" * 55)
    print("   CAPEX BREAKDOWN — 500 kWp SYSTEM")
    print("=" * 55)
    items = [
        ("PV Modules",          "modules_eur"),
        ("Inverters",           "inverter_eur"),
        ("Mounting System",     "mounting_eur"),
        ("Electrical BOS",      "electrical_bos_eur"),
        ("Installation",        "installation_eur"),
        ("Engineering & PM",    "engineering_eur"),
        ("Grid Connection",     "grid_connection_eur"),
        ("Commissioning",       "commissioning_eur"),
    ]
    for label, key in items:
        pct = result[key] / result["subtotal_eur"] * 100
        print(f"  {label:<22} EUR {result[key]:>10,.0f}  ({pct:.1f}%)")
    print(f"  {'─'*45}")
    print(f"  {'Subtotal':<22} EUR {result['subtotal_eur']:>10,.0f}")
    print(f"  {'Contingency (5%)':<22} EUR {result['contingency_eur']:>10,.0f}")
    print(f"  {'─'*45}")
    print(f"  {'TOTAL CAPEX':<22} EUR {result['total_capex_eur']:>10,.0f}")
    print(f"  {'Specific Cost':<22} EUR {result['specific_cost_eur_kwp']:>10,.0f}/kWp")
    print(f"\n  Budget range: EUR 400,000 – 600,000")
    if result["total_capex_eur"] < result["budget_min_eur"]:
        status = "⚠️  BELOW BUDGET RANGE — review cost assumptions"
    elif result["within_budget"]:
        status = "✅ WITHIN BUDGET"
    else:
        status = "❌ OVER BUDGET"
    print(f"  Budget status: {status}")
    print("=" * 55)


def print_kpi_report(kpis: dict, capex: dict) -> None:
    print("\n" + "=" * 55)
    print("   INVESTMENT KPIs — 500 kWp, 20 YEARS, 6% DISCOUNT")
    print("=" * 55)
    print(f"  {'Total CAPEX':<35} EUR {kpis['total_capex_eur']:>10,.0f}")
    print(f"  {'Total 20yr Revenue':<35} EUR {kpis['total_revenue_20yr']:>10,.0f}")
    print(f"  {'Total 20yr OPEX':<35} EUR {kpis['total_opex_20yr']:>10,.0f}")
    print(f"  {'Total 20yr Yield':<35} {kpis['total_yield_20yr_mwh']:>10,.0f} MWh")
    print(f"  {'─'*50}")
    print(f"  {'NPV (6% discount rate)':<35} EUR {kpis['npv_eur']:>10,.0f}")
    print(f"  {'IRR':<35} {kpis['irr_pct']:>10.2f}%")
    print(f"  {'LCOE':<35} {kpis['lcoe_ct_kwh']:>10.2f} ct/kWh")
    print(f"  {'Simple Payback':<35} {str(kpis['payback_years']):>10} years")
    print(f"  {'Discounted Payback':<35} {str(kpis['discounted_payback_years']):>10} years")
    print(f"  {'─'*50}")

    # Investment verdict
    npv_ok      = kpis["npv_eur"] > 0
    irr_ok      = kpis["irr_pct"] > 8 if kpis["irr_pct"] else False
    payback_ok  = (isinstance(kpis["payback_years"], float) and
                   kpis["payback_years"] <= 8)

    print(f"\n  Investment Criteria:")
    print(f"  NPV > 0:              {'✅' if npv_ok else '❌'}  "
          f"EUR {kpis['npv_eur']:,.0f}")
    print(f"  IRR > 8%:             {'✅' if irr_ok else '❌'}  "
          f"{kpis['irr_pct']:.2f}%")
    print(f"  Payback ≤ 8 years:    {'✅' if payback_ok else '❌'}  "
          f"{kpis['payback_years']} years")

    all_ok = npv_ok and irr_ok and payback_ok
    verdict = "✅ GO — Investment recommended" if all_ok else \
              "⚠️  CONDITIONAL — Review assumptions" if npv_ok else \
              "❌ NO-GO — Does not meet investment criteria"
    print(f"\n  {'─'*50}")
    print(f"  PRELIMINARY VERDICT:  {verdict}")
    print("=" * 55)


def save_outputs(df: pd.DataFrame, kpis: dict, capex: dict) -> None:
    base = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "data", "processed"))

    cf_path   = os.path.join(base, "cashflow_20yr.csv")
    kpi_path  = os.path.join(base, "investment_kpis.csv")

    df.to_csv(cf_path, index=False)
    pd.DataFrame([kpis]).to_csv(kpi_path, index=False)

    print(f"\n✓ Cash flow model saved: {cf_path}")
    print(f"✓ KPIs saved:            {kpi_path}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    print("=" * 55)
    print("   COMMERCIAL PV INVESTMENT FINANCIAL MODEL")
    print("   500 kWp Rooftop — Bochum, Germany — EEG 2023")
    print("=" * 55)

    # 1. CAPEX
    print("\n[1/4] Calculating CAPEX...")
    capex_result = calculate_capex(CAPEX, SYSTEM_KWP)
    print_capex_report(capex_result)

    # 2. Cash flow model
    print("\n[2/4] Building 20-year cash flow model...")
    df_cf = build_cashflow_model(
        capex_result  = capex_result,
        opex          = OPEX,
        energy        = ENERGY,
        system_kwp    = SYSTEM_KWP,
        project_years = 20,
        discount_rate = 0.06
    )
    print(f"✓ Cash flow model built — {len(df_cf)} years modelled")

    # 3. KPIs
    print("\n[3/4] Calculating investment KPIs...")
    kpis = calculate_kpis(df_cf, capex_result, ENERGY, discount_rate=0.06)
    print_kpi_report(kpis, capex_result)

    # 4. Save
    print("\n[4/4] Saving outputs...")
    save_outputs(df_cf, kpis, capex_result)

    # 5. Print cash flow table preview
    print("\n── Cash Flow Preview (first 5 years) ──")
    preview_cols = ["year", "yield_kwh", "total_revenue_eur",
                    "opex_eur", "net_cashflow_eur", "cumulative_cashflow_eur"]
    print(df_cf[preview_cols].head().to_string(index=False))

    print("\n✅ Financial model complete — ready for Phase 4 sensitivity analysis")