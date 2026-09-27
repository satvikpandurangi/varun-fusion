"""
Unit tests for VARUN-FUSION extreme risk layer, confidence scoring, and safe fallback pipeline.
"""
from datetime import datetime
import numpy as np
import pytest
from app.blend.pipeline import get_blending_pipeline
from app.confidence.scoring import ForecasterConfidenceEngine
from app.extremes.risk_layer import ExtremeRiskEngine


def test_extreme_risk_layer_and_minority_signal():
    engine = ExtremeRiskEngine()
    cycle = datetime(2025, 8, 5, 0, 0, 0)
    lead = 24
    grid_shape = (29, 37)

    # Synthetic setup where model 1 predicts 85 mm (exceeds heavy rain 64.5 mm threshold)
    # but model 2 predicts 10 mm, so average is 47.5 mm (< 64.5 mm threshold)
    raw_fcsts = {
        "m1": np.full(grid_shape, 85.0, dtype=np.float32),
        "m2": np.full(grid_shape, 10.0, dtype=np.float32),
    }
    blended = np.full(grid_shape, 47.5, dtype=np.float32)

    result = engine.compute_extreme_risk_layer(
        cycle=cycle,
        lead=lead,
        raw_forecasts=raw_fcsts,
        blended_forecast=blended,
        variable="rain24_mm",
        threshold_name="heavy",
    )

    assert result["risk_score"].shape == grid_shape
    assert (result["risk_score"] > 0.0).all()
    # Minority signal must be triggered because m1 exceeds 64.5 but blend does not!
    assert result["minority_signal_mask"].all()
    assert result["n_alerts"] == 29 * 37
    first_alert = result["minority_alerts"][0]
    assert first_alert["threshold"] == 64.5
    assert len(first_alert["sources_exceeding"]) == 1
    assert first_alert["sources_exceeding"][0]["source"] == "m1"


def test_confidence_scoring_variations():
    conf_engine = ForecasterConfidenceEngine()
    grid_shape = (29, 37)

    # 1. Perfect agreement across all 4 models -> High confidence
    raw_high = {f"m{i}": np.full(grid_shape, 20.0, dtype=np.float32) for i in range(4)}
    weights_high = {f"m{i}": np.full(grid_shape, 0.25, dtype=np.float32) for i in range(4)}
    res_high = conf_engine.compute_confidence(raw_high, weights_high, "rain24_mm")

    # 2. Extreme divergence across models -> Lower confidence
    raw_low = {
        "m0": np.full(grid_shape, 0.0, dtype=np.float32),
        "m1": np.full(grid_shape, 80.0, dtype=np.float32),
        "m2": np.full(grid_shape, 40.0, dtype=np.float32),
        "m3": np.full(grid_shape, 120.0, dtype=np.float32),
    }
    res_low = conf_engine.compute_confidence(raw_low, weights_high, "rain24_mm")

    assert res_high["mean_confidence"] > res_low["mean_confidence"]
    assert res_high["mean_confidence"] >= 0.70


def test_master_blending_pipeline_and_fallback():
    pipeline = get_blending_pipeline()
    cycle = datetime(2025, 8, 12, 0, 0, 0)

    # 1. Normal Adaptive Blend run
    out_normal = pipeline.run_cycle_blend(
        cycle=cycle,
        variable="rain24_mm",
        lead=24,
        method="adaptive",
    )
    assert out_normal["method_effective"] in ["adaptive", "inverse_error"]
    assert out_normal["blended_grid"].shape == (29, 37)
    assert len(out_normal["weights"]) >= 3
    assert out_normal["disclaimer"] == "Forecaster guidance — not a public warning"

    # 2. Test Safe Fallback with simulated missing model
    out_fallback = pipeline.run_cycle_blend(
        cycle=cycle,
        variable="rain24_mm",
        lead=24,
        method="adaptive",
        simulate_missing_models=["noaa_gfs"],
    )
    assert out_fallback["fallback_active"] is True
    assert "noaa_gfs" in out_fallback["fallback_reason"]
    assert "noaa_gfs" not in out_fallback["weights"]
    # Remaining weights must still sum to 1.0!
    sum_rem = sum(out_fallback["weights"].values())
    assert np.allclose(sum_rem, 1.0, atol=1e-5)
