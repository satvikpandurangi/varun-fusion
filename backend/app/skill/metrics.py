"""
Verification metrics engine for VARUN-FUSION.
Implements continuous, probabilistic, categorical event, and spatial neighborhood (FSS) scores.
"""
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.ndimage import uniform_filter


# ---------------------------------------------------------
# 1. Continuous Verification Metrics
# ---------------------------------------------------------

def compute_rmse(fcst: np.ndarray, obs: np.ndarray) -> float:
    """Root Mean Square Error."""
    diff = fcst - obs
    valid = ~np.isnan(diff)
    if not np.any(valid):
        return 0.0
    return float(np.sqrt(np.mean(diff[valid] ** 2)))


def compute_mae(fcst: np.ndarray, obs: np.ndarray) -> float:
    """Mean Absolute Error."""
    diff = np.abs(fcst - obs)
    valid = ~np.isnan(diff)
    if not np.any(valid):
        return 0.0
    return float(np.mean(diff[valid]))


def compute_bias(fcst: np.ndarray, obs: np.ndarray) -> float:
    """Mean Bias Error (positive = overforecast, negative = underforecast)."""
    diff = fcst - obs
    valid = ~np.isnan(diff)
    if not np.any(valid):
        return 0.0
    return float(np.mean(diff[valid]))


# ---------------------------------------------------------
# 2. Categorical & Contingency Table Metrics
# ---------------------------------------------------------

def compute_contingency(
    fcst: np.ndarray,
    obs: np.ndarray,
    threshold: float
) -> Tuple[int, int, int, int]:
    """
    Compute 2x2 contingency table elements for a given threshold:
    A = Hits (forecast >= th, obs >= th)
    B = False Alarms (forecast >= th, obs < th)
    C = Misses (forecast < th, obs >= th)
    D = Correct Negatives (forecast < th, obs < th)
    """
    valid = (~np.isnan(fcst)) & (~np.isnan(obs))
    f = fcst[valid] >= threshold
    o = obs[valid] >= threshold

    a = int(np.sum(f & o))
    b = int(np.sum(f & (~o)))
    c = int(np.sum((~f) & o))
    d = int(np.sum((~f) & (~o)))
    return a, b, c, d


def compute_pod(fcst: np.ndarray, obs: np.ndarray, threshold: float) -> float:
    """Probability of Detection (Hit Rate): A / (A + C)."""
    a, b, c, d = compute_contingency(fcst, obs, threshold)
    denom = a + c
    if denom == 0:
        return 1.0 if (a + b == 0) else 0.0
    return float(a / denom)


def compute_far(fcst: np.ndarray, obs: np.ndarray, threshold: float) -> float:
    """False Alarm Ratio: B / (A + B)."""
    a, b, c, d = compute_contingency(fcst, obs, threshold)
    denom = a + b
    if denom == 0:
        return 0.0
    return float(b / denom)


def compute_csi(fcst: np.ndarray, obs: np.ndarray, threshold: float) -> float:
    """Critical Success Index (Threat Score): A / (A + B + C)."""
    a, b, c, d = compute_contingency(fcst, obs, threshold)
    denom = a + b + c
    if denom == 0:
        # Neither event was forecast nor observed
        return 1.0
    return float(a / denom)


# ---------------------------------------------------------
# 3. Fractions Skill Score (FSS)
# ---------------------------------------------------------

def compute_fss_2d(
    fcst_2d: np.ndarray,
    obs_2d: np.ndarray,
    threshold: float,
    window_size: int = 3,
) -> float:
    """
    Fractions Skill Score (FSS) at neighborhood scale window_size (e.g. 1, 3, 5, 9).
    fcst_2d and obs_2d must be 2D arrays (lat, lon).
    FSS = 1 - (MSE / MSE_ref)
    """
    if fcst_2d.ndim != 2 or obs_2d.ndim != 2:
        raise ValueError("FSS requires 2D spatial grid arrays")

    # Binary exceedance masks
    i_f = (fcst_2d >= threshold).astype(np.float64)
    i_o = (obs_2d >= threshold).astype(np.float64)

    if window_size <= 1:
        p_f = i_f
        p_o = i_o
    else:
        # Spatial neighborhood average using uniform box filter
        p_f = uniform_filter(i_f, size=window_size, mode="nearest")
        p_o = uniform_filter(i_o, size=window_size, mode="nearest")

    mse = np.mean((p_f - p_o) ** 2)
    mse_ref = np.mean(p_f ** 2) + np.mean(p_o ** 2)

    if mse_ref < 1e-12:
        # Neither field had any exceedance anywhere
        return 1.0

    fss = 1.0 - (mse / mse_ref)
    return float(np.clip(fss, 0.0, 1.0))


# ---------------------------------------------------------
# 4. Probabilistic Verification Metrics
# ---------------------------------------------------------

def compute_brier_score(prob_pred: np.ndarray, obs: np.ndarray, threshold: float) -> float:
    """
    Brier Score: mean square error of probabilistic forecast.
    prob_pred: array of predicted probabilities in [0, 1]
    obs: ground truth values
    """
    observed_binary = (obs >= threshold).astype(np.float64)
    valid = (~np.isnan(prob_pred)) & (~np.isnan(observed_binary))
    if not np.any(valid):
        return 0.0
    return float(np.mean((prob_pred[valid] - observed_binary[valid]) ** 2))


def compute_crps_ensemble(fcst_members: np.ndarray, obs: np.ndarray) -> float:
    """
    Continuous Ranked Probability Score (CRPS) for an ensemble forecast.
    fcst_members: shape (n_members, n_points)
    obs: shape (n_points,)
    """
    if fcst_members.ndim == 1:
        # Deterministic case: CRPS equals MAE
        return compute_mae(fcst_members, obs)

    m = fcst_members.shape[0]
    term1 = np.mean(np.abs(fcst_members - obs), axis=0)  # (n_points,)

    # Pairwise difference across members
    diff_matrix = np.abs(fcst_members[:, None, :] - fcst_members[None, :, :])
    term2 = 0.5 * np.mean(diff_matrix, axis=(0, 1))

    crps_points = term1 - term2
    return float(np.nanmean(crps_points))


def compute_reliability_curve(
    prob_pred: np.ndarray,
    obs: np.ndarray,
    threshold: float,
    n_bins: int = 5,
) -> Dict[str, List[float]]:
    """
    Compute calibration curve: forecast probability bins vs observed relative frequency.
    """
    obs_binary = (obs >= threshold).astype(int)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    forecast_probs = []
    observed_freqs = []
    bin_counts = []

    for i in range(n_bins):
        low, high = bin_edges[i], bin_edges[i + 1]
        if i == n_bins - 1:
            mask = (prob_pred >= low) & (prob_pred <= high)
        else:
            mask = (prob_pred >= low) & (prob_pred < high)

        count = int(np.sum(mask))
        bin_counts.append(count)
        if count > 0:
            forecast_probs.append(float(np.mean(prob_pred[mask])))
            observed_freqs.append(float(np.mean(obs_binary[mask])))
        else:
            forecast_probs.append(float((low + high) / 2.0))
            observed_freqs.append(0.0)

    return {
        "bin_centers": [float((bin_edges[i] + bin_edges[i+1])/2) for i in range(n_bins)],
        "forecast_probabilities": forecast_probs,
        "observed_frequencies": observed_freqs,
        "sample_counts": bin_counts,
    }
