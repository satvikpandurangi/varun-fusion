"""
Verification, baseline evaluation, and explainability endpoints for VARUN-FUSION.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from app.adapters.factory import get_adapter
from app.blend.ml_gate import get_ml_gate
from app.core.config import get_config
from app.skill.evaluate import run_evaluation

router = APIRouter(tags=["Verification & Explainability"])
DISCLAIMER_TEXT = "Forecaster guidance — not a public warning"


@router.get("/skill")
def get_skill_history(
    variable: str = Query("rain24_mm"),
    lead: Optional[int] = Query(None),
    region: Optional[str] = Query("all"),
    metric: Optional[str] = Query(None),
) -> Dict[str, Any]:
    parquet_path = Path("data/skill_history.parquet")
    if not parquet_path.exists():
        raise HTTPException(status_code=404, detail="Skill history not found. Run backfill/evaluation first.")

    df = pd.read_parquet(parquet_path)
    df = df[df["variable"] == variable]
    if lead is not None:
        df = df[df["lead"] == lead]
    if region is not None:
        df = df[df["region"] == region]

    # Convert cycle to ISO string
    if "cycle" in df.columns:
        df["cycle"] = df["cycle"].astype(str)

    records = df.to_dict(orient="records")
    return {
        "variable": variable,
        "region": region,
        "lead": lead,
        "total_records": len(records),
        "records": records,
        "disclaimer": DISCLAIMER_TEXT,
    }


@router.get("/evaluation")
def get_evaluation_results(
    variable: str = Query("rain24_mm"),
    lead: Optional[int] = Query(None),
) -> Dict[str, Any]:
    parquet_path = Path("data/evaluation_results.parquet")
    if not parquet_path.exists():
        logger.info("Evaluation results not found; running holdout evaluation...")
        df = run_evaluation()
    else:
        df = pd.read_parquet(parquet_path)

    df_filtered = df[df["variable"] == variable]
    if lead is not None:
        df_filtered = df_filtered[df_filtered["lead"] == lead]

    records = df_filtered.to_dict(orient="records")
    return {
        "variable": variable,
        "lead": lead,
        "disclaimer": DISCLAIMER_TEXT,
        "total_entities": len(records),
        "results": records,
    }


@router.get("/explain")
def explain_point_prediction(
    lat: float = Query(...),
    lon: float = Query(...),
    source_id: str = Query("ecmwf_ifs"),
    variable: str = Query("rain24_mm"),
    lead: int = Query(24),
    cycle: str = Query("2025-08-12"),
) -> Dict[str, Any]:
    """
    Forecaster explainability tool: returns Tree-SHAP feature contributions
    explaining why a model received its predicted error and weight at this location.
    """
    dt = datetime.strptime(cycle, "%Y-%m-%d")
    cfg = get_config()
    gate = get_ml_gate(variable)

    models = [m for m in cfg.sources.keys() if cfg.sources[m].enabled]
    raw_fcsts = {}
    for mid in models:
        ad = get_adapter(mid)
        ds = ad.fetch(dt, leads=[lead], variables=[variable])
        raw_fcsts[mid] = ds[variable].sel(lead=lead).values

    feature_contribs = gate.explain_point_prediction(
        cycle=dt,
        lead=lead,
        source_id=source_id,
        lat=lat,
        lon=lon,
        raw_forecasts=raw_fcsts,
    )

    importances = gate.get_feature_importances()

    return {
        "cycle": cycle,
        "variable": variable,
        "lead": lead,
        "lat": lat,
        "lon": lon,
        "source_id": source_id,
        "disclaimer": DISCLAIMER_TEXT,
        "shap_contributions": feature_contribs,
        "global_feature_importances": importances,
    }
