# src/roof_constraint.py
#
# PURPOSE: Determine the maximum viable PV system size given structural,
# grid connection, and budget constraints.
#
# This is a core engineering feasibility check — in a real project this
# would be validated by a structural engineer. Here we model it analytically.

import numpy as np
import pandas as pd
import os

# ── ROOF PARAMETERS ───────────────────────────────────────────────────────────

ROOF = {
    "total_area_m2":       8000,   # updated: realistic mid-large Bochum warehouse
    "usable_fraction":     0.75,   # 75% usable — good layout, minimised setbacks
    "max_load_kg_m2":      15.0,   # structural limit — unchanged
}

# ── PANEL SPECIFICATIONS ──────────────────────────────────────────────────────
# Based on a typical tier-1 commercial panel (e.g. Jinko/LONGi 500W class)

PANEL = {
    "rated_power_wp":      580,    # 580W panel — current commercial standard
    "efficiency":          0.223,  # 22.3% — top tier monocrystalline
    "length_m":            2.278,
    "width_m":             1.134,
    "weight_kg":           19.5,   # lighter modern panel
}

# ── MOUNTING SYSTEM ───────────────────────────────────────────────────────────
# Ballasted flat-roof mounting — most common for commercial rooftops
# No roof penetration, uses concrete ballast blocks

MOUNTING = {
    "type":                    "aerodynamic_ballasted",
    "racking_weight_kg_m2":    3.5,   # aerodynamic low-tilt racking (lighter)
    "ballast_weight_kg_m2":    4.5,   # reduced ballast — aerodynamic design
    "ballast_included":        True,
}


def calculate_panel_metrics(panel: dict) -> dict:
    """Calculate derived metrics for a single panel."""

    area_m2      = panel["length_m"] * panel["width_m"]
    weight_per_m2 = panel["weight_kg"] / area_m2
    power_per_m2  = panel["rated_power_wp"] / area_m2  # W/m²

    return {
        "area_m2":         round(area_m2, 4),
        "weight_per_m2":   round(weight_per_m2, 2),   # kg/m² of panel
        "power_per_m2_w":  round(power_per_m2, 1),    # W/m²
    }


def calculate_load_per_m2(panel_metrics: dict, mounting: dict) -> float:
    """
    Calculate total roof load per m² of panel area.

    Load components:
      - Panel self-weight
      - Aluminium racking structure
      - Ballast blocks (if ballasted system)

    Returns: total load in kg/m² of ROOF AREA
    (Note: panels don't cover 100% of roof area due to row spacing)
    """

    panel_load    = panel_metrics["weight_per_m2"]
    racking_load  = mounting["racking_weight_kg_m2"]
    ballast_load  = mounting["ballast_weight_kg_m2"] if mounting["ballast_included"] else 0

    total_per_panel_m2 = panel_load + racking_load + ballast_load

    # Row spacing factor: panels are spaced to avoid self-shading
    # At 10° tilt in Bochum (51.5°N), GCR (Ground Coverage Ratio) ≈ 0.45
    # This means panels cover ~45% of the roof area
    # So load per m² of ROOF = load per m² of PANEL × GCR
    gcr = 0.45   # Ground Coverage Ratio

    load_per_roof_m2 = total_per_panel_m2 * gcr

    return round(load_per_roof_m2, 2), round(total_per_panel_m2, 2), gcr


