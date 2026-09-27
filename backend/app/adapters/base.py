"""
Standard adapter protocol and base classes for forecast sources and truth.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Literal, Protocol, Tuple, runtime_checkable
import numpy as np
import xarray as xr
from app.core.config import get_config
from app.core.logging import logger

DISCLAIMER_TEXT = "Forecaster guidance — not a public warning"


@runtime_checkable
class ForecastSource(Protocol):
    """Universal protocol for all NWP, AI, ensemble, and truth forecast sources."""
    id: str
    kind: Literal["nwp", "ai", "ensemble"]
    provenance: Literal["LIVE", "CACHED", "SYNTHETIC"]

    def available_cycles(self, start: datetime, end: datetime) -> List[datetime]:
        """Return sorted list of available cycle datetimes in [start, end]."""
        ...

    def fetch(
        self,
        cycle: datetime,
        leads: List[int],
        variables: List[str],
        bbox: Tuple[float, float, float, float],
    ) -> xr.Dataset:
        """
        Fetch gridded forecast for a cycle, lead times, variables, and bounding box.
        Output dims must be (valid_time, lead, lat, lon) [or + member].
        """
        ...


class BaseForecastAdapter(ABC):
    """Abstract base adapter providing validation and standard attribute injection."""

    def __init__(
        self,
        source_id: str,
        kind: Literal["nwp", "ai", "ensemble"],
        provenance: Literal["LIVE", "CACHED", "SYNTHETIC"] = "CACHED",
        native_resolution: float = 0.25,
    ):
        self.id = source_id
        self.kind = kind
        self.provenance = provenance
        self.native_resolution = native_resolution
        self.cfg = get_config()

    @abstractmethod
    def available_cycles(self, start: datetime, end: datetime) -> List[datetime]:
        pass

    @abstractmethod
    def _load_raw(
        self,
        cycle: datetime,
        leads: List[int],
        variables: List[str],
        bbox: Tuple[float, float, float, float],
    ) -> xr.Dataset:
        pass

    def fetch(
        self,
        cycle: datetime,
        leads: List[int] = None,
        variables: List[str] = None,
        bbox: Tuple[float, float, float, float] = None,
    ) -> xr.Dataset:
        if leads is None:
            leads = self.cfg.lead_times_hours
        if variables is None:
            variables = list(self.cfg.variables.keys())
        if bbox is None:
            bbox = self.cfg.domain.bbox

        ds = self._load_raw(cycle, leads, variables, bbox)
        ds = self.validate_and_standardize(ds, cycle, leads, variables, bbox)
        return ds

    def validate_and_standardize(
        self,
        ds: xr.Dataset,
        cycle: datetime,
        leads: List[int],
        variables: List[str],
        bbox: Tuple[float, float, float, float],
    ) -> xr.Dataset:
        """Validate dimensions, variable names, coordinate boundaries, and attributes."""
        lat_min, lon_min, lat_max, lon_max = bbox

        # Ensure correct dimensions
        required_dims = {"lead", "lat", "lon"}
        missing_dims = required_dims - set(ds.dims)
        if missing_dims:
            raise ValueError(f"Dataset for {self.id} missing required dims: {missing_dims}")

        # Check variables
        for var in variables:
            if var not in ds.data_vars:
                raise ValueError(f"Dataset for {self.id} missing variable: {var}")

        # Ensure coordinates are within bbox
        lat_coords = ds.coords["lat"].values
        lon_coords = ds.coords["lon"].values
        if (lat_coords.min() < lat_min - 0.1) or (lat_coords.max() > lat_max + 0.1):
            logger.warning(f"{self.id} lat coords [{lat_coords.min()}, {lat_coords.max()}] outside bbox [{lat_min}, {lat_max}]")
        if (lon_coords.min() < lon_min - 0.1) or (lon_coords.max() > lon_max + 0.1):
            logger.warning(f"{self.id} lon coords [{lon_coords.min()}, {lon_coords.max()}] outside bbox [{lon_min}, {lon_max}]")

        # Standard metadata attributes
        ds.attrs["source_id"] = self.id
        ds.attrs["kind"] = self.kind
        ds.attrs["provenance"] = self.provenance
        ds.attrs["native_resolution"] = self.native_resolution
        ds.attrs["cycle"] = cycle.isoformat()
        ds.attrs["disclaimer"] = DISCLAIMER_TEXT
        return ds
