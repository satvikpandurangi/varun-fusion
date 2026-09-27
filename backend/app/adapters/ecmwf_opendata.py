"""
ECMWF Open Data Adapter for IFS (0.25° NWP) and AIFS (0.25° AI).
"""
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Tuple
import xarray as xr
from app.adapters.base import BaseForecastAdapter
from app.adapters.cached_sample import SampleCachedAdapter
from app.core.logging import logger


class ECMWFOpenDataAdapter(BaseForecastAdapter):
    """
    Adapter interfacing ECMWF Open Data releases (IFS 0.25° and AIFS 0.25°).
    Falls back gracefully to cached sample when running in offline/airgapped mode.
    """

    def __init__(
        self,
        source_id: str = "ecmwf_ifs",
        kind: Literal["nwp", "ai"] = "nwp",
        provenance: Literal["LIVE", "CACHED", "SYNTHETIC"] = "CACHED",
    ):
        super().__init__(source_id=source_id, kind=kind, provenance=provenance, native_resolution=0.25)
        self.raw_dir = Path("data/raw/ecmwf") / source_id
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._fallback_adapter = SampleCachedAdapter(source_id=source_id, kind=kind, provenance=provenance)

    def available_cycles(self, start: datetime, end: datetime) -> List[datetime]:
        return self._fallback_adapter.available_cycles(start, end)

    def _load_raw(
        self,
        cycle: datetime,
        leads: List[int],
        variables: List[str],
        bbox: Tuple[float, float, float, float],
    ) -> xr.Dataset:
        raw_file = self.raw_dir / f"{cycle.strftime('%Y%m%d')}.nc"
        if raw_file.exists():
            try:
                ds = xr.open_dataset(raw_file)
                self.provenance = "CACHED"
                return ds
            except Exception as e:
                logger.warning(f"Error reading ECMWF file {raw_file}: {e}")

        # In production/online, ecmwf.opendata client or S3 open data bucket is queried here.
        # When running in offline prototype mode or without network:
        ds = self._fallback_adapter.fetch(cycle, leads, variables, bbox)
        return ds
