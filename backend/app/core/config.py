"""
Configuration loader and settings models for VARUN-FUSION.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml
from pydantic import BaseModel, Field


def find_config_path() -> Path:
    candidates = [
        Path("config.yaml"),
        Path("backend/config.yaml"),
        Path("../config.yaml"),
        Path(__file__).resolve().parent.parent.parent / "config.yaml",
        Path(__file__).resolve().parent.parent.parent.parent / "config.yaml",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c.resolve()
    raise FileNotFoundError("Could not locate config.yaml in workspace candidates")


class SubRegion(BaseModel):
    name: str
    description: str
    color: str
    polygon: List[List[float]]  # list of [lon, lat] points


class DomainConfig(BaseModel):
    name: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    grid_resolution: float
    subregions: Dict[str, SubRegion]

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """Return (lat_min, lon_min, lat_max, lon_max)"""
        return (self.lat_min, self.lon_min, self.lat_max, self.lon_max)

    @property
    def lats(self) -> List[float]:
        import numpy as np
        # Ensure inclusive endpoint with round to avoid float precision drift
        n = int(round((self.lat_max - self.lat_min) / self.grid_resolution)) + 1
        return [float(x) for x in np.round(np.linspace(self.lat_min, self.lat_max, n), 4)]

    @property
    def lons(self) -> List[float]:
        import numpy as np
        n = int(round((self.lon_max - self.lon_min) / self.grid_resolution)) + 1
        return [float(x) for x in np.round(np.linspace(self.lon_min, self.lon_max, n), 4)]


class VariableConfig(BaseModel):
    name: str
    unit: str
    display_name: str
    cmap: str
    scale_min: float
    scale_max: float
    aggregation: str


class SourceConfig(BaseModel):
    id: str
    name: str
    kind: str  # nwp, ai, ensemble
    color: str
    license: str
    native_resolution: float
    enabled: bool = True


class AppConfig(BaseModel):
    system: Dict[str, Any]
    domain: DomainConfig
    variables: Dict[str, VariableConfig]
    lead_times_hours: List[int]
    thresholds: Dict[str, Any]
    sources: Dict[str, SourceConfig]
    truth: Dict[str, str]
    skill: Dict[str, Any]
    blending: Dict[str, Any]
    storage: Dict[str, str]


_CONFIG: Optional[AppConfig] = None


def get_config() -> AppConfig:
    global _CONFIG
    if _CONFIG is None:
        cfg_path = find_config_path()
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        _CONFIG = AppConfig(**raw)
    return _CONFIG


def get_storage_path(key: str, default: str) -> Path:
    cfg = get_config()
    raw = cfg.storage.get(key, default)
    p = Path(raw)
    p.mkdir(parents=True, exist_ok=True)
    return p
