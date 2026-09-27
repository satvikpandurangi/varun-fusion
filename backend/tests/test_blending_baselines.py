"""
Unit tests for VARUN-FUSION baseline blending methods (B0, B1, B2).
Validates mathematical constraints: w_m >= 0, sum w_m = 1, floor, cap, and fallback.
"""
from datetime import datetime
import numpy as np
import pytest
from app.blend.baselines import (
    apply_weight_constraints,
    blend_forecasts,
    compute_b0_weights,
    compute_b1_weights,
    compute_b2_weights,
)
from app.skill.engine import RollingSkillEngine


def test_apply_weight_constraints_simplex():
    # Synthetic raw weights for 3 models
    raw = {
        "m1": np.array([[10.0, 0.0], [5.0, 1.0]], dtype=np.float32),
        "m2": np.array([[2.0, 5.0], [1.0, 1.0]], dtype=np.float32),
        "m3": np.array([[0.0, 5.0], [4.0, 2.0]], dtype=np.float32),
    }

    # 1. Non-negativity and sum = 1
    w = apply_weight_constraints(raw, floor=None, cap=None)
    sum_w = w["m1"] + w["m2"] + w["m3"]
    assert np.allclose(sum_w, 1.0, atol=1e-5)
    for mid in ["m1", "m2", "m3"]:
        assert (w[mid] >= 0.0).all()

    # 2. Floor = 0.05 and Cap = 0.80
    w_bounded = apply_weight_constraints(raw, floor=0.05, cap=0.80)
    sum_bounded = w_bounded["m1"] + w_bounded["m2"] + w_bounded["m3"]
    assert np.allclose(sum_bounded, 1.0, atol=1e-5)
    for mid in ["m1", "m2", "m3"]:
        assert (w_bounded[mid] >= 0.049).all(), f"Floor violated for {mid}: min={w_bounded[mid].min()}"
        assert (w_bounded[mid] <= 0.801).all(), f"Cap violated for {mid}: max={w_bounded[mid].max()}"


def test_b0_best_single_weighting():
    skill_engine = RollingSkillEngine()
    cycle = datetime(2025, 8, 10, 0, 0, 0)
    models = ["ecmwf_ifs", "ecmwf_aifs", "noaa_gfs", "ncmrwf"]

    w_b0 = compute_b0_weights(cycle, "rain24_mm", 24, models, skill_engine, grid_shape=(29, 37))

    # Exactly one model should have weight 1.0 everywhere, others 0.0
    active_models = [mid for mid, arr in w_b0.items() if np.all(arr == 1.0)]
    zero_models = [mid for mid, arr in w_b0.items() if np.all(arr == 0.0)]

    assert len(active_models) == 1
    assert len(zero_models) == 3

    # Total weight equals 1.0 everywhere
    sum_w = sum(w_b0.values())
    assert np.allclose(sum_w, 1.0, atol=1e-5)


def test_b1_equal_weighting():
    models = ["ecmwf_ifs", "ecmwf_aifs", "noaa_gfs", "ncmrwf"]
    w_b1 = compute_b1_weights(models, grid_shape=(29, 37))

    expected_w = 1.0 / len(models)
    for mid in models:
        assert np.allclose(w_b1[mid], expected_w, atol=1e-5)

    sum_w = sum(w_b1.values())
    assert np.allclose(sum_w, 1.0, atol=1e-5)


def test_b2_inverse_error_properties():
    skill_engine = RollingSkillEngine()
    cycle = datetime(2025, 8, 10, 0, 0, 0)
    models = ["ecmwf_ifs", "noaa_gfs"]

    w_b2 = compute_b2_weights(cycle, "rain24_mm", 24, models, skill_engine, grid_shape=(29, 37))

    # Weights must sum to 1 everywhere and be non-negative
    sum_w = w_b2["ecmwf_ifs"] + w_b2["noaa_gfs"]
    assert np.allclose(sum_w, 1.0, atol=1e-5)
    assert (w_b2["ecmwf_ifs"] >= 0.0).all()
    assert (w_b2["noaa_gfs"] >= 0.0).all()

    # Model with lower RMSE must receive higher weight
    rmse_ifs = skill_engine.compute_gridcell_rmse(cycle, "ecmwf_ifs", "rain24_mm", 24)
    rmse_gfs = skill_engine.compute_gridcell_rmse(cycle, "noaa_gfs", "rain24_mm", 24)

    # In cells where IFS has lower error, its weight should be higher
    ifs_better_mask = rmse_ifs < rmse_gfs
    if np.any(ifs_better_mask):
        assert (w_b2["ecmwf_ifs"][ifs_better_mask] >= w_b2["noaa_gfs"][ifs_better_mask]).all()


def test_missing_model_renormalization():
    # If one model is dropped, remaining models renormalize to 1.0
    models_full = ["ecmwf_ifs", "ecmwf_aifs", "noaa_gfs"]
    models_subset = ["ecmwf_ifs", "ecmwf_aifs"]

    w_subset = compute_b1_weights(models_subset, grid_shape=(10, 10))
    assert np.allclose(w_subset["ecmwf_ifs"], 0.5)
    assert np.allclose(w_subset["ecmwf_aifs"], 0.5)
    assert np.allclose(w_subset["ecmwf_ifs"] + w_subset["ecmwf_aifs"], 1.0)


def test_blend_forecasts_linear_combination():
    f_fields = {
        "m1": np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float32),
        "m2": np.array([[20.0, 30.0], [40.0, 50.0]], dtype=np.float32),
    }
    weights = {
        "m1": np.full((2, 2), 0.75, dtype=np.float32),
        "m2": np.full((2, 2), 0.25, dtype=np.float32),
    }

    blended = blend_forecasts(f_fields, weights)
    # Expected: 0.75 * 10 + 0.25 * 20 = 7.5 + 5.0 = 12.5
    assert pytest.approx(float(blended[0, 0]), 0.01) == 12.5
    # Expected: 0.75 * 20 + 0.25 * 30 = 15.0 + 7.5 = 22.5
    assert pytest.approx(float(blended[0, 1]), 0.01) == 22.5
