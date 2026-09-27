"""
Harmonization pipeline integrating units, regridding, temporal alignment, and ensemble statistics.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional
import numpy as np
import xarray as xr
from app.core.config import get_config
from app.core.logging import logger
from app.harmonize.regrid import regrid_to_canonical
from app.harmonize.units import standardize_units


def harmonize_dataset(
    ds: xr.Dataset,
    source_id: str,
    cycle: datetime,
    save: bool = True,
) -> xr.Dataset:
    """
    Run full harmonization pipeline on a forecast dataset:
    1. Standardize units (K->C, m->mm, wind vector->speed)
    2. Regrid to canonical pilot grid (0.25 deg)
    3. Compute ensemble statistics if member dimension exists
    4. Save to data/harmonized/{source_id}/{cycle}.nc
    """
    cfg = get_config()
    logger.debug(f"Harmonizing {source_id} for cycle {cycle.isoformat()}")

    # 1. Units & physical bounds
    ds = standardize_units(ds)

    # 2. Regrid
    ds = regrid_to_canonical(ds)

    # 3. Handle ensemble members if present
    if "member" in ds.dims:
        logger.info(f"Computing ensemble mean and spread for {source_id} with {len(ds.member)} members")
        for var in ["rain24_mm", "t2m_max_c", "t2m_mean_c", "ws10_ms"]:
            if var in ds.data_vars:
                ds[f"{var}_mean"] = ds[var].mean(dim="member")
                ds[f"{var}_spread"] = ds[var].std(dim="member")

    # 4. Canonical metadata
    ds.attrs["harmonized"] = True
    ds.attrs["harmonized_at"] = datetime.utcnow().isoformat()
    ds.attrs["grid_resolution"] = cfg.domain.grid_resolution

    if save:
        out_dir = Path("data/harmonized") / source_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{cycle.strftime('%Y%m%d')}.nc"
        try:
            ds.to_netcdf(out_path)
            logger.debug(f"Saved harmonized dataset to {out_path}")
        except Exception as e:
            logger.warning(f"Could not persist harmonized dataset to {out_path}: {e}")

    return ds
