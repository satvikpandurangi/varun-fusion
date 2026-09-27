"""
Unit tests for VARUN-FUSION verification and skill engine.
"""
from datetime import datetime
import numpy as np
import pytest
from app.skill.engine import RollingSkillEngine
from app.skill.metrics import (
    compute_bias,
    compute_brier_score,
    compute_contingency,
    compute_crps_ensemble,
    compute_csi,
    compute_far,
    compute_fss_2d,
    compute_mae,
    compute_pod,
    compute_rmse,
)
from app.skill.regions import get_subregion_masks


def test_continuous_metrics():
    obs = np.array([10.0, 20.0, 30.0, 40.0])
    perfect_fcst = np.array([10.0, 20.0, 30.0, 40.0])
    biased_fcst = np.array([12.0, 22.0, 32.0, 42.0])

    assert compute_rmse(perfect_fcst, obs) == 0.0
    assert compute_mae(perfect_fcst, obs) == 0.0
    assert compute_bias(perfect_fcst, obs) == 0.0

    assert pytest.approx(compute_rmse(biased_fcst, obs), 0.01) == 2.0
    assert pytest.approx(compute_mae(biased_fcst, obs), 0.01) == 2.0
    assert pytest.approx(compute_bias(biased_fcst, obs), 0.01) == 2.0


def test_contingency_and_event_metrics():
    # Threshold = 64.5 mm
    th = 64.5
    # Cases:
    # 1: Hit (80, 80)
    # 2: False Alarm (80, 20)
    # 3: Miss (20, 80)
    # 4: Correct Negative (20, 20)
    fcst = np.array([80.0, 80.0, 20.0, 20.0])
    obs = np.array([80.0, 20.0, 80.0, 20.0])

    a, b, c, d = compute_contingency(fcst, obs, th)
    assert a == 1  # Hit
    assert b == 1  # False Alarm
    assert c == 1  # Miss
    assert d == 1  # Correct Negative

    assert pytest.approx(compute_pod(fcst, obs, th), 0.01) == 0.5   # 1 / (1 + 1)
    assert pytest.approx(compute_far(fcst, obs, th), 0.01) == 0.5   # 1 / (1 + 1)
    assert pytest.approx(compute_csi(fcst, obs, th), 0.01) == 1.0 / 3.0 # 1 / (1 + 1 + 1)


def test_fractions_skill_score_scales():
    # 10x10 spatial domain
    grid_obs = np.zeros((10, 10), dtype=float)
    grid_fcst_displaced = np.zeros((10, 10), dtype=float)

    # Place event at (4, 4) in obs
    grid_obs[4, 4] = 100.0
    # Displace forecast to neighboring cell (4, 5) - distance 1 cell
    grid_fcst_displaced[4, 5] = 100.0

    th = 64.5

    # Scale 1 (exact pixel match): displacement yields FSS = 0.0
    fss_1 = compute_fss_2d(grid_fcst_displaced, grid_obs, threshold=th, window_size=1)
    assert pytest.approx(fss_1, 0.01) == 0.0

    # Scale 3 (3x3 neighborhood): window covers adjacent displacement -> FSS > 0
    fss_3 = compute_fss_2d(grid_fcst_displaced, grid_obs, threshold=th, window_size=3)
    assert fss_3 > 0.0

    # Scale 5 (5x5 neighborhood): larger tolerance -> higher FSS
    fss_5 = compute_fss_2d(grid_fcst_displaced, grid_obs, threshold=th, window_size=5)
    assert fss_5 >= fss_3

    # Perfect forecast test
    fss_perfect = compute_fss_2d(grid_obs, grid_obs, threshold=th, window_size=1)
    assert pytest.approx(fss_perfect, 0.01) == 1.0


def test_probabilistic_metrics():
    # Brier score test
    probs = np.array([0.8, 0.2])
    obs = np.array([100.0, 10.0]) # exceedance: [1, 0] at th=50
    th = 50.0

    bs = compute_brier_score(probs, obs, th)
    # (0.8 - 1)^2 = 0.04, (0.2 - 0)^2 = 0.04 -> mean = 0.04
    assert pytest.approx(bs, 0.001) == 0.04

    # CRPS deterministic equals MAE
    crps = compute_crps_ensemble(np.array([12.0, 22.0]), np.array([10.0, 20.0]))
    assert pytest.approx(crps, 0.01) == 2.0


def test_subregion_masks_coverage():
    masks = get_subregion_masks()
    assert "all" in masks
    assert "coastal" in masks
    assert "inland" in masks
    assert "hills" in masks

    assert masks["all"].sum() == 29 * 37
    assert masks["coastal"].sum() > 20
    assert masks["inland"].sum() > 50
    assert masks["hills"].sum() > 20


def test_rolling_skill_engine_on_pilot_data():
    engine = RollingSkillEngine()
    eval_cycle = datetime(2025, 8, 10, 0, 0, 0)
    df_skill = engine.compute_rolling_skill(eval_cycle=eval_cycle, window_days=7, persist_db=True)

    assert not df_skill.empty
    assert "RMSE" in df_skill.columns
    assert "MAE" in df_skill.columns
    assert "BIAS" in df_skill.columns
    assert "source_id" in df_skill.columns

    # Verify all 4 models were evaluated
    evaluated_models = set(df_skill["source_id"].unique())
    assert {"ecmwf_ifs", "ecmwf_aifs", "noaa_gfs", "ncmrwf"}.issubset(evaluated_models)

    # Verify Parquet history was written
    assert engine.parquet_path.exists()

    # Test spatial grid-cell RMSE extraction
    rmse_grid = engine.compute_gridcell_rmse(
        eval_cycle=eval_cycle,
        source_id="ecmwf_ifs",
        variable="rain24_mm",
        lead=24,
        window_days=7,
    )
    assert rmse_grid.shape == (29, 37)
    assert (rmse_grid >= 0.0).all()
