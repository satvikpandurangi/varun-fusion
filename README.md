# VARUN-FUSION (वरुण-फ्यूजन)
### Adaptive AI–NWP Multi-Model Forecast Blending System for India

> **Smart India Hackathon 2026** | **Problem Statement 26081**  
> **Ministry of Earth Sciences (MoES)** | **Theme: Disaster Management**  
> **Team CodeX_2026** | **Team ID: 159951**

---

## What is VARUN-FUSION?
VARUN-FUSION is an operational meteorological post-processing and decision-support system. It dynamically harmonizes, scores, and blends multi-model numerical weather prediction (ECMWF IFS, NOAA GFS, NCMRWF) and cutting-edge artificial intelligence forecasts (ECMWF AIFS) against real-time observations (ERA5 and IMD gridded datasets).

### Key Features
- **Rigorous Multi-Model Blending**: Baseline blends ($B_0$ Best-Single, $B_1$ Equal-Weight, $B_2$ Inverse-Error) and $B_3$ Adaptive ML Gate (LightGBM predicting error conditioned on orography, lead time, regime, and model spread).
- **Physical Constraints**: Strictly enforces non-negative weights summing to 1 ($w_m \ge 0, \sum w_m = 1$) with bounded shrinkage ($0.05 \le w_m \le 0.80$).
- **Extreme-Risk Layer & Minority Signal Retention**: Special event weights derived from CSI & FSS ensure convective precipitation cores are never smoothed away; flags cells where any high-skill model predicts extreme events even if the blended average does not.
- **Explainable Diagnostics**: SHAP-style feature contribution bars and regional skill heatmaps explain *why* a particular model was given higher weight.
- **Fail-Safe Fallback Cascade**: Automatic graceful degradation ($B_3 \to B_2 \to B_0$) with full audit logging if an input model is delayed or confidence is degraded.
- **Forecaster-Grade Dashboard**: Dark-mode operations console with MapLibre GL raster overlays, point inspectors, and downloadable PDF shift handover bulletins.

---

## Quickstart (Demo Mode)

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend dashboard)

### 1. Backend Setup
```bash
pip install -r backend/requirements.txt
```

### 2. Generate / Verify 2-Week Pilot Dataset
```bash
# Downloads or initializes cached pilot dataset (2025-08-01 to 2025-08-15)
python -m backend.app.jobs.backfill --start 2025-08-01 --end 2025-08-15
```

### 3. Run Automated Tests
```bash
pytest backend/tests -v
```

### 4. Start Development API
```bash
uvicorn backend.app.api.main:app --reload --port 8000
```
Open interactive Swagger documentation at: `http://localhost:8000/docs`

---

## Pilot Domain
- **Region**: East India & Odisha Coast (Bay of Bengal landfall zone)
- **Bounding Box**: $17.0^\circ\text{N} - 24.0^\circ\text{N}, 81.0^\circ\text{E} - 90.0^\circ\text{E}$ ($0.25^\circ$ grid, $29 \times 37$ cells)
- **Sub-regions**: Coastal Belt, Inland Plains, Eastern Ghats / Highlands
- **Lead Times**: 24h, 48h, 72h, 96h, 120h (daily)
- **Key Variables**: 24h Accumulated Rainfall (03 UTC IMD day), Max Temperature, Mean Temperature, 10m Wind Speed.

---

## Disclaimer
> **Operational Guidance Only**: VARUN-FUSION produces scientific decision-support guidance for certified meteorological forecasters and disaster management authorities; it is not a public warning dissemination service.
