# src/data_fetcher.py
#
# PURPOSE: Fetch solar irradiance and climate data from the PVGIS API
# for a given location in Germany.
#
# PVGIS = Photovoltaic Geographical Information System (EU Joint Research Centre)
# API = Application Programming Interface (a way for code to talk to a web service)

import requests   # library for making HTTP requests (like a browser, but in code)
import pandas as pd  # library for working with tabular data (like Excel, but in code)
import json       # library for reading/writing JSON data format
import os         # library for file and folder operations

# --- SITE CONFIGURATION ---
# These are the parameters for our hypothetical commercial site.
# Bochum, NRW, Germany — a realistic industrial/commercial rooftop location.

SITE = {
    "lat": 51.4818,       # Latitude  (decimal degrees, North = positive)
    "lon": 7.2162,        # Longitude (decimal degrees, East = positive)
    "altitude": 100,      # metres above sea level
    "name": "Bochum_NRW"
}

# --- SYSTEM CONFIGURATION ---
# Starting assumption: 500 kWp system
# We will refine this in Step 3 using the roof constraint

SYSTEM = {
    "peakpower": 500,      # kWp — DC peak power of the PV array
    "loss": 14,            # % — system losses (wiring, soiling, mismatch etc.)
    "tilt": 10,            # degrees — panel tilt angle (flat roof = low tilt)
    "azimuth": 180,        # degrees — 180 = south-facing (optimal for Germany)
    "mountingplace": "building",  # 'building' or 'free' — affects temperature model
    "pvtechchoice": "crystSi",    # crystalline silicon — most common commercial panel
}


def fetch_pvgis_hourly(site: dict, system: dict, year: int = 2020) -> pd.DataFrame:
    """
    Fetch hourly irradiance and PV output data from the PVGIS API.

    Parameters:
        site   : dict with lat, lon, altitude
        system : dict with peakpower, loss, tilt, azimuth etc.
        year   : which historical year to pull (2005-2020 available)

    Returns:
        df : pandas DataFrame with hourly data for the full year
    """

    # This is the PVGIS API endpoint for hourly data
    url = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"

    # These are the query parameters — they tell PVGIS exactly what we want
    params = {
        "lat":          site["lat"],
        "lon":          site["lon"],
        "angle":        system["tilt"],
        "aspect":       system["azimuth"] - 180,
        "startyear":    year,
        "endyear":      year,
        "outputformat": "json",
        "browser":      0,
    }
   

    print(f"Fetching PVGIS data for {site['name']} ({site['lat']}°N, {site['lon']}°E)...")

    # Make the API call
    response = requests.get(url, params=params, timeout=30)

    # Check if the call succeeded (HTTP 200 = success)
    if response.status_code != 200:
        raise ConnectionError(f"PVGIS API error: {response.status_code} — {response.text}")

    # Parse the JSON response into a Python dictionary
    raw = response.json()

    # The hourly data lives inside this nested key
    hourly_records = raw["outputs"]["hourly"]

    # Convert list of dicts → pandas DataFrame (a table)
    df = pd.DataFrame(hourly_records)

    # The 'time' column from PVGIS looks like "20200101:0010" — convert to real datetime
    df["time"] = pd.to_datetime(df["time"], format="%Y%m%d:%H%M")
    df = df.set_index("time")  # use time as the row index

    # Rename columns to clearer names
    df = df.rename(columns={
        "G(i)":  "GHI_Wm2",
        "H_sun": "sun_height",
        "T2m":   "temp_air_C",
        "WS10m": "wind_speed",
        "Int":   "interpolated"
    })

    print(f"✓ Retrieved {len(df)} hourly records")
    print(f"✓ Date range: {df.index[0]} → {df.index[-1]}")
    print(f"✓ Peak irradiance recorded: {df['GHI_Wm2'].max():.0f} W/m²")
    print(f"✓ Mean air temperature: {df['temp_air_C'].mean():.1f} °C")
    
    return df


def save_raw_data(df: pd.DataFrame, filename: str) -> None:
    """Save the raw fetched data to the data/raw folder as CSV."""

    # Build the path relative to this file's location
    output_path = os.path.join(
        os.path.dirname(__file__),  # folder where this script lives (src/)
        "..", "data", "raw", filename
    )

    # Normalise the path (resolve any ../ etc.)
    output_path = os.path.normpath(output_path)

    df.to_csv(output_path)
    print(f"✓ Data saved to: {output_path}")


# --- MAIN EXECUTION ---
# This block only runs when you execute this file directly
# (not when it's imported by another script)

if __name__ == "__main__":

    # Fetch hourly data for year 2020
    df_hourly = fetch_pvgis_hourly(SITE, SYSTEM, year=2020)

    # Save to data/raw/
    save_raw_data(df_hourly, "pvgis_hourly_bochum_500kwp_2020.csv")

    # Print a preview of the data table
    print("\n--- Data Preview (first 5 rows) ---")
    print(df_hourly.head())

    print("\n--- Column Summary ---")
    print(df_hourly.describe().round(2))