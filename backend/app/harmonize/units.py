"""
Meteorological unit standardization and physical constraint enforcement.
"""
import numpy as np
import xarray as xr
from app.core.logging import logger


def standardize_units(ds: xr.Dataset) -> xr.Dataset:
    """
    Standardize raw meteorological fields:
    - Temperature: Kelvin -> Celsius (if mean > 100)
    - Precipitation: meters -> millimeters (if max < 1.0)
    - Wind: derive speed from (u10, v10) if ws10 is absent
    - Enforce physical bounds (rain >= 0, wind >= 0)
    """
    ds = ds.copy()

    # Temperature standardization
    for t_var in ["t2m_max_c", "t2m_mean_c", "t2m", "temperature_2m"]:
        if t_var in ds.data_vars:
            arr = ds[t_var].values
            # If values appear to be in Kelvin (e.g. > 150)
            if np.nanmean(arr) > 100.0:
                ds[t_var] = ds[t_var] - 273.15
                logger.debug(f"Converted {t_var} from Kelvin to Celsius")

    # Rename canonical temperature names if needed
    if "temperature_2m" in ds.data_vars and "t2m_mean_c" not in ds.data_vars:
        ds = ds.rename({"temperature_2m": "t2m_mean_c"})
    if "t2m" in ds.data_vars and "t2m_mean_c" not in ds.data_vars:
        ds = ds.rename({"t2m": "t2m_mean_c"})
    if "t2m_max_c" not in ds.data_vars and "t2m_mean_c" in ds.data_vars:
        # If t2m_max not explicitly given, approximate from diurnal cycle
        ds["t2m_max_c"] = ds["t2m_mean_c"] + 3.0

    # Precipitation standardization
    for r_var in ["rain24_mm", "tp", "precipitation", "total_precipitation"]:
        if r_var in ds.data_vars:
            arr = ds[r_var].values
            # If values appear to be in meters (e.g. max < 1.5)
            if np.nanmax(arr) < 1.5 and np.nanmax(arr) > 0:
                ds[r_var] = ds[r_var] * 1000.0
                logger.debug(f"Converted {r_var} from meters to millimeters")
            # Enforce non-negativity
            ds[r_var] = np.maximum(0.0, ds[r_var])

    if "tp" in ds.data_vars and "rain24_mm" not in ds.data_vars:
        ds = ds.rename({"tp": "rain24_mm"})
    elif "precipitation" in ds.data_vars and "rain24_mm" not in ds.data_vars:
        ds = ds.rename({"precipitation": "rain24_mm"})

    # Wind speed derivation
    if "ws10_ms" not in ds.data_vars:
        if "u10" in ds.data_vars and "v10" in ds.data_vars:
            ds["ws10_ms"] = np.sqrt(ds["u10"]**2 + ds["v10"]**2)
            logger.debug("Computed ws10_ms from u10 and v10 components")
        elif "wind_speed_10m" in ds.data_vars:
            ds = ds.rename({"wind_speed_10m": "ws10_ms"})

    if "ws10_ms" in ds.data_vars:
        ds["ws10_ms"] = np.maximum(0.0, ds["ws10_ms"])

    return ds
