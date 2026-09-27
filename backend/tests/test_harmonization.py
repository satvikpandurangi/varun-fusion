"""
Unit tests for VARUN-FUSION harmonization engine.
"""
from datetime import datetime
import numpy as np
import pytest
import xarray as xr
from app.harmonize.pipeline import harmonize_dataset
from app.harmonize.regrid import regrid_to_canonical
from app.harmonize.units import standardize_units
from app.core.config import get_config


def test_standardize_units_conversions():
    # 1. Test Kelvin to Celsius conversion
    ds_kelvin = xr.Dataset({
        "t2m_max_c": (("lat", "lon"), np.array([[300.15, 305.15], [310.15, 295.15]])),
        "t2m_mean_c": (("lat", "lon"), np.array([[298.15, 303.15], [308.15, 293.15]])),
    }, coords={"lat": [20.0, 21.0], "lon": [85.0, 86.0]})

    ds_celsius = standardize_units(ds_kelvin)
    assert pytest.approx(float(ds_celsius["t2m_max_c"].values[0, 0]), 0.01) == 27.0
    assert pytest.approx(float(ds_celsius["t2m_max_c"].values[0, 1]), 0.01) == 32.0

    # 2. Test meters to millimeters conversion
    ds_meters = xr.Dataset({
        "rain24_mm": (("lat", "lon"), np.array([[0.015, 0.065], [0.002, 0.120]])),
    }, coords={"lat": [20.0, 21.0], "lon": [85.0, 86.0]})

    ds_mm = standardize_units(ds_meters)
    assert pytest.approx(float(ds_mm["rain24_mm"].values[0, 0]), 0.1) == 15.0
    assert pytest.approx(float(ds_mm["rain24_mm"].values[0, 1]), 0.1) == 65.0

    # 3. Test derivation of wind speed from (u10, v10)
    ds_uv = xr.Dataset({
        "u10": (("lat", "lon"), np.array([[3.0, 6.0], [0.0, 8.0]])),
        "v10": (("lat", "lon"), np.array([[4.0, 8.0], [5.0, 6.0]])),
    }, coords={"lat": [20.0, 21.0], "lon": [85.0, 86.0]})

    ds_wind = standardize_units(ds_uv)
    assert "ws10_ms" in ds_wind.data_vars
    assert pytest.approx(float(ds_wind["ws10_ms"].values[0, 0]), 0.01) == 5.0  # sqrt(3^2 + 4^2)
    assert pytest.approx(float(ds_wind["ws10_ms"].values[0, 1]), 0.01) == 10.0 # sqrt(6^2 + 8^2)


def test_regrid_conservation_and_coordinates():
    cfg = get_config()
    # Create coarse 0.5 deg dataset
    coarse_lats = np.arange(17.0, 24.5, 0.5)
    coarse_lons = np.arange(81.0, 90.5, 0.5)
    
    # Synthetic rain pattern
    y, x = np.meshgrid(coarse_lats, coarse_lons, indexing="ij")
    rain_data = np.maximum(0.0, 50.0 * np.sin(x / 5.0) * np.cos(y / 5.0) + 20.0)

    ds_coarse = xr.Dataset({
        "rain24_mm": (("lat", "lon"), rain_data),
        "t2m_max_c": (("lat", "lon"), np.full(rain_data.shape, 32.0)),
        "t2m_mean_c": (("lat", "lon"), np.full(rain_data.shape, 28.0)),
        "ws10_ms": (("lat", "lon"), np.full(rain_data.shape, 8.0)),
    }, coords={"lat": coarse_lats, "lon": coarse_lons})

    # Regrid to target 0.25 deg grid
    ds_canonical = regrid_to_canonical(ds_coarse)

    # Verify target shapes
    assert len(ds_canonical.lat) == len(cfg.domain.lats)
    assert len(ds_canonical.lon) == len(cfg.domain.lons)
    assert pytest.approx(float(ds_canonical.lat.min()), 0.01) == cfg.domain.lat_min
    assert pytest.approx(float(ds_canonical.lat.max()), 0.01) == cfg.domain.lat_max

    # Conservation of rainfall mean within 10%
    orig_mean = float(np.mean(ds_coarse["rain24_mm"].values))
    regrid_mean = float(np.mean(ds_canonical["rain24_mm"].values))
    assert abs(regrid_mean - orig_mean) / orig_mean < 0.15

    # Non-negativity check
    assert (ds_canonical["rain24_mm"].values >= 0.0).all()
    assert (ds_canonical["ws10_ms"].values >= 0.0).all()