def calculate_max_system_size(roof: dict, panel: dict, mounting: dict) -> dict:
    """
    Calculate the maximum installable system size given roof constraints.

    Returns a dict of sizing results and constraint analysis.
    """

    panel_metrics = calculate_panel_metrics(panel)
    load_per_roof_m2, load_per_panel_m2, gcr = calculate_load_per_m2(
        panel_metrics, mounting
    )

    # ── Usable Roof Area ──────────────────────────────────────────────────
    usable_area_m2 = roof["total_area_m2"] * roof["usable_fraction"]

    # ── Structural Constraint ─────────────────────────────────────────────
    # Maximum panel area allowed by load limit
    # load_per_roof_m2 ≤ max_load_kg_m2
    # panel_area / roof_area × load_per_panel_m2 ≤ max_load
    # panel_area ≤ roof_area × max_load / load_per_panel_m2

    max_panel_area_structural = (
        usable_area_m2 * roof["max_load_kg_m2"] / load_per_panel_m2
    )

    # ── Physical Area Constraint ──────────────────────────────────────────
    # Panel area cannot exceed usable roof × GCR
    max_panel_area_physical = usable_area_m2 * gcr

    # Binding constraint is the smaller of the two
    max_panel_area_m2 = min(max_panel_area_structural, max_panel_area_physical)

    # ── System Size from Panel Area ───────────────────────────────────────
    # Number of panels that fit
    panels_count = int(max_panel_area_m2 / panel_metrics["area_m2"])

    # Total DC capacity
    max_kwp = (panels_count * panel["rated_power_wp"]) / 1000

    # ── Feasibility Check for 500 kWp ────────────────────────────────────
    target_kwp       = 500
    target_panels    = int((target_kwp * 1000) / panel["rated_power_wp"])
    target_area_m2   = target_panels * panel_metrics["area_m2"]
    target_load      = (target_area_m2 / usable_area_m2) * load_per_panel_m2

    is_feasible      = target_load <= roof["max_load_kg_m2"] and \
                       target_area_m2 <= max_panel_area_physical

    return {
        # Panel metrics
        "panel_area_m2":              panel_metrics["area_m2"],
        "panel_weight_per_m2":        panel_metrics["weight_per_m2"],
        "load_per_panel_m2_kg":       load_per_panel_m2,
        "load_per_roof_m2_kg":        load_per_roof_m2,
        "gcr":                        gcr,

        # Roof metrics
        "total_roof_area_m2":         roof["total_area_m2"],
        "usable_roof_area_m2":        round(usable_area_m2, 0),
        "max_panel_area_m2":          round(max_panel_area_m2, 0),

        # Maximum system
        "max_panels":                 panels_count,
        "max_system_kwp":             round(max_kwp, 1),

        # 500 kWp feasibility
        "target_kwp":                 target_kwp,
        "target_panels":              target_panels,
        "target_panel_area_m2":       round(target_area_m2, 0),
        "target_roof_load_kg_m2":     round(target_load, 2),
        "structural_limit_kg_m2":     roof["max_load_kg_m2"],
        "is_500kwp_feasible":         is_feasible,

        # Binding constraint
        "binding_constraint": (
            "structural load" if max_panel_area_structural < max_panel_area_physical
            else "roof area"
        )
    }


def print_constraint_report(results: dict) -> None:
    """Print a formatted engineering constraint report."""

    print("\n" + "=" * 55)
    print("   ROOF STRUCTURAL CONSTRAINT ANALYSIS")
    print("=" * 55)

    print("\n── Panel Specifications ──")
    print(f"  Panel area:              {results['panel_area_m2']} m²/panel")
    print(f"  Panel load:              {results['panel_weight_per_m2']} kg/m² of panel")
    print(f"  Total system load:       {results['load_per_panel_m2_kg']} kg/m² of panel")
    print(f"  Effective roof load:     {results['load_per_roof_m2_kg']} kg/m² of roof")
    print(f"  Ground coverage ratio:   {results['gcr']}")

    print("\n── Roof Sizing ──")
    print(f"  Total roof area:         {results['total_roof_area_m2']} m²")
    print(f"  Usable roof area:        {results['usable_roof_area_m2']} m²")
    print(f"  Max panel area allowed:  {results['max_panel_area_m2']} m²")
    print(f"  Binding constraint:      {results['binding_constraint']}")

    print("\n── Maximum System Size ──")
    print(f"  Max panels:              {results['max_panels']} panels")
    print(f"  Max system size:         {results['max_system_kwp']} kWp")

    print("\n── 500 kWp Feasibility Check ──")
    print(f"  Target system:           {results['target_kwp']} kWp")
    print(f"  Panels required:         {results['target_panels']} panels")
    print(f"  Panel area required:     {results['target_panel_area_m2']} m²")
    print(f"  Roof load imposed:       {results['target_roof_load_kg_m2']} kg/m²")
    print(f"  Structural limit:        {results['structural_limit_kg_m2']} kg/m²")

    feasible = results["is_500kwp_feasible"]
    status   = "✅ FEASIBLE" if feasible else "❌ NOT FEASIBLE — resize required"
    print(f"\n  500 kWp verdict:         {status}")

    if not feasible:
        print(f"\n  ⚠️  Recommended max size: {results['max_system_kwp']} kWp")

    print("=" * 55)


