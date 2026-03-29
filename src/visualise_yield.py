# src/visualise_yield.py
#
# PURPOSE: Generate publication-quality charts from the pvlib simulation results.
# These visualisations communicate the energy yield story to a non-technical
# decision-maker — exactly what a real feasibility report requires.

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os

# ── STYLE CONFIGURATION ───────────────────────────────────────────────────────
# Professional colour palette — clean, suitable for engineering reports

COLORS = {
    "primary":     "#2563EB",   # blue
    "secondary":   "#16A34A",   # green
    "accent":      "#F59E0B",   # amber
    "danger":      "#DC2626",   # red
    "light_grey":  "#F1F5F9",
    "mid_grey":    "#94A3B8",
    "dark":        "#1E293B",
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

def load_simulation(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath, index_col="time", parse_dates=True)
    # Force datetime index — timezone-aware timestamps from CSV need explicit conversion
    df.index = pd.to_datetime(df.index, utc=True)
    return df


def plot_monthly_yield(df: pd.DataFrame, output_dir: str) -> None:
    """
    Chart 1: Monthly energy yield bar chart.
    Shows seasonal variation — critical for understanding German solar profile.
    """

    # Resample hourly data to monthly sums (kWh per month)
    monthly = df["P_ac_kW"].resample("ME").sum()
    monthly.index = monthly.index.strftime("%b")   # Jan, Feb, Mar...

    fig, ax = plt.subplots(figsize=(12, 5))

    bars = ax.bar(monthly.index, monthly.values,
                  color=COLORS["primary"], alpha=0.85, width=0.6,
                  edgecolor="white", linewidth=0.5)

    # Add value labels on top of each bar
    for bar, val in zip(bars, monthly.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 500,
                f"{val/1000:.1f}", ha="center", va="bottom",
                fontsize=9, color=COLORS["dark"])

    ax.set_title("Monthly AC Energy Yield — 500 kWp Rooftop PV, Bochum 2020")
    ax.set_ylabel("Energy Yield (MWh)")
    ax.set_xlabel("")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f"{x/1000:.0f} MWh"))
    ax.set_facecolor(COLORS["light_grey"])
    ax.grid(axis="y", color="white", linewidth=1.2)

    # Annotate annual total
    annual = monthly.sum() / 1000
    ax.text(0.98, 0.95, f"Annual Total: {annual:.1f} MWh",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=11, color=COLORS["dark"],
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor=COLORS["mid_grey"]))

    plt.tight_layout()
    path = os.path.join(output_dir, "01_monthly_yield.png")
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"✓ Saved: {path}")


def plot_daily_heatmap(df: pd.DataFrame, output_dir: str) -> None:
    """
    Chart 2: Daily generation heatmap (hour of day × day of year).
    Instantly shows when the system produces power across the year.
    """

    # Pivot: rows = hour of day, columns = day of year
    df_copy = df.copy()
    df_copy["hour"] = df_copy.index.hour
    df_copy["doy"]  = df_copy.index.dayofyear

    pivot = df_copy.pivot_table(
        values="P_ac_kW", index="hour", columns="doy", aggfunc="mean"
    )

    fig, ax = plt.subplots(figsize=(14, 5))

    im = ax.imshow(pivot.values, aspect="auto", origin="lower",
                   cmap="YlOrRd", interpolation="nearest")

    cbar = plt.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    cbar.set_label("AC Power (kW)", fontsize=10)

    ax.set_title("Hourly Power Output Heatmap — Full Year 2020 (500 kWp, Bochum)")
    ax.set_xlabel("Day of Year")
    ax.set_ylabel("Hour of Day")

    # Add month labels on x-axis
    month_starts = [1, 32, 61, 92, 122, 153, 183, 214, 245, 275, 306, 336]
    month_labels = ["Jan","Feb","Mar","Apr","May","Jun",
                    "Jul","Aug","Sep","Oct","Nov","Dec"]
    ax.set_xticks(month_starts)
    ax.set_xticklabels(month_labels)
    ax.set_yticks(range(0, 24, 3))
    ax.set_yticklabels([f"{h:02d}:00" for h in range(0, 24, 3)])

    plt.tight_layout()
    path = os.path.join(output_dir, "02_daily_heatmap.png")
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"✓ Saved: {path}")


