"""
Unit tests for VARUN-FUSION hold-out evaluation framework.
"""
from pathlib import Path
import pandas as pd
import pytest
from app.skill.evaluate import compute_bootstrap_ci, run_evaluation


def test_compute_bootstrap_ci():
    rng = np_rng = [1.0, -1.0, 2.0, -2.0, 0.5, -0.5, 1.5, -1.5]
    errors = pd.Series(rng).to_numpy()
    low, high = compute_bootstrap_ci(errors, n_bootstraps=200, ci=0.90)
    assert low > 0.0
    assert high > low
    rmse_exact = float((errors ** 2).mean() ** 0.5)
    assert low <= rmse_exact <= high


def test_holdout_evaluation_pipeline():
    # Run evaluation on 3 days of the pilot holdout set
    df_eval = run_evaluation(
        eval_start="2025-08-12",
        eval_end="2025-08-14",
    )

    assert not df_eval.empty
    assert "RMSE" in df_eval.columns
    assert "RMSE_ci_low" in df_eval.columns
    assert "RMSE_ci_high" in df_eval.columns
    assert "delta_rmse_pct" in df_eval.columns

    # Verify that both raw models and blends are included
    entities = set(df_eval["entity"].unique())
    assert "B0_best_single" in entities
    assert "B1_equal" in entities
    assert "B2_inverse_error" in entities
    assert "ecmwf_ifs" in entities

    # Verify output files
    assert Path("data/evaluation_results.csv").exists()
    assert Path("data/evaluation_results.parquet").exists()

    # Verify bootstrap CI ordering
    for _, row in df_eval.iterrows():
        assert row["RMSE_ci_low"] <= row["RMSE_ci_high"]
