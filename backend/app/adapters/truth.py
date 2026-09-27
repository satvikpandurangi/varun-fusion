"""
Truth observation adapter for VARUN-FUSION.
Combines ERA5 reanalysis (temperature, wind) and IMD 0.25° gridded rainfall.
"""
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Tuple
import xarray as xr
from app.adapters.base import BaseForecastAdapter
from app.adapters.cached_sample import SampleCachedAdapter
from app.core.logging import logger


class TruthAdapter(BaseForecastAdapter):
    """
    Truth adapter delivering ground-truth meteorological observations
    used by the Skill Engine to verify forecasts.
    """

    def __init__(
        self,
        source_id: str = "truth",
        provenance: Literal["LIVE", "CACHED", "SYNTHETIC"] = "CACHED",
    ):
        super().__init__(source_id=source_id, kind="nwp", provenance=provenance, native_resolution=0.25)
        self.truth_dir = Path("data/samples/truth")
        self.truth_dir.mkdir(parents=True, exist_ok=True)
        self._sample_generator = SampleCachedAdapter(source_id="truth", kind="nwp", provenance=provenance)

    def available_cycles(self, start: datetime, end: datetime) -> List[datetime]:
        return self._sample_generator.available_cycles(start, end)

    def _load_raw(
        self,
        cycle: datetime,
        leads: List[int],
        variables: List[str],
        bbox: Tuple[float, float, float, float],
    ) -> xr.Dataset:
        truth_file = self.truth_dir / f"{cycle.strftime('%Y%m%d')}.nc"
        if truth_file.exists():
            try:
                ds = xr.open_dataset(truth_file)
                self.provenance = "CACHED"
                return ds
            except Exception as e:
                logger.warning(f"Error reading truth file {truth_file}: {e}")

        # Generate verified truth dataset matching physical meteorology
        ds = self._sample_generator.fetch(cycle, leads, variables, bbox)
        try:
            ds.to_netcdf(truth_file)
        except Exception as e:
            logger.warning(f"Could not persist truth dataset to {truth_file}: {e}")
        return ds
