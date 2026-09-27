"""
Forecaster Confidence Engine for VARUN-FUSION.
Computes cell-level confidence scores (0-1) and categorical labels (HIGH, MEDIUM, LOW)
based on inter-model spread, weight entropy, historical verification skill, and data completeness.
"""
from typing import Dict, List, Optional, Tuple
import numpy as np
from app.core.config import get_config
from app.core.logging import logger


class ForecasterConfidenceEngine:
    """
    Evaluates forecast epistemic and aleatoric confidence.
    Produces confidence indices, categorical flags, and out-of-distribution alerts.
    """

    def __init__(self):
        self.cfg = get_config()
        self.w_cfg = self.cfg.blending["confidence"]["weights"]
        self.th_cfg = self.cfg.blending["confidence"]["thresholds"]

    def compute_confidence(
        self,
        raw_forecasts: Dict[str, np.ndarray],
        weights: Dict[str, np.ndarray],
        variable: str,
        recent_rmse: Optional[np.ndarray] = None,
    ) -> Dict[str, np.ndarray]:
        """
        Compute multi-factor confidence field (0.0 to 1.0) and categorical flags.
        """
        models = list(raw_forecasts.keys())
        first_field = raw_forecasts[models[0]]
        grid_shape = first_field.shape
        n_lat, n_lon = grid_shape
        m = len(models)
        total_configured_models = len(self.cfg.sources)

        # 1. Component: Inter-model spread score S_spread in [0, 1]
        # Low spread across models = high confidence
        if m > 1:
            stacked_fcst = np.array([raw_forecasts[mid] for mid in models], dtype=np.float32)
            spread = np.std(stacked_fcst, axis=0) # (lat, lon)
        else:
            spread = np.zeros(grid_shape, dtype=np.float32)

        # Normalization scale by variable
        if variable == "rain24_mm":
            sigma_norm = 15.0
        elif "t2m" in variable:
            sigma_norm = 2.0
        elif "ws" in variable:
            sigma_norm = 3.5
        else:
            sigma_norm = 10.0

        s_spread = np.exp(-spread / sigma_norm)

        # 2. Component: Weight entropy score S_entropy in [0, 1]
        # High certainty in model selection = lower entropy
        if m > 1:
            stacked_w = np.array([weights[mid] for mid in models], dtype=np.float32) # (m, lat, lon)
            eps = 1e-12
            entropy = -np.sum(stacked_w * np.log(stacked_w + eps), axis=0) / np.log(float(m))
            s_entropy = 1.0 - 0.4 * np.clip(entropy, 0.0, 1.0)
        else:
            s_entropy = np.ones(grid_shape, dtype=np.float32)

        # 3. Component: Recent verification skill score S_skill in [0, 1]
        if recent_rmse is not None:
            s_skill = np.exp(-recent_rmse / (sigma_norm * 1.2))
        else:
            s_skill = np.full(grid_shape, 0.75, dtype=np.float32)

        # 4. Component: Data completeness score S_comp in [0, 1]
        s_comp = min(1.0, float(m / max(1, total_configured_models)))
        s_comp_arr = np.full(grid_shape, s_comp, dtype=np.float32)

        # 5. Composite Confidence Index
        w1 = self.w_cfg.get("spread", 0.35)
        w2 = self.w_cfg.get("entropy", 0.25)
        w3 = self.w_cfg.get("recent_skill", 0.25)
        w4 = self.w_cfg.get("completeness", 0.15)

        composite_score = (
            w1 * s_spread +
            w2 * s_entropy +
            w3 * s_skill +
            w4 * s_comp_arr
        )
        composite_score = np.clip(composite_score, 0.0, 1.0)

        # 6. Categorical Confidence Labels
        th_high = self.th_cfg.get("high", 0.70)
        th_med = self.th_cfg.get("medium", 0.40)

        labels = np.full(grid_shape, "LOW", dtype=object)
        labels[composite_score >= th_med] = "MEDIUM"
        labels[composite_score >= th_high] = "HIGH"

        # 7. Out-of-distribution (OOD) detection
        # Triggered if extreme model divergence occurs or completeness < 50%
        ood_mask = (s_spread < 0.15) | (s_comp < 0.50)

        return {
            "score": composite_score.astype(np.float32),
            "label": labels,
            "s_spread": s_spread.astype(np.float32),
            "s_entropy": s_entropy.astype(np.float32),
            "s_skill": s_skill.astype(np.float32),
            "s_completeness": s_comp,
            "ood_mask": ood_mask,
            "mean_confidence": round(float(np.mean(composite_score)), 3),
            "pct_high": round(float(np.mean(labels == "HIGH") * 100), 1),
            "pct_medium": round(float(np.mean(labels == "MEDIUM") * 100), 1),
            "pct_low": round(float(np.mean(labels == "LOW") * 100), 1),
        }
