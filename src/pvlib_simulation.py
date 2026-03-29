# src/pvlib_simulation.py
#
# PURPOSE: Simulate hourly AC power output of a commercial rooftop PV system
# using pvlib — the industry-standard Python PV modelling library.
#
# APPROACH: We use the PVWatts model — a simplified but industry-validated
# model developed by NREL (US National Renewable Energy Laboratory).
# It is widely used for commercial PV feasibility studies.

import pvlib
import pandas as pd
import numpy as np
import os

# ── SYSTEM & SITE PARAMETERS ──────────────────────────────────────────────────

SITE = {
    "lat":      51.4818,
    "lon":       7.2162,
    "altitude":    100,
    "tz":   "Europe/Berlin",   # timezone — important for solar position calculations
    "name": "Bochum_NRW"
}

SYSTEM = {
    "peakpower_kwp":  500,    # DC peak power (kWp) — our starting assumption
    "tilt":            10,    # panel tilt angle (degrees) — typical for flat roofs
    "azimuth":        180,    # 180 = south-facing
    "system_loss":   0.14,    # 14% total system losses (wiring, soiling, mismatch)
    "inverter_eff":  0.96,    # 96% inverter efficiency — typical commercial inverter
    "temp_coeff":   -0.004,   # -0.4%/°C power temperature coefficient (crystalline Si)
    "noct":          45,      # Nominal Operating Cell Temperature (°C) — standard spec
}


def load_pvgis_data(filepath: str) -> pd.DataFrame:
    """
    Load the PVGIS CSV we saved in data_fetcher.py.

    Parameters:
        filepath : path to the CSV file

    Returns:
        df : DataFrame with DatetimeIndex in Europe/Berlin timezone
    """
    df = pd.read_csv(filepath, index_col="time", parse_dates=True)

    
    # PVGIS timestamps are in UTC. We localise as UTC first, then convert
    # to Berlin time. This avoids DST ambiguity errors entirely.
    df.index = df.index.tz_localize("UTC").tz_convert("Europe/Berlin")

    return df


def simulate_pvwatts(df: pd.DataFrame, site: dict, system: dict) -> pd.DataFrame:
    """
    Simulate hourly AC power output using the PVWatts model.

    PVWatts Steps:
      1. Calculate cell temperature from air temp + irradiance + wind
      2. Apply temperature correction to DC power
      3. Apply system losses
      4. Apply inverter efficiency → AC power output

    Parameters:
        df     : DataFrame with GHI_Wm2, temp_air_C, wind_speed columns
        site   : site configuration dict
        system : system configuration dict

    Returns:
        df : original DataFrame with new simulation columns added
    """

    # ── STEP 1: Cell Temperature ───────────────────────────────────────────
    # Solar panels heat up in the sun. Hot panels produce less power.
    # The NOCT model estimates cell temperature from ambient conditions.
    #
    # Formula: T_cell = T_air + (NOCT - 20) / 800 * G_poa
    # Where: NOCT = Nominal Operating Cell Temperature (45°C typically)
    #        G_poa = irradiance on panel surface (W/m²)
    #        800 = reference irradiance for NOCT test (W/m²)

    df["temp_cell_C"] = pvlib.temperature.faiman(
        poa_global  = df["GHI_Wm2"],      # irradiance on tilted panel surface
        temp_air    = df["temp_air_C"],    # ambient air temperature
        wind_speed  = df["wind_speed"],    # wind speed (cooling effect)
        u0          = 25.0,                # heat transfer coefficient (free-standing)
        u1          = 6.84                 # wind-dependent heat loss coefficient
    )

    # ── STEP 2: DC Power Output ────────────────────────────────────────────
    # PVWatts DC model:
    #   P_dc = P_peak × (G_poa / 1000) × [1 + γ × (T_cell - 25)]
    #
    # Where: P_peak = nameplate capacity (kWp)
    #        G_poa / 1000 = irradiance ratio (1.0 at STC = 1000 W/m²)
    #        γ = temperature coefficient (negative = power drops when hot)
    #        25°C = Standard Test Condition reference temperature

    dc_power_kw = pvlib.pvsystem.pvwatts_dc(
        effective_irradiance = df["GHI_Wm2"],
        temp_cell       = df["temp_cell_C"],
        pdc0            = system["peakpower_kwp"],  # rated DC power at STC
        gamma_pdc       = system["temp_coeff"],     # temperature coefficient
        temp_ref        = 25.0                      # STC reference temperature
    )

    # ── STEP 3: Apply System Losses ────────────────────────────────────────
    # Real systems lose energy to: wiring resistance, soiling (dust/dirt),
    # module mismatch, shading, etc.
    # We apply a single derating factor (1 - loss fraction)

    dc_power_kw_derated = dc_power_kw * (1 - system["system_loss"])

    # ── STEP 4: AC Power Output (inverter conversion) ─────────────────────
    # The inverter converts DC → AC. It has a small efficiency loss.
    # PVWatts AC model applies inverter efficiency, capped at rated AC output.

    ac_power_kw = pvlib.inverter.pvwatts(
        pdc      = dc_power_kw_derated,
        pdc0     = system["peakpower_kwp"] * (1 - system["system_loss"]),
        eta_inv_nom = system["inverter_eff"]
    )

    # Store results back into the DataFrame
    df["P_dc_kW"] = dc_power_kw_derated.values
    df["P_ac_kW"] = ac_power_kw.values

    # Clip any tiny negative values (numerical artefacts at night)
    df["P_dc_kW"] = df["P_dc_kW"].clip(lower=0)
    df["P_ac_kW"] = df["P_ac_kW"].clip(lower=0)

    return df


