"""
Adapter factory to instantiate and manage forecast and truth sources.
"""
from typing import Dict
from app.adapters.base import ForecastSource
from app.adapters.cached_sample import SampleCachedAdapter
from app.adapters.ecmwf_opendata import ECMWFOpenDataAdapter
from app.adapters.noaa_gfs import NOAAGFSAdapter
from app.adapters.open_meteo import OpenMeteoAdapter
from app.adapters.truth import TruthAdapter
from app.core.config import get_config

_ADAPTER_REGISTRY: Dict[str, ForecastSource] = {}


def get_adapter(source_id: str) -> ForecastSource:
    """Return configured adapter instance for a source_id."""
    if source_id in _ADAPTER_REGISTRY:
        return _ADAPTER_REGISTRY[source_id]

    cfg = get_config()

    if source_id == "truth":
        adapter = TruthAdapter(source_id="truth", provenance="CACHED")
    elif source_id == "ecmwf_ifs":
        adapter = ECMWFOpenDataAdapter(source_id="ecmwf_ifs", kind="nwp", provenance="CACHED")
    elif source_id == "ecmwf_aifs":
        adapter = ECMWFOpenDataAdapter(source_id="ecmwf_aifs", kind="ai", provenance="CACHED")
    elif source_id == "noaa_gfs":
        adapter = NOAAGFSAdapter(source_id="noaa_gfs", provenance="CACHED")
    elif source_id == "ncmrwf":
        adapter = SampleCachedAdapter(source_id="ncmrwf", kind="nwp", provenance="SYNTHETIC")
    elif source_id.startswith("open_meteo_"):
        real_id = source_id.replace("open_meteo_", "")
        adapter = OpenMeteoAdapter(source_id=real_id, provenance="LIVE")
    else:
        # Generic fallback to cached sample adapter
        kind = "ai" if "ai" in source_id.lower() else "nwp"
        adapter = SampleCachedAdapter(source_id=source_id, kind=kind, provenance="CACHED")

    _ADAPTER_REGISTRY[source_id] = adapter
    return adapter
