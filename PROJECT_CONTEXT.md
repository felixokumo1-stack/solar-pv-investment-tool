# Project Context — Solar PV Investment Tool

## What This Project Is
A reproducible, data-driven investment decision tool for a 500 kWp 
commercial rooftop PV system in Bochum, NRW, Germany. Built as an 
MSc portfolio project at Ruhr University Bochum.

## Live Links
- Dashboard: https://felix-pv-investment-dashboard.netlify.app/
- GitHub: https://github.com/felixokumo1-stack/solar-pv-investment-tool

## Current Status
v1.0 complete and published. All phases done:
- Phase 1: Environment setup (Python 3.12, conda, Git)
- Phase 2: PVGIS data fetch, pvlib simulation, roof constraint analysis
- Phase 3: Financial model, sensitivity analysis
- Phase 4: HTML dashboard, README, Netlify deployment

## Key Results (Base Case)
- System: 500 kWp DC, 862 × 580W panels, aerodynamic ballasted mount
- Annual yield: 510 MWh/yr, specific yield 1,020 kWh/kWp, PR = 0.811
- CAPEX: EUR 407,400 (EUR 815/kWp)
- NPV: EUR 537,723 @ 6% discount rate
- IRR: 18.94%
- Payback: 5.3 years
- LCOE: 9.84 ct/kWh
- Verdict: GO — holds across Bear, Base, Bull scenarios

## Technical Stack
- Python 3.12, conda environment named: solar-pv
- pvlib 0.15.0 — PVWatts model
- PVGIS API v5.2 — EU JRC hourly irradiance data
- SMARD.de — German electricity market (BDEW benchmark used)
- pandas, numpy, matplotlib, Chart.js
- Git + GitHub + Netlify

## Repository Structure
solar-pv-investment-tool/
├── src/
│   ├── data_fetcher.py        # PVGIS API client
│   ├── pvlib_simulation.py    # PVWatts energy yield model
│   ├── roof_constraint.py     # Structural feasibility
│   ├── smard_fetcher.py       # Electricity price model
│   ├── financial_model.py     # NPV, IRR, LCOE, cash flow
│   ├── sensitivity.py         # Sensitivity & scenario analysis
│   └── visualise_yield.py     # Chart generation
├── data/raw/                  # PVGIS hourly data (CSV)
├── data/processed/            # Simulation & financial outputs
├── outputs/figures/           # 7 PNG charts
├── outputs/reports/           # HTML dashboard
└── index.html                 # Netlify entry point

## Key Decisions & Rationale
- Roof area: 8,000 m² (realistic mid-large Bochum warehouse)
- GCR: 0.45 (10° tilt, Bochum latitude)
- Mounting: aerodynamic ballasted, 3.5 kg/m² racking + 4.5 kg ballast
- Panel: 580 Wp, 22.3% efficiency, 19.5 kg
- Discount rate: 6% WACC (60% KfW debt @ 3.5% + 40% equity @ 10%)
- Self-consumption: 60% (conservative commercial estimate)
- EEG feed-in tariff: 8.11 ct/kWh (>100 kWp systems)
- Electricity price escalation: 2%/yr from 22.95 ct/kWh base (2025)
- Degradation: 0.4%/yr (monocrystalline PERC manufacturer guarantee)

## Planned Extensions (v2.0)
1. BESS Integration — battery dispatch model, hourly charge/discharge
2. PPA vs Ownership — comparative financial model, Mieterstrom structure
3. LCA — cradle-to-grave, ISO 14040/44, energy & carbon payback
4. Multi-site comparison — automated site ranking across NRW
5. Jupyter notebooks — narrative methodology walkthrough
6. Unit tests — pytest suite for financial model functions

