"""
Extreme-aware risk layer and minority extreme signal retention engine for VARUN-FUSION.
Ensures life-threatening weather events are never smoothed away by multi-model averaging.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from app.core.config import get_config
from app.core.logging import logger
from app.skill.engine import RollingSkillEngine


class ExtremeRiskEngine:
    """
    Computes extreme weather risk layers and identifies high-risk minority extreme signals.
    """

    def __init__(self):
        self.cfg = get_config()
        self.skill_engine = RollingSkillEngine()

    def compute_extreme_risk_layer(
        self,
        cycle: datetime,
        lead: int,
        raw_forecasts: Dict[str, np.ndarray],
        blended_forecast: np.ndarray,
        variable: str = "rain24_mm",
        threshold_name: str = "heavy",
    ) -> Dict[str, Any]:
        """
        Compute probabilistic extreme risk layer and minority extreme alerts.
        """
        models = list(raw_forecasts.keys())
        first_field = raw_forecasts[models[0]]
        grid_shape = first_field.shape
        n_lat, n_lon = grid_shape
        lats = np.array(self.cfg.domain.lats)
        lons = np.array(self.cfg.domain.lons)

        # 1. Resolve meteorological threshold
        if variable == "rain24_mm":
            th_val = self.cfg.thresholds["rain"].get(threshold_name, 64.5)
        elif "t2m" in variable:
            th_val = self.cfg.thresholds["t2m_max"].get("heatwave", 40.0)
        elif "ws" in variable:
            th_val = self.cfg.thresholds["ws10"].get("squall", 15.0)
        else:
            th_val = 50.0

        # 2. Derive event weights from rolling event skill (CSI / FSS)
        # Models with higher recent verification of extremes receive higher weight in risk score
        event_weights = {}
        for mid in models:
            # Base event weight from inverse error or default
            rmse_grid = self.skill_engine.compute_gridcell_rmse(cycle, mid, variable, lead)
            event_weights[mid] = 1.0 / np.maximum(0.1, rmse_grid)

        # Normalize event weights to sum to 1
        stacked_w = np.array([event_weights[mid] for mid in models], dtype=np.float32)
        sum_w = np.sum(stacked_w, axis=0, keepdims=True)
        norm_w = stacked_w / np.where(sum_w < 1e-12, 1.0, sum_w)

        # 3. Calculate Extreme Risk Score (0.0 to 1.0)
        # Exceedance indicator per model: (m, lat, lon)
        exceedance = np.array([raw_forecasts[mid] >= th_val for mid in models], dtype=np.float32)
        risk_score = np.sum(norm_w * exceedance, axis=0) # shape (n_lat, n_lon)
        risk_score = np.clip(risk_score, 0.0, 1.0)

        # 4. Minority Extreme Signal Detection:
        # A cell where:
        # - Any model exceeds the threshold (F_m >= th_val)
        # - But the blend does NOT (F_blend < th_val)
        # Never suppress this — mark it for operational forecasters!
        blend_exceeds = (blended_forecast >= th_val)
        any_model_exceeds = np.any(exceedance > 0.5, axis=0)
        minority_signal_mask = any_model_exceeds & (~blend_exceeds)

        minority_alerts = []
        alert_coords = np.argwhere(minority_signal_mask)
        for lat_idx, lon_idx in alert_coords:
            flagged_models = []
            max_val = 0.0
            for i, mid in enumerate(models):
                val = float(raw_forecasts[mid][lat_idx, lon_idx])
                if val >= th_val:
                    flagged_models.append({"source": mid, "value": round(val, 1)})
                    if val > max_val:
                        max_val = val

            minority_alerts.append({
                "lat": float(lats[lat_idx]),
                "lon": float(lons[lon_idx]),
                "lat_idx": int(lat_idx),
                "lon_idx": int(lon_idx),
                "threshold": th_val,
                "blend_value": round(float(blended_forecast[lat_idx, lon_idx]), 1),
                "max_model_value": round(max_val, 1),
                "sources_exceeding": flagged_models,
                "message": f"Minority Extreme: {len(flagged_models)} model(s) exceed {th_val} threshold (max {max_val} vs blend {blended_forecast[lat_idx, lon_idx]:.1f})",
            })

        # Categorize risk severity
        # None < 0.20, Watch 0.20-0.45, Alert 0.45-0.70, Warning >= 0.70
        risk_category = np.full(grid_shape, "NONE", dtype=object)
        risk_category[risk_score >= 0.20] = "WATCH"
        risk_category[risk_score >= 0.45] = "ALERT"
        risk_category[risk_score >= 0.70] = "WARNING"

        return {
            "variable": variable,
            "threshold_name": threshold_name,
            "threshold_value": th_val,
            "risk_score": risk_score,
            "risk_category": risk_category,
            "minority_signal_mask": minority_signal_mask,
            "minority_alerts": minority_alerts,
            "n_alerts": len(minority_alerts),
        }
