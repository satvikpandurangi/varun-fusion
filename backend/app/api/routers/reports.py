"""
Shift Handover Report API router for VARUN-FUSION.
Generates, caches, and serves publication-grade forecaster PDF bulletins.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from app.reports.generator import generate_shift_report

router = APIRouter(tags=["Reports & Handover"])
DISCLAIMER_TEXT = "Forecaster guidance — not a public warning"


@router.post("/report")
def create_report(
    cycle: str = Query("2025-08-05", description="Cycle date YYYY-MM-DD"),
    region: str = Query("all", description="Subregion (all, coastal, inland, hills)"),
    variable: str = Query("rain24_mm", description="Variable (rain24_mm, t2m_max_c, ws10_ms)"),
    lead: int = Query(24, description="Lead time in hours"),
    method: str = Query("adaptive", description="Blending method used"),
) -> Dict[str, Any]:
    try:
        dt = datetime.strptime(cycle, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    try:
        pdf_path = generate_shift_report(
            cycle=dt,
            region=region,
            variable=variable,
            lead=lead,
            method=method,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate shift report: {e}")

    return {
        "status": "GENERATED",
        "filename": pdf_path.name,
        "download_url": f"/api/v1/report/download?filename={pdf_path.name}",
        "cycle": cycle,
        "region": region,
        "variable": variable,
        "lead": lead,
        "method": method,
        "disclaimer": DISCLAIMER_TEXT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/report/download")
def download_report(filename: str = Query(...)) -> FileResponse:
    reports_dir = Path("data/reports")
    file_path = reports_dir / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Requested report PDF not found")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/pdf",
    )