def plot_duration_curve(df: pd.DataFrame, output_dir: str) -> None:
    """
    Chart 3: Power duration curve.
    Shows what % of the year the system produces above a given power level.
    Used in grid connection and inverter sizing decisions.
    """

    # Sort AC power in descending order
    sorted_power = np.sort(df["P_ac_kW"].values)[::-1]
    hours        = np.arange(1, len(sorted_power) + 1)
    pct_hours    = hours / len(hours) * 100

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.fill_between(pct_hours, sorted_power,
                    alpha=0.25, color=COLORS["primary"])
    ax.plot(pct_hours, sorted_power,
            color=COLORS["primary"], linewidth=2)

    # Mark key thresholds
    for pct, label in [(25, "25%"), (50, "50%"), (75, "75%")]:
        idx   = int(pct / 100 * len(sorted_power))
        power = sorted_power[idx]
        ax.axvline(pct, color=COLORS["mid_grey"],
                   linestyle="--", linewidth=1)
        ax.text(pct + 0.5, power + 5,
                f"{power:.0f} kW\n@ {label} of hours",
                fontsize=8.5, color=COLORS["dark"])

    ax.set_title("Power Duration Curve — 500 kWp System, Bochum 2020")
    ax.set_xlabel("% of Annual Hours")
    ax.set_ylabel("AC Power Output (kW)")
    ax.set_xlim(0, 100)
    ax.set_ylim(0)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    path = os.path.join(output_dir, "03_duration_curve.png")
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"✓ Saved: {path}")


def plot_scenario_comparison(output_dir: str) -> None:
    """
    Chart 4: Scenario comparison bar chart.
    Conservative / Base Case / Optimistic system sizes and estimated yields.
    Based on our roof constraint analysis results.
    """

    scenarios = {
        "Conservative\n~350 kWp": {
            "kwp":       350,
            "yield_mwh": 357,    # 350 × 1020 kWh/kWp / 1000
            "color":     COLORS["accent"]
        },
        "Base Case\n500 kWp": {
            "kwp":       500,
            "yield_mwh": 510,    # from our pvlib simulation
            "color":     COLORS["primary"]
        },
        "Optimistic\n~600 kWp": {
            "kwp":       600,
            "yield_mwh": 612,    # 600 × 1020 kWh/kWp / 1000
            "color":     COLORS["secondary"]
        },
    }

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    names  = list(scenarios.keys())
    kwps   = [v["kwp"]       for v in scenarios.values()]
    yields = [v["yield_mwh"] for v in scenarios.values()]
    colors = [v["color"]     for v in scenarios.values()]

    # Left: System size
    bars1 = ax1.bar(names, kwps, color=colors, alpha=0.85,
                    edgecolor="white", width=0.5)
    for bar, val in zip(bars1, kwps):
        ax1.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 5,
                 f"{val} kWp", ha="center", fontsize=10,
                 fontweight="bold", color=COLORS["dark"])
    ax1.set_title("System Size by Scenario")
    ax1.set_ylabel("DC Peak Power (kWp)")
    ax1.set_ylim(0, 720)
    ax1.set_facecolor(COLORS["light_grey"])
    ax1.grid(axis="y", color="white", linewidth=1.2)

    # Right: Annual yield
    bars2 = ax2.bar(names, yields, color=colors, alpha=0.85,
                    edgecolor="white", width=0.5)
    for bar, val in zip(bars2, yields):
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + 3,
                 f"{val} MWh", ha="center", fontsize=10,
                 fontweight="bold", color=COLORS["dark"])
    ax2.set_title("Estimated Annual Energy Yield")
    ax2.set_ylabel("Annual AC Energy (MWh/year)")
    ax2.set_ylim(0, 750)
    ax2.set_facecolor(COLORS["light_grey"])
    ax2.grid(axis="y", color="white", linewidth=1.2)

    fig.suptitle("Scenario Comparison — Commercial Rooftop PV, Bochum",
                 fontsize=13, fontweight="bold", y=1.01)

    plt.tight_layout()
    path = os.path.join(output_dir, "04_scenario_comparison.png")
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"✓ Saved: {path}")


# ── MAIN EXECUTION ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # Paths
    sim_path   = os.path.normpath(os.path.join(
        os.path.dirname(__file__),
        "..", "data", "processed", "pvlib_simulation_500kwp_2020.csv"
    ))
    output_dir = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "outputs", "figures"
    ))

    print("Loading simulation data...")
    df = load_simulation(sim_path)
    print(f"✓ Loaded {len(df)} records\n")

    print("Generating charts...")
    plot_monthly_yield(df, output_dir)
    plot_daily_heatmap(df, output_dir)
    plot_duration_curve(df, output_dir)
    plot_scenario_comparison(output_dir)

    print(f"\n✅ All 4 charts saved to: {output_dir}")
    print("   Phase 2 visualisation complete — ready for Phase 3")