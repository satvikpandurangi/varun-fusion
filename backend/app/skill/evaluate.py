"""
Hold-out verification and multi-model baseline evaluation framework for VARUN-FUSION.
Compares individual NWP/AI models against B0 (Best Single), B1 (Equal), and B2 (Inverse-Error),
with bootstrap confidence intervals and percent gains.
"""
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from app.adapters.factory import get_adapter
from app.blend.baselines import (
    blend_forecasts,
    compute_b0_weights,
    compute_b1_weights,
    compute_b2_weights,
)
from app.blend.ml_gate import get_ml_gate
from app.core.config import get_config
from app.core.logging import logger
from app.skill.engine import RollingSkillEngine
from app.skill.metrics import (
    compute_bias,
    compute_csi,
    compute_far,
    compute_fss_2d,
    compute_mae,
    compute_pod,
    compute_rmse,
)


def compute_bootstrap_ci(
    errors: np.ndarray,
    n_bootstraps: int = 500,
    ci: float = 0.95,
) -> Tuple[float, float]:
    """
    Compute non-parametric bootstrap confidence interval for RMSE.
    errors: array of (fcst - obs) residuals.
    """
    if len(errors) == 0:
        return 0.0, 0.0
    rng = np.random.RandomState(42)
    n = len(errors)
    boot_rmse = []
    for _ in range(n_bootstraps):
        sample = rng.choice(errors, size=n, replace=True)
        boot_rmse.append(np.sqrt(np.mean(sample ** 2)))

    alpha = (1.0 - ci) / 2.0
    low = float(np.percentile(boot_rmse, alpha * 100))
    high = float(np.percentile(boot_rmse, (1.0 - alpha) * 100))
    return low, high