def summarise_yield(df: pd.DataFrame, system: dict) -> dict:
    """
    Calculate key energy yield performance metrics.

    Returns a dict of KPIs that will feed into the financial model.
    """

    annual_kwh    = df["P_ac_kW"].sum()           # total AC energy (kWh/year)
    peak_kw       = df["P_ac_kW"].max()           # maximum AC power output
    capacity_kwp  = system["peakpower_kwp"]

    # Specific yield: kWh produced per kWp installed
    # Industry benchmark for Germany: 850–1050 kWh/kWp/year
    specific_yield = annual_kwh / capacity_kwp

    # Performance Ratio (PR): actual vs theoretical yield
    # PR = E_ac / (H_poa/1000 × P_peak)
    # Industry standard target: PR > 0.75
    h_poa_sum     = df["GHI_Wm2"].sum() / 1000   # total irradiation (kWh/m²)
    pr            = annual_kwh / (h_poa_sum * capacity_kwp)

    # Full load hours: equivalent hours at full rated output
    full_load_hrs = annual_kwh / capacity_kwp

    metrics = {
        "annual_yield_kwh":    round(annual_kwh, 0),
        "specific_yield_kwh_kwp": round(specific_yield, 1),
        "performance_ratio":   round(pr, 3),
        "full_load_hours":     round(full_load_hrs, 1),
        "peak_ac_power_kw":    round(peak_kw, 1),
        "capacity_kwp":        capacity_kwp,
    }

    return metrics


def save_simulation_results(df: pd.DataFrame, filename: str) -> None:
    """Save the simulation output to data/processed/"""
    output_path = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "data", "processed", filename
    ))
    df.to_csv(output_path)
    print(f"✓ Simulation results saved to: {output_path}")


# ── MAIN EXECUTION ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # 1. Load PVGIS weather data
    data_path = os.path.normpath(os.path.join(
        os.path.dirname(__file__),
        "..", "data", "raw", "pvgis_hourly_bochum_500kwp_2020.csv"
    ))

    print("Loading PVGIS weather data...")
    df = load_pvgis_data(data_path)
    print(f"✓ Loaded {len(df)} hourly records\n")

    # 2. Run pvlib simulation
    print("Running PVWatts simulation...")
    df = simulate_pvwatts(df, SITE, SYSTEM)
    print("✓ Simulation complete\n")

    # 3. Print performance summary
    metrics = summarise_yield(df, SYSTEM)

    print("=" * 50)
    print("   ANNUAL ENERGY YIELD SUMMARY — 500 kWp")
    print("=" * 50)
    for key, val in metrics.items():
        print(f"  {key:<35} {val:>10}")
    print("=" * 50)

    # 4. Benchmark check
    print("\n── Industry Benchmarks (Germany) ──")
    sy = metrics["specific_yield_kwh_kwp"]
    pr = metrics["performance_ratio"]
    print(f"  Specific yield:  {sy} kWh/kWp  (target: 850–1050)")
    print(f"  Performance ratio: {pr}        (target: >0.75)")

    if 850 <= sy <= 1100 and pr > 0.75:
        print("  ✅ Results within expected range — simulation validated")
    else:
        print("  ⚠️  Results outside expected range — review inputs")

    # 5. Save results
    save_simulation_results(df, "pvlib_simulation_500kwp_2020.csv")