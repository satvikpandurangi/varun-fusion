"""
Operational forecast endpoints: blended gridded fields, model weights, confidence, extremes, and point inspector.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import numpy as np
from fastapi import APIRouter, HTTPException, Query
from app.adapters.factory import get_adapter
from app.blend.pipeline import get_blending_pipeline
from app.core.config import get_config

router = APIRouter(tags=["Forecast & Blending"])
DISCLAIMER_TEXT = "Forecaster guidance — not a public warning"


def parse_cycle(cycle_str: str) -> datetime:
    try:
        return datetime.strptime(cycle_str, "%Y-%m-%d")
    except ValueError:
        try:
            return datetime.fromisoformat(cycle_str)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid cycle format: '{cycle_str}'. Use YYYY-MM-DD.")


@router.get("/blend")
def get_blend(
    cycle: str = Query("2025-08-05", description="Cycle date YYYY-MM-DD"),
    variable: str = Query("rain24_mm", description="Variable (rain24_mm, t2m_max_c, t2m_mean_c, ws10_ms)"),
    lead: int = Query(24, description="Lead time in hours (24, 48, 72, 96, 120)"),
    method: str = Query("adaptive", description="Blending method (adaptive, inverse_error, equal, best_single)"),
) -> Dict[str, Any]:
    cfg = get_config()
    dt = parse_cycle(cycle)
    pipeline = get_blending_pipeline()
    data = pipeline.run_cycle_blend(dt, variable, lead, method=method)

    # Convert 2D arrays to nested lists for JSON transport
    blended_list = data["blended_grid"].tolist()
    dom_source_list = data["dominant_source"].tolist()
    dom_weight_list = data["dominant_weight"].tolist()
    conf_score_list = data["confidence_score"].tolist()
    conf_label_list = data["confidence_label"].tolist()
    extreme_risk_list = data["extreme_risk"].tolist()

    return {
        "cycle": data["cycle"],
        "variable": variable,
        "lead": lead,
        "method_requested": data["method_requested"],
        "method_effective": data["method_effective"],
        "fallback_active": data["fallback_active"],
        "fallback_reason": data["fallback_reason"],
        "provenance": data["provenance"],
        "disclaimer": DISCLAIMER_TEXT,
        "coordinates": {
            "lats": cfg.domain.lats,
            "lons": cfg.domain.lons,
            "shape": [len(cfg.domain.lats), len(cfg.domain.lons)],
        },
        "grid": blended_list,
        "dominant_source": dom_source_list,
        "dominant_weight": dom_weight_list,
        "confidence_score": conf_score_list,
        "confidence_label": conf_label_list,
        "confidence_mean": data["confidence_mean"],
        "extreme_risk": extreme_risk_list,
        "minority_alerts": data["minority_alerts"],
        "n_minority_alerts": data["n_minority_alerts"],
    }


@router.get("/weights")
def get_weights(
    cycle: str = Query("2025-08-05"),
    variable: str = Query("rain24_mm"),
    lead: int = Query(24),
    method: str = Query("adaptive"),
) -> Dict[str, Any]:
    cfg = get_config()
    dt = parse_cycle(cycle)
    pipeline = get_blending_pipeline()
    data = pipeline.run_cycle_blend(dt, variable, lead, method=method)

    weights_json = {mid: arr.tolist() for mid, arr in data["weights"].items()}
    summary_mean = {mid: round(float(np.mean(arr)), 4) for mid, arr in data["weights"].items()}

    return {
        "cycle": data["cycle"],
        "variable": variable,
        "lead": lead,
        "method": data["method_effective"],
        "provenance": data["provenance"],
        "disclaimer": DISCLAIMER_TEXT,
        "weights": weights_json,
        "mean_weights": summary_mean,
        "dominant_source": data["dominant_source"].tolist(),
        "dominant_weight": data["dominant_weight"].tolist(),
    }


@router.get("/confidence")
def get_confidence(
    cycle: str = Query("2025-08-05"),
    variable: str = Query("rain24_mm"),
    lead: int = Query(24),
) -> Dict[str, Any]:
    dt = parse_cycle(cycle)
    pipeline = get_blending_pipeline()
    data = pipeline.run_cycle_blend(dt, variable, lead)

    return {
        "cycle": data["cycle"],
        "variable": variable,
        "lead": lead,
        "mean_confidence": data["confidence_mean"],
        "pct_high": data["pct_high"],
        "pct_medium": data["pct_medium"],
        "pct_low": data["pct_low"],
        "confidence_grid": data["confidence_score"].tolist(),
        "label_grid": data["confidence_label"].tolist(),
        "disclaimer": DISCLAIMER_TEXT,
    }


@router.get("/extremes")
def get_extremes(
    cycle: str = Query("2025-08-05"),
    variable: str = Query("rain24_mm"),
    lead: int = Query(24),
) -> Dict[str, Any]:
    dt = parse_cycle(cycle)
    pipeline = get_blending_pipeline()
    data = pipeline.run_cycle_blend(dt, variable, lead)

    return {
        "cycle": data["cycle"],
        "variable": variable,
        "lead": lead,
        "extreme_risk": data["extreme_risk"].tolist(),
        "extreme_category": data["extreme_category"].tolist(),
        "minority_alerts": data["minority_alerts"],
        "n_minority_alerts": data["n_minority_alerts"],
        "disclaimer": DISCLAIMER_TEXT,
    }


@router.get("/point")
def get_point_inspection(
    lat: float = Query(..., description="Latitude (e.g. 20.25)"),
    lon: float = Query(..., description="Longitude (e.g. 85.80)"),
    cycle: str = Query("2025-08-05"),
    variable: str = Query("rain24_mm"),
    method: str = Query("adaptive"),
) -> Dict[str, Any]:
    """
    Forecaster point inspector: returns full time series (24h to 120h)
    comparing individual models, the blended value, weights, confidence, and fallback flags.
    """
    cfg = get_config()
    dt = parse_cycle(cycle)
    pipeline = get_blending_pipeline()
    leads = cfg.lead_times_hours

    # Find nearest grid indices
    lats = np.array(cfg.domain.lats)
    lons = np.array(cfg.domain.lons)
    lat_idx = int(np.argmin(np.abs(lats - lat)))
    lon_idx = int(np.argmin(np.abs(lons - lon)))
    nearest_lat = float(lats[lat_idx])
    nearest_lon = float(lons[lon_idx])

    time_series = []

    for lead in leads:
        blend_data = pipeline.run_cycle_blend(dt, variable, lead, method=method)
        raw_vals = {
            mid: round(float(arr[lat_idx, lon_idx]), 2)
            for mid, arr in blend_data["raw_forecasts"].items()
        }
        w_vals = {
            mid: round(float(arr[lat_idx, lon_idx]), 3)
            for mid, arr in blend_data["weights"].items()
        }

        valid_dt = dt + timedelta(hours=lead)
        time_series.append({
            "lead": lead,
            "valid_time": valid_dt.strftime("%Y-%m-%d %H:%M UTC"),
            "blend_value": round(float(blend_data["blended_grid"][lat_idx, lon_idx]), 2),
            "dominant_source": str(blend_data["dominant_source"][lat_idx, lon_idx]),
            "dominant_weight": round(float(blend_data["dominant_weight"][lat_idx, lon_idx]), 3),
            "models": raw_vals,
            "weights": w_vals,
            "confidence_score": round(float(blend_data["confidence_score"][lat_idx, lon_idx]), 2),
            "confidence_label": str(blend_data["confidence_label"][lat_idx, lon_idx]),
            "extreme_risk": round(float(blend_data["extreme_risk"][lat_idx, lon_idx]), 2),
            "fallback_active": blend_data["fallback_active"],
            "fallback_reason": blend_data["fallback_reason"],
        })

    return {
        "requested_lat": lat,
        "requested_lon": lon,
        "matched_lat": nearest_lat,
        "matched_lon": nearest_lon,
        "cycle": dt.strftime("%Y-%m-%d"),
        "variable": variable,
        "unit": cfg.variables[variable].unit,
        "method": method,
        "disclaimer": DISCLAIMER_TEXT,
        "time_series": time_series,
    }
