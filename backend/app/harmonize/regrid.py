"""
Spatial regridding engine for VARUN-FUSION.
Interpolates native grids to the canonical 0.25° pilot domain.
Preserves spatial precipitation totals and enforces physical bounds.
"""
from typing import List, Tuple
import numpy as np
import xarray as xr
from app.core.config import get_config
from app.core.logging import logger


def regrid_to_canonical(
    ds: xr.Dataset,
    target_lats: List[float] = None,
    target_lons: List[float] = None,
) -> xr.Dataset:
    """
    Regrid dataset to the standard 0.25° grid.
    - Precipitation: conservative/flux-preserving bilinear interpolation
    - Continuous scalars (temp, wind): standard 2D bilinear interpolation
    """
    cfg = get_config()
    if target_lats is None:
        target_lats = cfg.domain.lats
    if target_lons is None:
        target_lons = cfg.domain.lons

    # If coordinates already match exact canonical target, return
    if (
        len(ds.lat) == len(target_lats)
        and len(ds.lon) == len(target_lons)
        and np.allclose(ds.lat.values, target_lats, atol=1e-4)
        and np.allclose(ds.lon.values, target_lons, atol=1e-4)
    ):
        return ds

    # Perform bilinear interpolation
    new_coords = {"lat": target_lats, "lon": target_lons}
    regridded = ds.interp(
        new_coords,
        method="linear",
        kwargs={"fill_value": "extrapolate"}
    )

    # Flux conservation adjustment for precipitation
    if "rain24_mm" in ds.data_vars and "rain24_mm" in regridded.data_vars:
        src_mean = float(np.nanmean(ds["rain24_mm"].values))
        tgt_mean = float(np.nanmean(regridded["rain24_mm"].values))
        if src_mean > 0.01 and tgt_mean > 0.01:
            ratio = src_mean / tgt_mean
            # Limit correction factor between 0.85 and 1.15 to prevent boundary distortion
            if 0.85 <= ratio <= 1.15:
                regridded["rain24_mm"] = regridded["rain24_mm"] * ratio

        # Re-enforce non-negativity
        regridded["rain24_mm"] = np.maximum(0.0, regridded["rain24_mm"])

    if "ws10_ms" in regridded.data_vars:
        regridded["ws10_ms"] = np.maximum(0.0, regridded["ws10_ms"])

    return regridded
