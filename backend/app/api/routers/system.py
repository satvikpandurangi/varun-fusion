"""
System metadata, source catalog, cycle discovery, and run audit router for VARUN-FUSION.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.adapters.factory import get_adapter
from app.core.config import get_config
from app.db.models import ForecastCycle, ForecastRun, ModelSource
from app.db.session import get_db

router = APIRouter(tags=["System & Status"])
DISCLAIMER_TEXT = "Forecaster guidance — not a public warning"


@router.get("/health")
def get_health() -> Dict[str, Any]:
    cfg = get_config()
    return {
        "status": "HEALTHY",
        "system": cfg.system["name"],
        "version": cfg.system["version"],
        "pilot_region": cfg.domain.name,
        "bbox": cfg.domain.bbox,
        "grid_resolution": cfg.domain.grid_resolution,
        "disclaimer": DISCLAIMER_TEXT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/sources")
def get_sources(db: Session = Depends(get_db)) -> Dict[str, Any]:
    cfg = get_config()
    db_sources = db.query(ModelSource).all()
    source_items = []
    for s in db_sources:
        item = s.to_dict()
        # Enrich with live provenance info from adapter
        try:
            adapter = get_adapter(s.id)
            item["provenance"] = adapter.provenance
        except Exception:
            pass
        source_items.append(item)

    return {
        "sources": source_items,
        "total_sources": len(source_items),
        "disclaimer": DISCLAIMER_TEXT,
    }


@router.get("/cycles")
def get_cycles(db: Session = Depends(get_db)) -> Dict[str, Any]:
    cycles = db.query(ForecastCycle).order_by(ForecastCycle.cycle.desc()).all()
    cycle_list = [c.cycle.strftime("%Y-%m-%d") for c in cycles]
    if not cycle_list:
        # Fallback to standard 2-week pilot dataset range
        cycle_list = [
            f"2025-08-{d:02d}" for d in range(15, 0, -1)
        ]

    return {
        "cycles": cycle_list,
        "latest_cycle": cycle_list[0] if cycle_list else None,
        "disclaimer": DISCLAIMER_TEXT,
    }


@router.get("/runs/{run_id}")
def get_run_details(run_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    run = db.query(ForecastRun).filter(ForecastRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Forecast run ID {run_id} not found")

    fallbacks = [fb.to_dict() for fb in run.fallbacks]
    data = run.to_dict()
    data["fallbacks"] = fallbacks
    data["disclaimer"] = DISCLAIMER_TEXT
    return data
