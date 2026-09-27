"""
Integration tests for VARUN-FUSION FastAPI endpoints (/api/v1).
"""
from fastapi.testclient import TestClient
import pytest
from app.api.main import app

client = TestClient(app)


def test_root_and_health():
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["system"] == "VARUN-FUSION"

    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    data = res_health.json()
    assert data["status"] == "HEALTHY"
    assert "East India" in data["pilot_region"]


def test_sources_and_cycles():
    res_sources = client.get("/api/v1/sources")
    assert res_sources.status_code == 200
    data_sources = res_sources.json()
    assert data_sources["total_sources"] >= 4
    source_ids = [s["id"] for s in data_sources["sources"]]
    assert "ecmwf_ifs" in source_ids
    assert "ecmwf_aifs" in source_ids

    res_cycles = client.get("/api/v1/cycles")
    assert res_cycles.status_code == 200
    data_cycles = res_cycles.json()
    assert len(data_cycles["cycles"]) > 0


def test_blend_endpoint():
    res = client.get("/api/v1/blend?cycle=2025-08-05&variable=rain24_mm&lead=24&method=adaptive")
    assert res.status_code == 200
    data = res.json()
    assert data["variable"] == "rain24_mm"
    assert data["lead"] == 24
    assert len(data["grid"]) == 29
    assert len(data["grid"][0]) == 37
    assert "dominant_source" in data
    assert "confidence_score" in data
    assert "minority_alerts" in data
    assert data["disclaimer"] == "Forecaster guidance — not a public warning"


def test_weights_and_confidence():
    res_w = client.get("/api/v1/weights?cycle=2025-08-05&variable=rain24_mm&lead=24")
    assert res_w.status_code == 200
    data_w = res_w.json()
    assert "weights" in data_w
    assert "mean_weights" in data_w
    assert "ecmwf_ifs" in data_w["weights"]

    res_c = client.get("/api/v1/confidence?cycle=2025-08-05&variable=rain24_mm&lead=24")
    assert res_c.status_code == 200
    data_c = res_c.json()
    assert 0.0 <= data_c["mean_confidence"] <= 1.0


def test_extremes_and_point_inspector():
    res_e = client.get("/api/v1/extremes?cycle=2025-08-05&variable=rain24_mm&lead=24")
    assert res_e.status_code == 200
    data_e = res_e.json()
    assert "extreme_risk" in data_e
    assert "minority_alerts" in data_e

    # Point inspector at Bhubaneswar (approx 20.25N, 85.80E)
    res_p = client.get("/api/v1/point?lat=20.25&lon=85.80&cycle=2025-08-05&variable=rain24_mm")
    assert res_p.status_code == 200
    data_p = res_p.json()
    assert "time_series" in data_p
    assert len(data_p["time_series"]) == 5
    assert "blend_value" in data_p["time_series"][0]
    assert "models" in data_p["time_series"][0]


def test_verification_skill_and_explain():
    res_skill = client.get("/api/v1/skill?variable=rain24_mm&lead=24&region=coastal")
    assert res_skill.status_code == 200
    data_skill = res_skill.json()
    assert "records" in data_skill

    res_explain = client.get("/api/v1/explain?lat=20.25&lon=85.80&cycle=2025-08-12&source_id=ecmwf_ifs")
    assert res_explain.status_code == 200
    data_explain = res_explain.json()
    assert "shap_contributions" in data_explain
    assert "global_feature_importances" in data_explain


def test_pdf_report_generation_and_download():
    # 1. Generate Report
    res_gen = client.post("/api/v1/report?cycle=2025-08-05&region=all&variable=rain24_mm&lead=24&method=adaptive")
    assert res_gen.status_code == 200
    data_gen = res_gen.json()
    assert data_gen["status"] == "GENERATED"
    filename = data_gen["filename"]

    # 2. Download Report PDF
    res_dl = client.get(f"/api/v1/report/download?filename={filename}")
    assert res_dl.status_code == 200
    assert res_dl.headers["content-type"] == "application/pdf"
    assert len(res_dl.content) > 1000
