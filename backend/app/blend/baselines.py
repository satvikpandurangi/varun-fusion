"""
Baseline blending algorithms for VARUN-FUSION.
Implements:
- B0: Best single model (from recent verification skill)
- B1: Equal-weight multi-model ensemble mean
- B2: Inverse-error weighting w_m ∝ 1 / (RMSE_m + ε)^p
With strict weight constraints: w_m >= 0, Σ w_m = 1, and optional floor/cap.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np
from app.core.config import get_config
from app.core.logging import logger
from app.skill.engine import RollingSkillEngine


def apply_weight_constraints(
    raw_weights: Dict[str, np.ndarray],
    floor: Optional[float] = 0.05,
    cap: Optional[float] = 0.80,
) -> Dict[str, np.ndarray]:
    """
    Enforce weight constraints across models at each spatial grid cell:
    1. w_m >= 0
    2. Optional floor (w_m >= floor) and cap (w_m <= cap)
    3. Renormalize: sum_m w_m = 1.0
    """
    model_ids = list(raw_weights.keys())
    m = len(model_ids)
    if m == 0:
        return {}
    if m == 1:
        # Single model gets weight 1.0 everywhere
        arr = list(raw_weights.values())[0]
        return {model_ids[0]: np.ones_like(arr, dtype=np.float32)}

    # Stack weights: shape (m, n_lat, n_lon) or (m,)
    stacked = np.array([raw_weights[mid] for mid in model_ids], dtype=np.float32)

    # 1. Non-negativity
    stacked = np.maximum(0.0, stacked)

    # 2. Initial sum normalization
    sum_w = np.sum(stacked, axis=0, keepdims=True)
    sum_w = np.where(sum_w < 1e-12, 1.0 / m, sum_w)
    stacked = stacked / sum_w

    # 3. Apply floor and cap if feasible (i.e. floor * m <= 1.0 and cap * m >= 1.0)
    if floor is not None and cap is not None and (floor * m <= 1.0) and (cap * m >= 1.0):
        # Iterative water-filling projection to guarantee bounds and sum=1 simultaneously
        for _ in range(10):
            stacked = np.clip(stacked, floor, cap)
            sum_w = np.sum(stacked, axis=0, keepdims=True)
            diff = 1.0 - sum_w
            # Find elements not at bounds that can absorb the difference
            uncapped = (stacked > floor + 1e-4) & (stacked < cap - 1e-4)
            n_uncapped = np.sum(uncapped, axis=0, keepdims=True)
            has_uncapped = n_uncapped > 0
            adj = np.where(has_uncapped, diff / np.maximum(1, n_uncapped), 0.0)
            stacked = np.where(uncapped, stacked + adj, stacked)
            if np.max(np.abs(diff)) < 1e-5:
                break
        # Final clip and guarantee bounds
        stacked = np.clip(stacked, floor, cap)
        sum_w = np.sum(stacked, axis=0, keepdims=True)
        stacked = stacked / np.where(sum_w < 1e-12, 1.0, sum_w)

    return {model_ids[i]: stacked[i] for i in range(m)}


def compute_b0_weights(
    cycle: datetime,
    variable: str,
    lead: int,
    available_models: List[str],
    skill_engine: RollingSkillEngine,
    grid_shape: Tuple[int, int] = (29, 37),
) -> Dict[str, np.ndarray]:
    """
    B0: Best single model.
    Selects the model with the lowest pilot-wide rolling RMSE.
    Assigns weight 1.0 to the best model and 0.0 to all others.
    """
    if len(available_models) == 1:
        return {available_models[0]: np.ones(grid_shape, dtype=np.float32)}

    # Evaluate mean regional RMSE for each model
    model_errors = {}
    for mid in available_models:
        rmse_grid = skill_engine.compute_gridcell_rmse(cycle, mid, variable, lead)
        model_errors[mid] = float(np.mean(rmse_grid))

    # Pick model with minimum error
    best_model = min(model_errors, key=model_errors.get)
    logger.debug(f"B0 Best model for {variable} lead={lead}h: {best_model} (RMSE={model_errors[best_model]:.3f})")

    weights = {}
    for mid in available_models:
        if mid == best_model:
            weights[mid] = np.ones(grid_shape, dtype=np.float32)
        else:
            weights[mid] = np.zeros(grid_shape, dtype=np.float32)

    return weights


def compute_b1_weights(
    available_models: List[str],
    grid_shape: Tuple[int, int] = (29, 37),
) -> Dict[str, np.ndarray]:
    """
    B1: Equal-weight multi-model ensemble mean.
    Each available model receives weight 1 / M.
    """
    m = len(available_models)
    if m == 0:
        return {}
    eq_weight = 1.0 / float(m)
    return {mid: np.full(grid_shape, eq_weight, dtype=np.float32) for mid in available_models}


def compute_b2_weights(
    cycle: datetime,
    variable: str,
    lead: int,
    available_models: List[str],
    skill_engine: RollingSkillEngine,
    grid_shape: Tuple[int, int] = (29, 37),
    p: float = 2.0,
    epsilon: float = 0.01,
    floor: float = 0.05,
    cap: float = 0.80,
) -> Dict[str, np.ndarray]:
    """
    B2: Inverse-error weighting.
    w_m(x) ∝ 1 / (RMSE_m(x) + ε)^p
    Calculated spatially cell-by-cell using recent rolling verification error fields.
    """
    m = len(available_models)
    if m == 0:
        return {}
    if m == 1:
        return {available_models[0]: np.ones(grid_shape, dtype=np.float32)}

    raw_weights = {}
    for mid in available_models:
        rmse_grid = skill_engine.compute_gridcell_rmse(cycle, mid, variable, lead)
        # Spatial inverse error formulation
        raw_w = 1.0 / np.power(rmse_grid + epsilon, p)
        raw_weights[mid] = raw_w.astype(np.float32)

    # Apply non-negativity, floor, cap, and convex simplex normalization (sum = 1)
    constrained_weights = apply_weight_constraints(raw_weights, floor=floor, cap=cap)
    return constrained_weights


def blend_forecasts(
    forecast_fields: Dict[str, np.ndarray],
    weights: Dict[str, np.ndarray],
) -> np.ndarray:
    """
    Compute blended forecast field:
    F_blend(x) = sum_m w_m(x) * F_m(x)
    """
    models = list(forecast_fields.keys())
    if not models:
        raise ValueError("No forecast fields provided for blending")

    first_field = forecast_fields[models[0]]
    blended = np.zeros_like(first_field, dtype=np.float32)

    for mid in models:
        w = weights.get(mid)
        if w is None:
            continue
        blended += w * forecast_fields[mid]

    return blended
