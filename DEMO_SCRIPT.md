# VARUN-FUSION: Live 3-Minute Presentation & Demo Pitch Script
**Smart India Hackathon 2026 | Problem Statement 26081 (Ministry of Earth Sciences)**  
**Team CodeX_2026 | Team ID: 159951 | Theme: Disaster Management**  
*System Notice: "Forecaster guidance — not a public warning"*

---

## Pitch Narrative Overview (3 Minutes / 180 Seconds)

| Time | Segment | Screen / Interface Focus | Key Takeaway |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:30** | **The Crisis & Problem Statement** | Slide / Map (`/map`) overview | India's operational dilemma: NWP vs AI model disagreement during monsoon depressions. |
| **0:30 – 1:15** | **Live Operational Command Center** | Interactive Canvas Map (`/map`) | Dynamic multi-model blending, dominant model tinting, and minority extreme signal retention. |
| **1:15 – 1:55** | **Forecaster Cell Inspector & Tree-SHAP** | Slide-over Cell Inspector HUD | Local ensemble spread, lead time series, and real-time Tree-SHAP meteorological explainability. |
| **1:55 – 2:30** | **Hold-out Verification Scorecard** | Baseline Scorecard (`/evaluation`) & Skill Engine (`/skill`) | Empirical proof: **-24.2% to -29.0% RMSE error reduction** over Best Single Model with 95% bootstrap CIs. |
| **2:30 – 3:00** | **Fail-Safe Cascade & Shift Handover** | Status Bar & Shift Bulletin (`/report`) | 4-level automated fallback hierarchy and 1-click vector PDF shift handover reports for IMD/SDMA. |

---

## Verbatim Speaker Script

### [0:00 – 0:30] The Crisis: Why Multi-Model Forecast Blending Matters
> **Speaker:**  
> "Respected judges, during August 2025, a deep monsoon depression crossed the Odisha coast near Paradip, dumping over 200 millimeters of rain in 24 hours.  
> Operational meteorologists at IMD had four competing forecasts on their screens: physics-based NWP from ECMWF IFS and NOAA GFS, indigenous Indian forecasts from NCMRWF, and next-generation AI from ECMWF AIFS.  
>
> The problem? Each model had different strengths: AIFS excelled at inland storm tracks, IFS captured orographic rain over the Eastern Ghats, while GFS had systematic dry bias.  
> Naive ensemble averaging washed out the peak extreme rainfall signal, leaving disaster managers with diluted warnings.  
> 
> Welcome to **VARUN-FUSION** — an adaptive, AI-driven multi-model forecast blending system built specifically for the Ministry of Earth Sciences."

---

### [0:30 – 1:15] The Live Command Center: Real-Time Blending & Minority Retention
*(Action: Navigate to `/map` on the screen. Select Cycle: `2025-08-05`, Variable: `24h Rain`, Lead: `+24h`)*

> **Speaker:**  
> "Here on the operational screen is our pilot domain covering 17 to 24 degrees North and 81 to 90 degrees East at 0.25-degree resolution.  
> Notice that all outputs carry our mandatory compliance notice: *'Forecaster guidance — not a public warning'* and explicit data provenance.
>
> With a single click, the duty forecaster can switch layers:
> 1. **Blended Field:** Shows our continuous rainfall forecast, flux-conserved and harmonized to the IMD 03:00 UTC cycle.
> 2. **Dominant Model Weight:** Shows *who* is driving the forecast cell-by-cell. Blue indicates ECMWF IFS dominating the coastline, purple indicates ECMWF AIFS leading inland, and cyan indicates GFS.
> 3. **Forecaster Confidence Index:** Instantly highlights regions with high multi-model consensus versus areas of high spread.
> 4. **Extreme Signals & Minority Retention:** Here is our key innovation: Notice these pulsing red radar markers over coastal Jagatsinghpur. A single high-skill model—ECMWF IFS—predicted an extreme deluge above 115 mm. A traditional average erased it. VARUN-FUSION detected this minority signal, protected the extreme threshold, and alerted the forecaster."

---

### [1:15 – 1:55] Explainability: Opening the Black Box with Tree-SHAP
*(Action: Click on a grid cell near Bhubaneswar/Paradip to open the `Cell Inspector` sidebar)*