def run_evaluation(
    eval_start: str = "2025-08-08",
    eval_end: str = "2025-08-15",
    train_window_days: int = 7,
) -> pd.DataFrame:
    """
    Execute rigorous hold-out evaluation comparing all raw models and blending methods.
    """
    cfg = get_config()
    start_dt = datetime.strptime(eval_start, "%Y-%m-%d")
    end_dt = datetime.strptime(eval_end, "%Y-%m-%d")

    models = [m for m in cfg.sources.keys() if cfg.sources[m].enabled]
    methods = ["B0_best_single", "B1_equal", "B2_inverse_error", "B3_adaptive"]
    all_evaluated = models + methods

    variables = list(cfg.variables.keys())
    leads = cfg.lead_times_hours
    grid_shape = (len(cfg.domain.lats), len(cfg.domain.lons))

    skill_engine = RollingSkillEngine()
    truth_adapter = get_adapter("truth")

    results = []

    logger.info(f"Running hold-out evaluation from {eval_start} to {eval_end} across {len(all_evaluated)} entities...")

    for var in variables:
        ml_gate = get_ml_gate(var)
        for lead in leads:
            # Container for test-period predictions and truth: entity -> list of 2D fields
            predictions: Dict[str, List[np.ndarray]] = {ent: [] for ent in all_evaluated}
            truth_fields: List[np.ndarray] = []

            curr_cycle = start_dt
            while curr_cycle <= end_dt:
                try:
                    # 1. Fetch truth observation
                    ds_truth = truth_adapter.fetch(curr_cycle, leads=[lead], variables=[var])
                    o_arr = ds_truth[var].sel(lead=lead).values
                    truth_fields.append(o_arr)

                    # 2. Fetch raw models
                    raw_fcsts = {}
                    for mid in models:
                        adapter = get_adapter(mid)
                        ds_m = adapter.fetch(curr_cycle, leads=[lead], variables=[var])
                        m_arr = ds_m[var].sel(lead=lead).values
                        raw_fcsts[mid] = m_arr
                        predictions[mid].append(m_arr)

                    # 3. Compute Blends
                    # B0: Best single
                    w_b0 = compute_b0_weights(curr_cycle, var, lead, models, skill_engine, grid_shape)
                    predictions["B0_best_single"].append(blend_forecasts(raw_fcsts, w_b0))

                    # B1: Equal weight
                    w_b1 = compute_b1_weights(models, grid_shape)
                    predictions["B1_equal"].append(blend_forecasts(raw_fcsts, w_b1))

                    # B2: Inverse error
                    w_b2 = compute_b2_weights(curr_cycle, var, lead, models, skill_engine, grid_shape)
                    predictions["B2_inverse_error"].append(blend_forecasts(raw_fcsts, w_b2))

                    # B3: Adaptive ML Gate
                    w_b3, _ = ml_gate.predict_weights(curr_cycle, lead, raw_fcsts)
                    predictions["B3_adaptive"].append(blend_forecasts(raw_fcsts, w_b3))

                except Exception as e:
                    logger.warning(f"Error evaluating cycle {curr_cycle} for {var} lead={lead}: {e}")

                curr_cycle += timedelta(days=1)

            if not truth_fields:
                continue

            # Stack test cycles across time
            o_stack = np.array(truth_fields)  # (n_test_cycles, n_lat, n_lon)

            # Baseline B0 error for reference
            b0_preds = np.array(predictions["B0_best_single"])
            b0_rmse = compute_rmse(b0_preds, o_stack)

            # Evaluate each entity
            for ent in all_evaluated:
                p_stack = np.array(predictions[ent])
                residuals = (p_stack - o_stack).flatten()

                rmse_val = compute_rmse(p_stack, o_stack)
                mae_val = compute_mae(p_stack, o_stack)
                bias_val = compute_bias(p_stack, o_stack)
                ci_low, ci_high = compute_bootstrap_ci(residuals)

                # Relative gain over best single model (negative delta = improvement)
                if b0_rmse > 1e-6:
                    delta_rmse_pct = ((rmse_val - b0_rmse) / b0_rmse) * 100.0
                else:
                    delta_rmse_pct = 0.0

                row = {
                    "variable": var,
                    "lead": lead,
                    "entity": ent,
                    "kind": "blend" if ent in methods else "raw_model",
                    "n_test_cycles": len(truth_fields),
                    "RMSE": round(rmse_val, 3),
                    "RMSE_ci_low": round(ci_low, 3),
                    "RMSE_ci_high": round(ci_high, 3),
                    "MAE": round(mae_val, 3),
                    "BIAS": round(bias_val, 3),
                    "delta_rmse_pct": round(delta_rmse_pct, 2),
                }

                # Event metrics for rain
                if var == "rain24_mm":
                    th_heavy = cfg.thresholds["rain"]["heavy"]
                    row["CSI_heavy"] = round(compute_csi(p_stack, o_stack, th_heavy), 3)
                    row["POD_heavy"] = round(compute_pod(p_stack, o_stack, th_heavy), 3)
                    row["FAR_heavy"] = round(compute_far(p_stack, o_stack, th_heavy), 3)

                    # Compute mean FSS at scale 3
                    fss_vals = [
                        compute_fss_2d(p_stack[t], o_stack[t], threshold=th_heavy, window_size=3)
                        for t in range(len(truth_fields))
                    ]
                    row["FSS_3"] = round(float(np.mean(fss_vals)), 3)

                results.append(row)

    df_results = pd.DataFrame(results)

    # Persist evaluation results
    out_csv = Path("data/evaluation_results.csv")
    out_parquet = Path("data/evaluation_results.parquet")
    df_results.to_csv(out_csv, index=False)
    df_results.to_parquet(out_parquet, index=False)
    logger.info(f"Evaluation finished: saved {len(df_results)} rows to {out_csv}")

    # Print summary scoreboard to console
    print_evaluation_summary(df_results)
    return df_results


def print_evaluation_summary(df: pd.DataFrame):
    """Print readable comparison scorecard to console."""
    print("\n" + "=" * 90)
    print("VARUN-FUSION MULTI-MODEL VERIFICATION & BLEND EVALUATION SCOREBOARD")
    print("Hold-Out Test Period (Verified against Ground Truth Observations)")
    print("=" * 90)

    for var in df["variable"].unique():
        print(f"\n--- Variable: {var} (Lead: 24h & 72h) ---")
        sub = df[(df["variable"] == var) & (df["lead"].isin([24, 72]))]
        pivot = sub.pivot(index="entity", columns="lead", values=["RMSE", "delta_rmse_pct"])
        print(pivot.to_string())

    print("\n" + "=" * 90)
    print("Legend: delta_rmse_pct < 0 indicates improvement (error reduction) over Best Single Model (B0)")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VARUN-FUSION Baseline Evaluator")
    parser.add_argument("--start", default="2025-08-08", help="Hold-out start date YYYY-MM-DD")
    parser.add_argument("--end", default="2025-08-15", help="Hold-out end date YYYY-MM-DD")
    args = parser.parse_args()
    run_evaluation(args.start, args.end)
