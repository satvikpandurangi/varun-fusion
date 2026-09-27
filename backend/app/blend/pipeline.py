"""
Master Multi-Model Blending & Safe Fallback Pipeline for VARUN-FUSION.
Orchestrates model fetching, weight calculation (B0-B3), confidence assessment,
extreme-risk detection, and automated fail-safe degradation cascades.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import numpy as np
from app.adapters.factory import get_adapter
from app.blend.baselines import (
    blend_forecasts,
    compute_b0_weights,
    compute_b1_weights,
    compute_b2_weights,
)
from app.blend.ml_gate import get_ml_gate
from app.confidence.scoring import ForecasterConfidenceEngine
from app.core.config import get_config
from app.core.logging import logger
from app.db.models import FallbackEvent, ForecastRun
from app.db.session import get_session_factory
from app.extremes.risk_layer import ExtremeRiskEngine
from app.skill.engine import RollingSkillEngine

DISCLAIMER_TEXT = "Forecaster guidance — not a public warning"


class BlendingPipeline:
    """
    Production-grade operational blending pipeline.
    Executes adaptive ML gate with rigorous fallback guards and audit logging.
    """

    def __init__(self):
        self.cfg = get_config()
        self.skill_engine = RollingSkillEngine()
        self.confidence_engine = ForecasterConfidenceEngine()
        self.extreme_engine = ExtremeRiskEngine()

    def run_cycle_blend(
        self,
        cycle: datetime,
        variable: str,
        lead: int,
        method: str = "adaptive",
        simulate_missing_models: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute full blending pipeline for a specific cycle, variable, and lead.
        Guarantees safe fallback if models are delayed, confidence is low, or ML gate fails.
        """
        grid_shape = (len(self.cfg.domain.lats), len(self.cfg.domain.lons))
        configured_models = [m for m in self.cfg.sources.keys() if self.cfg.sources[m].enabled]

        # 1. Fetch available forecast models
        raw_forecasts = {}
        missing_models = []
        provenance_set = set()

        for mid in configured_models:
            if simulate_missing_models and mid in simulate_missing_models:
                missing_models.append(mid)
                continue
            try:
                adapter = get_adapter(mid)
                ds = adapter.fetch(cycle, leads=[lead], variables=[variable])
                arr = ds[variable].sel(lead=lead).values
                raw_forecasts[mid] = arr
                provenance_set.add(ds.attrs.get("provenance", "CACHED"))
            except Exception as e:
                logger.warning(f"Model {mid} unavailable for cycle {cycle} lead={lead}: {e}")
                missing_models.append(mid)

        available_models = list(raw_forecasts.keys())
        if not available_models:
            raise RuntimeError(f"No forecast sources available for cycle {cycle.isoformat()}")

        # Determine overall provenance
        provenance = "LIVE" if "LIVE" in provenance_set else ("SYNTHETIC" if "SYNTHETIC" in provenance_set else "CACHED")

        effective_method = method
        fallback_active = False
        fallback_reason = None

        # 2. Check missing model trigger
        if missing_models:
            fallback_active = True
            fallback_reason = f"Source(s) {missing_models} delayed or missing; renormalized remaining {len(available_models)} models"
            logger.info(f"Fallback active: {fallback_reason}")

        # 3. Compute weights with Safe Fallback hierarchy: B3 -> B2 -> B0 -> B1
        weights: Dict[str, np.ndarray] = {}

        if effective_method == "adaptive":
            try:
                ml_gate = get_ml_gate(variable)
                w_ml, _ = ml_gate.predict_weights(
                    cycle=cycle,
                    lead=lead,
                    raw_forecasts=raw_forecasts,
                    tau=self.cfg.blending["ml_gate"]["temperature_tau"],
                    floor=self.cfg.blending["constraints"]["weight_floor"],
                    cap=self.cfg.blending["constraints"]["weight_cap"],
                )
                weights = w_ml
            except Exception as e:
                logger.error(f"Adaptive ML Gate error: {e}. Falling back to B2 (Inverse Error).")
                effective_method = "inverse_error"
                fallback_active = True
                fallback_reason = f"ML Gate failure: {e}; fell back to inverse_error (B2)"

        if effective_method == "inverse_error":
            weights = compute_b2_weights(
                cycle=cycle,
                variable=variable,
                lead=lead,
                available_models=available_models,
                skill_engine=self.skill_engine,
                grid_shape=grid_shape,
                p=self.cfg.blending["p_inverse_error"],
                epsilon=self.cfg.blending["epsilon_inverse_error"],
                floor=self.cfg.blending["constraints"]["weight_floor"],
                cap=self.cfg.blending["constraints"]["weight_cap"],
            )
        elif effective_method == "best_single":
            weights = compute_b0_weights(
                cycle=cycle,
                variable=variable,
                lead=lead,
                available_models=available_models,
                skill_engine=self.skill_engine,
                grid_shape=grid_shape,
            )
        elif effective_method == "equal":
            weights = compute_b1_weights(
                available_models=available_models,
                grid_shape=grid_shape,
            )

        # 4. Synthesize initial blended field
        blended_grid = blend_forecasts(raw_forecasts, weights)

        # 5. Assess Confidence & check for Out-of-Distribution fallback
        recent_rmse = self.skill_engine.compute_gridcell_rmse(cycle, available_models[0], variable, lead)
        conf_diagnostics = self.confidence_engine.compute_confidence(
            raw_forecasts=raw_forecasts,
            weights=weights,
            variable=variable,
            recent_rmse=recent_rmse,
        )

        # If adaptive method was used and mean confidence is critically LOW or OOD is triggered:
        # Fall back to inverse_error or best single
        if method == "adaptive" and (conf_diagnostics["mean_confidence"] < 0.35 or np.mean(conf_diagnostics["ood_mask"]) > 0.4):
            logger.warning(f"Low confidence ({conf_diagnostics['mean_confidence']:.2f}) or OOD triggered. Falling back to B2.")
            effective_method = "inverse_error"
            fallback_active = True
            fallback_reason = f"Low confidence ({conf_diagnostics['mean_confidence']:.2f}) or OOD conditions; fell back to inverse_error (B2)"
            weights = compute_b2_weights(
                cycle=cycle,
                variable=variable,
                lead=lead,
                available_models=available_models,
                skill_engine=self.skill_engine,
                grid_shape=grid_shape,
            )
            blended_grid = blend_forecasts(raw_forecasts, weights)
            # Recompute confidence with new weights
            conf_diagnostics = self.confidence_engine.compute_confidence(
                raw_forecasts=raw_forecasts,
                weights=weights,
                variable=variable,
                recent_rmse=recent_rmse,
            )

        # 6. Extreme-Aware Layer & Minority Extreme Signals
        extreme_diagnostics = self.extreme_engine.compute_extreme_risk_layer(
            cycle=cycle,
            lead=lead,
            raw_forecasts=raw_forecasts,
            blended_forecast=blended_grid,
            variable=variable,
        )

        # 7. Identify Dominant Source per cell
        stacked_w = np.array([weights[mid] for mid in available_models], dtype=np.float32)
        dom_idx = np.argmax(stacked_w, axis=0)
        dom_weight = np.max(stacked_w, axis=0)
        dom_source_grid = np.array([[available_models[dom_idx[r, c]] for c in range(grid_shape[1])] for r in range(grid_shape[0])])

        # 8. Record fallback event in DB if triggered
        if fallback_active:
            factory = get_session_factory()
            try:
                with factory() as session:
                    fb_event = FallbackEvent(
                        cycle=cycle,
                        variable=variable,
                        lead=lead,
                        from_method=method,
                        to_method=effective_method,
                        reason=fallback_reason or "Automated resilience cascade",
                    )
                    session.add(fb_event)
                    session.commit()
            except Exception as e:
                logger.debug(f"Could not persist fallback event to DB: {e}")

        return {
            "cycle": cycle.isoformat(),
            "variable": variable,
            "lead": lead,
            "method_requested": method,
            "method_effective": effective_method,
            "fallback_active": fallback_active,
            "fallback_reason": fallback_reason,
            "provenance": provenance,
            "disclaimer": DISCLAIMER_TEXT,
            "blended_grid": blended_grid,
            "raw_forecasts": raw_forecasts,
            "weights": weights,
            "dominant_source": dom_source_grid,
            "dominant_weight": dom_weight,
            "confidence_score": conf_diagnostics["score"],
            "confidence_label": conf_diagnostics["label"],
            "confidence_mean": conf_diagnostics["mean_confidence"],
            "pct_high": conf_diagnostics["pct_high"],
            "pct_medium": conf_diagnostics["pct_medium"],
            "pct_low": conf_diagnostics["pct_low"],
            "extreme_risk": extreme_diagnostics["risk_score"],
            "extreme_category": extreme_diagnostics["risk_category"],
            "minority_alerts": extreme_diagnostics["minority_alerts"],
            "n_minority_alerts": extreme_diagnostics["n_alerts"],
        }


_PIPELINE = None


def get_blending_pipeline() -> BlendingPipeline:
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = BlendingPipeline()
    return _PIPELINE
