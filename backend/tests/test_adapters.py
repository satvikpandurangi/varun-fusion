"""
Unit tests for VARUN-FUSION forecast adapters.
"""
from datetime import datetime
import pytest
import numpy as np
import xarray as xr
from app.adapters.base import ForecastSource, DISCLAIMER_TEXT
from app.adapters.factory import get_adapter
from app.core.config import get_config


def test_config_loader():
    cfg = get_config()
    assert cfg.system["name"] == "VARUN-FUSION"
    assert len(cfg.lead_times_hours) == 5
    assert "rain24_mm" in cfg.variables
    assert cfg.domain.lat_min == 17.0
    assert cfg.domain.lat_max == 24.0
    assert cfg.domain.lon_min == 81.0
    assert cfg.domain.lon_max == 90.0
    assert len(cfg.domain.lats) == 29
    assert len(cfg.domain.lons) == 37


@pytest.mark.parametrize("source_id,expected_kind", [
    ("ecmwf_ifs", "nwp"),
    ("ecmwf_aifs", "ai"),
    ("noaa_gfs", "nwp"),
    ("ncmrwf", "nwp"),
    ("truth", "nwp"),
])
def test_adapter_protocol_and_fetch(source_id, expected_kind):
    adapter = get_adapter(source_id)
    assert isinstance(adapter, ForecastSource)
    assert adapter.id == source_id
    assert adapter.kind == expected_kind

    cycle = datetime(2025, 8, 3, 0, 0, 0)
    ds = adapter.fetch(cycle)

    # Check dimensions
    assert set(ds.dims) >= {"lead", "lat", "lon"}
    assert len(ds.lead) == 5
    assert len(ds.lat) == 29
    assert len(ds.lon) == 37

    # Check variables
    for var in ["rain24_mm", "t2m_max_c", "t2m_mean_c", "ws10_ms"]:
        assert var in ds.data_vars
        arr = ds[var].values
        assert not np.isnan(arr).any(), f"NaN found in {source_id} {var}"

    # Physical validity checks
    assert (ds["rain24_mm"].values >= 0.0).all()
    assert (ds["ws10_ms"].values >= 0.0).all()
    assert (ds["t2m_max_c"].values >= 15.0).all()
    assert (ds["t2m_max_c"].values <= 50.0).all()
    assert (ds["t2m_max_c"].values >= ds["t2m_mean_c"].values - 0.1).all()

    # Check required metadata attributes
    assert ds.attrs["source_id"] == source_id
    assert ds.attrs["provenance"] in ["LIVE", "CACHED", "SYNTHETIC"]
    assert ds.attrs["disclaimer"] == DISCLAIMER_TEXT
    assert ds.attrs["native_resolution"] == 0.25
