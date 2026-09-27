"""
Unit tests for VARUN-FUSION context feature engineering and weather regime classification.
"""
from datetime import datetime
import numpy as np
import pytest
from app.context.features import (
    compute_elevation_map,
    extract_context_features,
    get_regime_classifier,
)
from app.core.config import get_config


def test_elevation_map_properties():
    cfg = get_config()
    lats = np.array(cfg.domain.lats)
    lons = np.array(cfg.domain.lons)

    elev = compute_elevation_map(lats, lons)
    assert elev.shape == (len(lats), len(lons))
    # Sea-level / plains lowest elevation >= 20m
    assert elev.min() >= 20.0
    # Highlands / Eastern Ghats ridge peak between 500m and 1200m
    assert elev.max() > 600.0
    assert elev.max() <= 1200.0


def test_weather_regime_classifier():
    clf = get_regime_classifier()
    assert clf.is_fitted

    # High rainfall depression conditions -> should trigger Active Depression (Regime 0)
    cid_dep, label_dep = clf.predict_regime(domain_rain_mean=80.0, domain_tmax_mean=28.0, domain_ws_mean=16.0)
    assert cid_dep == 0
    assert "Active Depression" in label_dep

    # Dry heat conditions -> Break monsoon / heat (Regime 2)
    cid_dry, label_dry = clf.predict_regime(domain_rain_mean=2.0, domain_tmax_mean=36.0, domain_ws_mean=5.0)
    assert cid_dry == 2
    assert "Heat" in label_dry or "Weak" in label_dry


def test_extract_context_features():
    cycle = datetime(2025, 8, 5, 0, 0, 0)
    lead = 24
    grid_shape = (29, 37)
    n_points = 29 * 37

    raw_fcsts = {
        "m1": np.full(grid_shape, 20.0, dtype=np.float32),
        "m2": np.full(grid_shape, 25.0, dtype=np.float32),
    }

    df_ctx = extract_context_features(cycle, lead, raw_fcsts, "rain24_mm")

    assert len(df_ctx) == n_points
    assert "lat" in df_ctx.columns
    assert "lon" in df_ctx.columns
    assert "elevation" in df_ctx.columns
    assert "subregion_id" in df_ctx.columns
    assert "inter_model_spread" in df_ctx.columns

    # Cyclical encoding identity sin^2 + cos^2 = 1
    sin_val = df_ctx["sin_doy"].iloc[0]
    cos_val = df_ctx["cos_doy"].iloc[0]
    assert pytest.approx(sin_val**2 + cos_val**2, 1e-4) == 1.0

    # Spread std([20, 25]) = 2.5
    assert pytest.approx(df_ctx["inter_model_spread"].mean(), 0.01) == 2.5
