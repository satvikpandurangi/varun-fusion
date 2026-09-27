"""
Context feature engineering and weather regime classification for VARUN-FUSION.
Generates spatial, temporal, physical, and atmospheric regime features for the ML gate.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from app.core.config import get_config
from app.core.logging import logger
from app.skill.regions import get_subregion_masks

REGIME_LABELS = {
    0: "Active Depression / Heavy Rain",
    1: "Normal Monsoon Flow / Coastal Rain",
    2: "Weak Monsoon / High Inland Heat",
    3: "Post-Depression / Moderate Wind",
}


class WeatherRegimeClassifier:
    """
    K-Means weather regime classifier on domain-mean meteorological anomalies.
    Categorizes the prevailing synoptic state into interpretable weather regimes.
    """

    def __init__(self, n_clusters: int = 4):
        self.n_clusters = n_clusters
        self.kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self.is_fitted = False
        self._init_default_clusters()

    def _init_default_clusters(self):
        """Canonical synoptic regime centroids across Indian monsoon lifecycle."""
        # Archetype feature vectors: [rain_mean_anom, tmax_mean_anom, ws_mean_anom]
        self.archetypes = np.array([
            [60.0, -3.5, 8.0],   # Regime 0: Active depression (high rain, low tmax, high wind)
            [25.0, -1.0, 3.0],   # Regime 1: Normal monsoon flow
            [-10.0, 3.0, -2.0],  # Regime 2: Break monsoon / high heat
            [10.0, 0.5, 4.0],    # Regime 3: Moderate disturbance
        ], dtype=np.float32)
        self.is_fitted = True

    def predict_regime(
        self,
        domain_rain_mean: float,
        domain_tmax_mean: float,
        domain_ws_mean: float,
    ) -> Tuple[int, str]:
        """Classify current domain-mean conditions into a regime id and human-readable label."""
        # Anomalies relative to August monsoon climatology
        # Climatological baselines: rain=15mm, tmax=32.0C, ws=8.0m/s
        anom_rain = domain_rain_mean - 15.0
        anom_tmax = domain_tmax_mean - 32.0
        anom_ws = domain_ws_mean - 8.0

        vec = np.array([anom_rain, anom_tmax, anom_ws], dtype=np.float32)
        # Normalized euclidean distance to canonical regime centroids
        scales = np.array([30.0, 2.0, 4.0], dtype=np.float32) # scale factors
        dists = np.sum(((self.archetypes - vec) / scales) ** 2, axis=1)
        cluster_id = int(np.argmin(dists))
        label = REGIME_LABELS.get(cluster_id, "Normal Monsoon Flow")
        return cluster_id, label


_REGIME_CLASSIFIER = None


def get_regime_classifier() -> WeatherRegimeClassifier:
    global _REGIME_CLASSIFIER
    if _REGIME_CLASSIFIER is None:
        _REGIME_CLASSIFIER = WeatherRegimeClassifier()
    return _REGIME_CLASSIFIER


def compute_elevation_map(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """
    Topographic elevation model (meters ASL) for East India / Odisha domain.
    Captures Eastern Ghats (elevation up to 1100m) and Similipal / Mayurbhanj plateau.
    """
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    # Eastern Ghats ridge: centered around 19.2N, 83.5E, extending northeast
    ghats = 950.0 * np.exp(-((lat_grid - 19.3)**2 / 2.8 + (lon_grid - 83.5)**2 / 2.2))
    # Similipal / Mayurbhanj highland: centered around 21.8N, 86.3E
    similipal = 850.0 * np.exp(-((lat_grid - 21.8)**2 / 1.5 + (lon_grid - 86.3)**2 / 1.5))
    # Coastal plains slope down to sea level at Bay of Bengal
    coastal_fall = np.clip((86.0 - lon_grid) * 30.0, 0.0, 150.0)

    elev = 20.0 + ghats + similipal + coastal_fall
    return np.round(elev, 1).astype(np.float32)


def extract_context_features(
    cycle: datetime,
    lead: int,
    raw_forecasts: Dict[str, np.ndarray],
    variable: str,
) -> pd.DataFrame:
    """
    Extract spatial, temporal, physical, and inter-model context features for each grid cell.
    Returns tabular DataFrame where each row corresponds to one grid cell (lat, lon).
    """
    cfg = get_config()
    lats = np.array(cfg.domain.lats)
    lons = np.array(cfg.domain.lons)
    n_lat = len(lats)
    n_lon = len(lons)
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    # 1. Spatial coordinates and elevation
    elevation = compute_elevation_map(lats, lons)

    # 2. Sub-region IDs (0=all/marine, 1=coastal, 2=inland, 3=hills)
    subregion_masks = get_subregion_masks()
    subregion_id_grid = np.zeros((n_lat, n_lon), dtype=int)
    subregion_id_grid[subregion_masks["coastal"]] = 1
    subregion_id_grid[subregion_masks["inland"]] = 2
    subregion_id_grid[subregion_masks["hills"]] = 3

    # 3. Temporal cyclical encodings
    doy = cycle.timetuple().tm_yday
    sin_doy = float(np.sin(2 * np.pi * doy / 365.25))
    cos_doy = float(np.cos(2 * np.pi * doy / 365.25))

    # Monsoon season indicator (June to Sept = 1, Oct-Nov = 2, Dec-Feb = 3, Mar-May = 4)
    month = cycle.month
    season_id = 1 if 6 <= month <= 9 else (2 if 10 <= month <= 11 else (3 if month in [12, 1, 2] else 4))

    # 4. Inter-model spread (standard deviation across models)
    model_arrays = list(raw_forecasts.values())
    if len(model_arrays) > 1:
        stacked_fcsts = np.array(model_arrays, dtype=np.float32)
        inter_model_spread = np.std(stacked_fcsts, axis=0)  # (n_lat, n_lon)
        ensemble_mean = np.mean(stacked_fcsts, axis=0)
    else:
        inter_model_spread = np.zeros((n_lat, n_lon), dtype=np.float32)
        ensemble_mean = model_arrays[0] if model_arrays else np.zeros((n_lat, n_lon), dtype=np.float32)

    # 5. Weather regime classification
    mean_val = float(np.mean(ensemble_mean))
    regime_clf = get_regime_classifier()
    # Approximate rain/tmax/ws from available variable context
    r_mean = mean_val if variable == "rain24_mm" else 15.0
    t_mean = mean_val if "t2m" in variable else 32.0
    w_mean = mean_val if "ws" in variable else 8.0
    regime_id, regime_name = regime_clf.predict_regime(r_mean, t_mean, w_mean)

    # Flatten into feature DataFrame
    df = pd.DataFrame({
        "lat": lat_grid.flatten(),
        "lon": lon_grid.flatten(),
        "elevation": elevation.flatten(),
        "subregion_id": subregion_id_grid.flatten(),
        "lead_hours": lead,
        "sin_doy": sin_doy,
        "cos_doy": cos_doy,
        "season_id": season_id,
        "regime_id": regime_id,
        "inter_model_spread": inter_model_spread.flatten(),
        "ensemble_mean": ensemble_mean.flatten(),
    })

    return df