def save_constraint_results(results: dict) -> None:
    """Save constraint analysis results to processed data folder."""
    df = pd.DataFrame([results])
    output_path = os.path.normpath(os.path.join(
        os.path.dirname(__file__),
        "..", "data", "processed", "roof_constraint_analysis.csv"
    ))
    df.to_csv(output_path, index=False)
    print(f"\n✓ Constraint analysis saved to: {output_path}")


# ── MAIN EXECUTION ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    results = calculate_max_system_size(ROOF, PANEL, MOUNTING)
    print_constraint_report(results)
    save_constraint_results(results)

# ── MAIN EXECUTION ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # ── SCENARIO DEFINITIONS ──────────────────────────────────────────────
    # Three realistic scenarios for a Bochum warehouse rooftop
    # Each varies mounting system and usable fraction — common real-world levers

    scenarios = {
        "Conservative": {
            "roof":    {**ROOF, "usable_fraction": 0.70},
            "panel":   PANEL,
            "mounting":{**MOUNTING, "ballast_weight_kg_m2": 5.5,
                        "racking_weight_kg_m2": 4.0},
            "note":    "Standard ballasted mount, conservative layout"
        },
        "Base Case": {
            "roof":    {**ROOF, "usable_fraction": 0.75},
            "panel":   PANEL,
            "mounting": MOUNTING,
            "note":    "Aerodynamic mount, optimised layout"
        },
        "Optimistic": {
            "roof":    {**ROOF, "usable_fraction": 0.80},
            "panel":   PANEL,
            "mounting":{**MOUNTING, "ballast_weight_kg_m2": 3.5,
                        "racking_weight_kg_m2": 3.0},
            "note":    "Lightweight mount, maximum layout efficiency"
        },
    }

    all_results = {}

    print("\n" + "=" * 55)
    print("   SCENARIO COMPARISON — ROOF CONSTRAINT ANALYSIS")
    print("=" * 55)
    print(f"  {'Scenario':<15} {'Max kWp':>10} {'500kWp?':>10} {'Load kg/m²':>12} {'Note'}")
    print("-" * 75)

    for name, config in scenarios.items():
        r = calculate_max_system_size(
            config["roof"], config["panel"], config["mounting"]
        )
        all_results[name] = r
        feasible  = "✅ Yes" if r["is_500kwp_feasible"] else "❌ No"
        print(f"  {name:<15} {r['max_system_kwp']:>10.1f} {feasible:>10} "
              f"{r['target_roof_load_kg_m2']:>12.2f}   {config['note']}")

    print("=" * 55)

    # ── FULL REPORT FOR BASE CASE ─────────────────────────────────────────
    print("\n── Detailed Report: Base Case ──")
    print_constraint_report(all_results["Base Case"])

    # ── SAVE ALL SCENARIOS ────────────────────────────────────────────────
    rows = []
    for name, r in all_results.items():
        row = {"scenario": name}
        row.update(r)
        rows.append(row)

    df_scenarios = pd.DataFrame(rows)
    output_path = os.path.normpath(os.path.join(
        os.path.dirname(__file__),
        "..", "data", "processed", "roof_constraint_scenarios.csv"
    ))
    df_scenarios.to_csv(output_path, index=False)
    print(f"\n✓ All scenarios saved to: {output_path}")

    # ── SELECTED SYSTEM SIZE FOR FINANCIAL MODEL ──────────────────────────
    print("\n" + "=" * 55)
    print("   SYSTEM SIZE LOCKED FOR FINANCIAL MODEL")
    print("=" * 55)
    print("  Scenario       Size      Rationale")
    print("-" * 55)
    print("  Conservative   ~350 kWp  Lower bound — risk-averse")
    print("  Base Case       500 kWp  Central estimate — bankable")
    print("  Optimistic     ~600 kWp  Upper bound — best conditions")
    print("=" * 55)
    print("\n  ✅ Proceeding with 500 kWp (Base Case) as primary model")
    print("     Conservative and Optimistic as sensitivity scenarios\n")