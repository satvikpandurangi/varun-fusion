"""
Sub-regional spatial partitioning and point-in-polygon masks for pilot domain.
"""
from typing import Dict, List
import numpy as np
from app.core.config import get_config


def point_in_poly(lon_pts: np.ndarray, lat_pts: np.ndarray, polygon: List[List[float]]) -> np.ndarray:
    """
    Vectorized ray-casting algorithm to test whether (lon, lat) points lie inside a polygon.
    polygon: list of [lon, lat] coordinates.
    """
    n_pts = lon_pts.shape
    x = lon_pts.flatten()
    y = lat_pts.flatten()
    inside = np.zeros(len(x), dtype=bool)

    n_vertices = len(polygon)
    p1x, p1y = polygon[0]
    for i in range(1, n_vertices + 1):
        p2x, p2y = polygon[i % n_vertices]
        # Check if horizontal ray from (x, y) crosses segment (p1, p2)
        cond1 = (y > min(p1y, p2y)) & (y <= max(p1y, p2y))
        cond2 = (x <= max(p1x, p2x))
        cross_x = (y - p1y) * (p2x - p1x) / (p2y - p1y + 1e-12) + p1x
        cond3 = (p1y != p2y) & (p1x == p2x or x <= cross_x)
        
        mask = cond1 & cond2 & cond3
        inside ^= mask
        p1x, p1y = p2x, p2y

    return inside.reshape(n_pts)


def get_subregion_masks() -> Dict[str, np.ndarray]:
    """
    Return dictionary mapping region name -> boolean mask of shape (n_lat, n_lon).
    Includes 'all', 'coastal', 'inland', 'hills'.
    """
    cfg = get_config()
    lats = np.array(cfg.domain.lats)
    lons = np.array(cfg.domain.lons)
    lon_grid, lat_grid = np.meshgrid(lons, lats)  # (n_lat, n_lon)

    masks = {
        "all": np.ones((len(lats), len(lons)), dtype=bool)
    }

    for region_id, subreg in cfg.domain.subregions.items():
        poly = subreg.polygon
        mask = point_in_poly(lon_grid, lat_grid, poly)
        masks[region_id] = mask

    return masks