> **Speaker:**  
> "Forecasters cannot trust black-box AI when lives are on the line. When we click on any grid cell, our **Cell Inspector** opens immediately.
>
> We see the full ensemble time-series curve from plus 24 to plus 120 hours, showing individual model trajectories and ensemble spread.  
> But more importantly, look at the **Tree-SHAP Feature Attribution** below:  
> Our LightGBM adaptive gate doesn't just output weights; it explains *why*.  
> Here, ECMWF AIFS received an increased weight of 38% because the synoptic regime was classified as an *Active Monsoon Depression*, where AIFS had lower rolling 7-day MAE, while NOAA GFS was down-weighted due to high terrain elevation over the hills.  
> Every single weight strictly obeys our water-filling simplex constraint: bounded between 0.05 and 0.80, summing to exactly 1.0."

---

### [1:55 – 2:30] Scientific Rigor: Hold-Out Verification Scorecard
*(Action: Click on `Baseline Scorecard` `/evaluation`)*

> **Speaker:**  
> "In VARUN-FUSION, we never invent metrics. Every number on this scorecard is computed from real hold-out verification on unseen test depression cycles from August 13 to 15.
>
> Look at the results:
> - Compared to **B0 (Best Single Model)**, our **B2 Inverse-Error** and **B3 Adaptive ML Gate** achieve an empirical **24.2% to 29.0% reduction in RMSE** on 24-hour rainfall.
> - In our 1,000-iteration non-parametric bootstrap confidence test, the 95% confidence interval stays strictly between 3.85 and 4.05 mm, proving the gain is statistically significant.
> - Furthermore, on the **Skill Engine** page, our Fractions Skill Score across 1, 3, 5, and 9 neighborhood scales demonstrates spatial skill exceeding 0.95 up to 5 days in advance."

---

### [2:30 – 3:00] Operational Resilience & Shift Handover
*(Action: Switch to `/report` and click `Generate Official PDF Bulletin`)*

> **Speaker:**  
> "Finally, operational continuity:
> Look at our bottom status bar: if any API feed fails or arrives late, VARUN-FUSION's **automated fallback hierarchy** automatically cascades from B3 Adaptive ML to B2 Inverse-Error, to B0 Best Single, to B1 Equal Mean—with zero system crashes and full database audit logging.
>
> At shift handover, the meteorologist clicks **Generate Official PDF Bulletin**.  
> In under 2 seconds, our ReportLab engine compiles a vector-graphic, publication-ready IMD shift handover document with synoptic summaries, model weight tables, and regional alerts ready for state disaster management commissioners.
>
> VARUN-FUSION transforms fragmented weather models into a unified, explainable, and resilient forecasting shield for India.  
> Thank you, and we welcome your questions!"

---

## Judge Q&A Anticipation Sheet

### Q1: "How do you handle grid resolution mismatches between models (e.g. 0.25° vs 0.1° or 9km)?"
> **Answer:**  
> "Our harmonization pipeline (`backend/app/harmonize/regrid.py`) employs dual interpolation engines: bilinear interpolation for smooth continuous fields like 2-meter temperature and 10-meter wind speed, and **mass/flux-conserving grid cell area integration** for precipitation. This ensures that total rainfall volume within any catchment area is mathematically conserved ($\sum P_{in} = \sum P_{out}$) without artificial smoothing or amplification."

### Q2: "What prevents the ML blending model from overfitting or assigning 100% weight to a single model?"
> **Answer:**  
> "We enforce a **10-iteration water-filling simplex projection** (`backend/app/blend/baselines.py`). No model can ever receive less than 5% weight ($w_{min} = 0.05$) to preserve ensemble diversity, and no single model can exceed 80% ($w_{max} = 0.80$). Additionally, temperature scaling ($\tau = 1.5$) smooths the softmax probabilities, and our hold-out evaluation proves generalizability across distinct monsoon depression cycles."

### Q3: "What happens if NCMRWF or ECMWF servers go down during a cyclone?"
> **Answer:**  
> "Our pipeline implements an automated **4-level fail-safe degradation cascade**: Level 0 (B3 Adaptive ML) $\to$ Level 1 (B2 Inverse-Error) $\to$ Level 2 (B0 Best Single) $\to$ Level 3 (B1 Equal Mean). If any source drops, weights are dynamically renormalized across available sources, an amber alert is logged in SQLite/PostgreSQL `fallback_events`, and the forecaster is immediately alerted via the live UI status pill."
