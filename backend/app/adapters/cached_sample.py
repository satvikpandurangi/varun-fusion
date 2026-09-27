"""
Sample / Cached Forecast Adapter for VARUN-FUSION.
Provides instant, deterministic, offline execution with authentic meteorological dynamics.
"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Literal, Tuple
import numpy as np
import xarray as xr
from app.adapters.base import BaseForecastAdapter
from app.core.config import get_config
from app.core.logging import logger


class SampleCachedAdapter(BaseForecastAdapter):
    """
    Adapter that reads pre-generated netCDF files from data/samples/
    or generates realistic monsoon synoptic fields on-the-fly.
    """

    def __init__(
        self,
        source_id: str = "ecmwf_ifs",
        kind: Literal["nwp", "ai", "ensemble"] = "nwp",
        provenance: Literal["LIVE", "CACHED", "SYNTHETIC"] = "CACHED",
    ):
        super().__init__(source_id=source_id, kind=kind, provenance=provenance, native_resolution=0.25)
        self.sample_dir = Path("data/samples") / source_id
        self.sample_dir.mkdir(parents=True, exist_ok=True)

    def available_cycles(self, start: datetime, end: datetime) -> List[datetime]:
        """Return daily 00:00 UTC cycles within [start, end]."""
        cycles = []
        curr = datetime(start.year, start.month, start.day, 0, 0, 0)
        end_date = datetime(end.year, end.month, end.day, 0, 0, 0)
        while curr <= end_date:
            cycles.append(curr)
            curr += timedelta(days=1)
        return cycles

    def _load_raw(
        self,
        cycle: datetime,
        leads: List[int],
        variables: List[str],
        bbox: Tuple[float, float, float, float],
    ) -> xr.Dataset:
        filename = f"{cycle.strftime('%Y%m%d')}.nc"
        file_path = self.sample_dir / filename

        if file_path.exists():
            try:
                ds = xr.open_dataset(file_path)
                return ds
            except Exception as e:
                logger.warning(f"Error opening existing sample {file_path}: {e}. Regenerating...")

        ds = self.generate_sample_dataset(cycle, leads, bbox)
        try:
            ds.to_netcdf(file_path)
        except Exception as e:
            logger.warning(f"Could not persist sample dataset to {file_path}: {e}")
        return ds

    def generate_sample_dataset(
        self,
        cycle: datetime,
        leads: List[int],
        bbox: Tuple[float, float, float, float],
    ) -> xr.Dataset:
        """
        Generate physically grounded synoptic fields (Monsoon Depression + Orography).
        Different models have distinct, realistic physical bias and skill profiles.
        """
        lats = np.array(self.cfg.domain.lats, dtype=np.float32)
        lons = np.array(self.cfg.domain.lons, dtype=np.float32)
        lon_grid, lat_grid = np.meshgrid(lons, lats)  # (n_lat, n_lon)

        n_leads = len(leads)
        n_lat = len(lats)
        n_lon = len(lons)

        rain_arr = np.zeros((n_leads, n_lat, n_lon), dtype=np.float32)
        tmax_arr = np.zeros((n_leads, n_lat, n_lon), dtype=np.float32)
        tmean_arr = np.zeros((n_leads, n_lat, n_lon), dtype=np.float32)
        ws_arr = np.zeros((n_leads, n_lat, n_lon), dtype=np.float32)
        valid_times = []

        day_of_year = cycle.timetuple().tm_yday
        base_seed = int((day_of_year * 1000 + hash(self.id) % 1000) % 2**31)
        rng = np.random.RandomState(base_seed)

        # Geographic terrain features
        # Eastern Ghats ridge around (19.0N, 83.5E) to (21.0N, 85.5E)
        hills_mask = np.exp(-((lat_grid - 19.5)**2 / 3.0 + (lon_grid - 83.8)**2 / 2.5))
        # Bay of Bengal maritime zone: lon >= 86.5 and lat <= 21.0
        marine_mask = 1.0 / (1.0 + np.exp(-(lon_grid - 86.5) * 1.5)) * (lat_grid <= 21.5)
        # Coastal boundary zone
        coast_dist = np.clip((lon_grid - 84.5) / 3.5, 0.0, 1.2)

        # Synoptic Monsoon Depression simulation
        # Peak depression lifecycle between Aug 03 and Aug 07 (DOY 215 - 219)
        # Secondary disturbance between Aug 10 and Aug 13 (DOY 222 - 225)
        for i, lead in enumerate(leads):
            vt = cycle + timedelta(hours=lead)
            valid_times.append(np.datetime64(vt))
            lead_days = lead / 24.0
            eff_doy = vt.timetuple().tm_yday

            # Depression vortex trajectory
            # Center moves from Bay (20.0N, 88.5E) inland towards (21.5N, 83.5E)
            dep_intensity = 0.0
            dep_lat, dep_lon = 20.0, 88.0

            if 214 <= eff_doy <= 220:
                frac = (eff_doy - 214) / 6.0
                dep_intensity = np.sin(np.pi * frac) ** 1.5
                dep_lat = 19.5 + frac * 2.2
                dep_lon = 88.5 - frac * 5.0
            elif 221 <= eff_doy <= 226:
                frac = (eff_doy - 221) / 5.0
                dep_intensity = 0.75 * np.sin(np.pi * frac)
                dep_lat = 18.8 + frac * 2.0
                dep_lon = 87.5 - frac * 4.0

            dist_to_vortex = np.sqrt((lat_grid - dep_lat)**2 + (lon_grid - dep_lon)**2)
            vortex_rain = dep_intensity * 120.0 * np.exp(-dist_to_vortex**2 / 2.8)
            vortex_wind = dep_intensity * 18.0 * np.exp(-dist_to_vortex / 2.2)

            # Background monsoon precipitation + orographic lifting
            bg_rain = 15.0 + 35.0 * hills_mask + 20.0 * coast_dist + rng.normal(0, 3.0, size=(n_lat, n_lon))
            tot_rain = np.maximum(0.0, bg_rain + vortex_rain)

            # Background wind (southwesterly monsoon flow)
            bg_wind = 7.0 + 8.0 * marine_mask + 4.0 * coast_dist + rng.normal(0, 0.8, size=(n_lat, n_lon))
            tot_wind = np.maximum(1.0, bg_wind + vortex_wind)

            # Temperature fields (cooling during depression rainfall, warmer inland)
            rain_cooling = np.clip(tot_rain / 25.0, 0.0, 6.0)
            tmax = 35.5 - rain_cooling - 2.5 * hills_mask + rng.normal(0, 0.5, size=(n_lat, n_lon))
            tmean = tmax - (5.0 - np.clip(tot_rain / 40.0, 0.0, 2.0))

            # Apply model-specific physical biases and characteristics
            if self.id == "ecmwf_ifs":
                # High skill, smooth convective peaks slightly
                model_rain = tot_rain * 0.96 + rng.normal(0, 2.5, size=(n_lat, n_lon))
                model_wind = tot_wind * 0.98 + rng.normal(0, 0.4, size=(n_lat, n_lon))
                model_tmax = tmax + 0.2
            elif self.id == "ecmwf_aifs":
                # AI model: very sharp winds, conservative on extreme rainfall tails
                model_rain = np.where(tot_rain > 60.0, tot_rain * 0.90, tot_rain * 1.02) + rng.normal(0, 2.0, size=(n_lat, n_lon))
                model_wind = tot_wind * 1.02 + rng.normal(0, 0.3, size=(n_lat, n_lon))
                model_tmax = tmax - 0.1
            elif self.id == "noaa_gfs":
                # Slight positive rainfall bias over Ghats and coastal strip
                model_rain = tot_rain * 1.08 + hills_mask * 8.0 + rng.normal(0, 4.0, size=(n_lat, n_lon))
                model_wind = tot_wind * 1.05 + rng.normal(0, 0.6, size=(n_lat, n_lon))
                model_tmax = tmax + 0.6
            elif self.id == "ncmrwf":
                # Strong orographic resolution over Odisha hills, slower track
                model_rain = tot_rain * 1.04 + hills_mask * 12.0 + rng.normal(0, 3.5, size=(n_lat, n_lon))
                model_wind = tot_wind * 0.95 + rng.normal(0, 0.5, size=(n_lat, n_lon))
                model_tmax = tmax - 0.4
            else:  # Truth
                model_rain = tot_rain
                model_wind = tot_wind
                model_tmax = tmax

            # Degradation with lead time (physical predictability loss)
            lead_noise_scale = (lead / 120.0) * 0.20
            if self.id != "truth":
                noise = rng.normal(0, lead_noise_scale * np.maximum(5.0, model_rain), size=(n_lat, n_lon))
                model_rain = np.maximum(0.0, model_rain + noise)

            rain_arr[i] = np.maximum(0.0, np.round(model_rain, 1))
            tmax_arr[i] = np.round(model_tmax, 1)
            tmean_arr[i] = np.round(tmean, 1)
            ws_arr[i] = np.maximum(0.0, np.round(model_wind, 1))

        ds = xr.Dataset(
            data_vars={
                "rain24_mm": (("lead", "lat", "lon"), rain_arr),
                "t2m_max_c": (("lead", "lat", "lon"), tmax_arr),
                "t2m_mean_c": (("lead", "lat", "lon"), tmean_arr),
                "ws10_ms": (("lead", "lat", "lon"), ws_arr),
            },
            coords={
                "valid_time": ("lead", valid_times),
                "lead": leads,
                "lat": lats,
                "lon": lons,
            }
        )
        return ds
