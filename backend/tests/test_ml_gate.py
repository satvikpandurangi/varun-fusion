"""
Unit tests for VARUN-FUSION Adaptive ML Gate (B3) using LightGBM.
Tests training, temperature-scaled softmax weighting, constraints, and Tree-SHAP explainability.
"""
from datetime import datetime
import numpy as np
import pytest
from app.adapters.factory import get_adapter
from app.blend.ml_gate import get_ml_gate


def test_ml_gate_training_and_importances():
    gate = get_ml_gate("rain24_mm")
    assert gate.booster is not None

    importances = gate.get_feature_importances()
    assert len(importances) > 5
    assert "elevation" in importances
    assert "inter_model_spread" in importances
    assert "lead_hours" in importances
    # Importances should sum to approx 1.0
    assert pytest.approx(sum(importances.values()), 0.05) == 1.0


def test_ml_gate_predict_weights_constraints():
    gate = get_ml_gate("rain24_mm")
    cycle = datetime(2025, 8, 12, 0, 0, 0)
    lead = 24

    # Fetch real raw forecasts
    models = ["ecmwf_ifs", "ecmwf_aifs", "noaa_gfs", "ncmrwf"]
    raw_fcsts = {}
    for mid in models:
        ad = get_adapter(mid)
        ds = ad.fetch(cycle, leads=[lead], variables=["rain24_mm"])
        raw_fcsts[mid] = ds["rain24_mm"].sel(lead=lead).values

    weights, pred_errors = gate.predict_weights(
        cycle=cycle,
        lead=lead,
        raw_forecasts=raw_fcsts,
        tau=1.0,
        floor=0.05,
        cap=0.80,
    )

    assert set(weights.keys()) == set(models)
    assert set(pred_errors.keys()) == set(models)

    # Simplex sum constraint
    sum_w = sum(weights.values())
    assert np.allclose(sum_w, 1.0, atol=1e-5)

    # Floor and cap constraints
    for mid in models:
        w_arr = weights[mid]
        assert (w_arr >= 0.049).all(), f"Floor violated for {mid}: min={w_arr.min()}"
        assert (w_arr <= 0.801).all(), f"Cap violated for {mid}: max={w_arr.max()}"


def test_tree_shap_explainability():
    gate = get_ml_gate("rain24_mm")
    cycle = datetime(2025, 8, 12, 0, 0, 0)
    lead = 24

    models = ["ecmwf_ifs", "ecmwf_aifs"]
    raw_fcsts = {mid: get_adapter(mid).fetch(cycle, leads=[lead], variables=["rain24_mm"])["rain24_mm"].sel(lead=lead).values for mid in models}

    # Explain prediction at Bhubaneswar/Cuttack coordinates (approx 20.3N, 85.8E)
    shap_vals = gate.explain_point_prediction(
        cycle=cycle,
        lead=lead,
        source_id="ecmwf_ifs",
        lat=20.25,
        lon=85.75,
        raw_forecasts=raw_fcsts,
    )

    assert "base_value" in shap_vals
    assert "elevation" in shap_vals
    assert "inter_model_spread" in shap_vals
    assert len(shap_vals) >= 10
