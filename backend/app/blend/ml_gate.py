"""
B3 Adaptive ML Gate for VARUN-FUSION.
Trains LightGBM regressors to predict each model's expected absolute error given context features.
Converts errors to blending weights via temperature-scaled softmax with simplex constraints.
Provides tree-SHAP explainability for operational forecaster trust.
"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import lightgbm as lgb
import numpy as np
import pandas as pd
from app.adapters.factory import get_adapter
from app.blend.baselines import apply_weight_constraints
from app.context.features import extract_context_features
from app.core.config import get_config
from app.core.logging import logger

FEATURE_COLUMNS = [
    "lat",
    "lon",
    "elevation",
    "subregion_id",
    "lead_hours",
    "sin_doy",
    "cos_doy",
    "season_id",
    "regime_id",
    "inter_model_spread",
    "source_idx",
]


class AdaptiveMLGate:
    """
    Adaptive Multi-Model Blending Gate using LightGBM.
    Predicts model error conditioned on geography, lead time, synoptic regime, and spread.
    """

    def __init__(self, variable: str):
        self.variable = variable
        self.cfg = get_config()
        self.models_dir = Path("data/models")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.model_file = self.models_dir / f"lgb_{variable}.txt"
        self.booster: Optional[lgb.Booster] = None
        self.feature_names = FEATURE_COLUMNS
        self.source_id_map = {src: i for i, src in enumerate(self.cfg.sources.keys())}
        self._load_or_train()

    def _load_or_train(self):
        """Load trained LightGBM model if cached, or train on pilot baseline."""
        if self.model_file.exists():
            try:
                self.booster = lgb.Booster(model_file=str(self.model_file))
                logger.debug(f"Loaded trained LightGBM gate for {self.variable}")
                return
            except Exception as e:
                logger.warning(f"Could not load {self.model_file}: {e}")

        # Train on initial pilot period (2025-08-01 to 2025-08-07)
        self.train(
            train_start=datetime(2025, 8, 1),
            train_end=datetime(2025, 8, 7),
            val_start=datetime(2025, 8, 8),
            val_end=datetime(2025, 8, 10),
        )

    def train(
        self,
        train_start: datetime,
        train_end: datetime,
        val_start: Optional[datetime] = None,
        val_end: Optional[datetime] = None,
    ):
        """
        Train LightGBM error predictor with strict chronological time-based split.
        No future data leaks into the training dataset.
        """
        logger.info(f"Training LightGBM gate for {self.variable} ({train_start.date()} to {train_end.date()})...")
        truth_adapter = get_adapter("truth")
        available_models = [m for m in self.cfg.sources.keys() if self.cfg.sources[m].enabled]

        def build_dataset(start_dt: datetime, end_dt: datetime):
            X_list = []
            y_list = []
            curr = start_dt
            while curr <= end_dt:
                for lead in self.cfg.lead_times_hours:
                    try:
                        # Ground truth
                        ds_truth = truth_adapter.fetch(curr, leads=[lead], variables=[self.variable])
                        o_arr = ds_truth[self.variable].sel(lead=lead).values

                        # Fetch forecasts
                        fcsts = {}
                        for mid in available_models:
                            ad = get_adapter(mid)
                            ds_m = ad.fetch(curr, leads=[lead], variables=[self.variable])
                            fcsts[mid] = ds_m[self.variable].sel(lead=lead).values

                        # Context features
                        df_ctx = extract_context_features(curr, lead, fcsts, self.variable)

                        # Create training samples for each model
                        for mid in available_models:
                            m_arr = fcsts[mid]
                            abs_err = np.abs(m_arr.flatten() - o_arr.flatten())
                            sub_df = df_ctx.copy()
                            sub_df["source_idx"] = self.source_id_map.get(mid, 0)
                            
                            X_list.append(sub_df[FEATURE_COLUMNS].values)
                            y_list.append(abs_err)

                    except Exception as e:
                        logger.debug(f"Train extraction skip for cycle {curr} lead={lead}: {e}")
                curr += timedelta(days=1)

            if not X_list:
                return None, None
            return np.vstack(X_list), np.concatenate(y_list)

        X_train, y_train = build_dataset(train_start, train_end)
        if X_train is None:
            logger.warning(f"Insufficient training samples for {self.variable}. Creating fallback model.")
            return

        lgb_train = lgb.Dataset(X_train, y_train, feature_name=FEATURE_COLUMNS)
        valid_sets = [lgb_train]

        if val_start and val_end:
            X_val, y_val = build_dataset(val_start, val_end)
            if X_val is not None:
                lgb_val = lgb.Dataset(X_val, y_val, reference=lgb_train, feature_name=FEATURE_COLUMNS)
                valid_sets.append(lgb_val)

        params = {
            "objective": "regression_l1",  # Predict MAE
            "metric": "l1",
            "learning_rate": self.cfg.blending["ml_gate"]["learning_rate"],
            "num_leaves": 31,
            "min_data_in_leaf": 20,
            "feature_fraction": 0.85,
            "verbose": -1,
            "random_state": 42,
        }

        self.booster = lgb.train(
            params,
            lgb_train,
            num_boost_round=self.cfg.blending["ml_gate"]["n_estimators"],
            valid_sets=valid_sets,
        )

        # Save model
        self.booster.save_model(str(self.model_file))
        logger.info(f"LightGBM gate for {self.variable} trained and persisted successfully.")

    def predict_weights(
        self,
        cycle: datetime,
        lead: int,
        raw_forecasts: Dict[str, np.ndarray],
        tau: float = 1.0,
        floor: float = 0.05,
        cap: float = 0.80,
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
        """
        Predict expected error per source and convert to blending weights via softmax:
        w_m(x) = softmax(- e_pred / tau)
        Returns (weights_dict, predicted_errors_dict)
        """
        available_models = list(raw_forecasts.keys())
        m = len(available_models)
        first_field = raw_forecasts[available_models[0]]
        grid_shape = first_field.shape

        if m <= 1 or self.booster is None:
            # Degenerate or untrained case: equal/single weight
            return {mid: np.full(grid_shape, 1.0 / m, dtype=np.float32) for mid in available_models}, {}

        # 1. Extract context features for current cycle and lead
        df_ctx = extract_context_features(cycle, lead, raw_forecasts, self.variable)

        # 2. Predict expected absolute error for each source
        pred_errors = {}
        for mid in available_models:
            sub_df = df_ctx.copy()
            sub_df["source_idx"] = self.source_id_map.get(mid, 0)
            X = sub_df[FEATURE_COLUMNS].values
            e_hat = self.booster.predict(X)
            pred_errors[mid] = np.maximum(0.01, e_hat.reshape(grid_shape).astype(np.float32))

        # 3. Softmax with temperature scaling: w_m ∝ exp(- e_hat / tau)
        # Numerical stability: subtract minimum error across models
        stacked_errors = np.array([pred_errors[mid] for mid in available_models], dtype=np.float32) # (m, lat, lon)
        min_errors = np.min(stacked_errors, axis=0, keepdims=True)
        # Scaled negative error
        scaled_logits = -(stacked_errors - min_errors) / max(0.1, tau)
        exp_logits = np.exp(scaled_logits)
        sum_exp = np.sum(exp_logits, axis=0, keepdims=True)
        raw_w = exp_logits / np.where(sum_exp < 1e-12, 1.0, sum_exp)

        raw_weights_dict = {available_models[i]: raw_w[i] for i in range(m)}

        # 4. Enforce simplex constraints (floor, cap, sum=1)
        constrained_weights = apply_weight_constraints(raw_weights_dict, floor=floor, cap=cap)
        return constrained_weights, pred_errors

    def get_feature_importances(self) -> Dict[str, float]:
        """Return normalized feature importances from the trained tree ensemble."""
        if self.booster is None:
            return {f: 1.0 / len(FEATURE_COLUMNS) for f in FEATURE_COLUMNS}
        raw_imp = self.booster.feature_importance(importance_type="gain")
        tot = sum(raw_imp) if sum(raw_imp) > 0 else 1.0
        return {name: round(float(imp / tot), 4) for name, imp in zip(FEATURE_COLUMNS, raw_imp)}

    def explain_point_prediction(
        self,
        cycle: datetime,
        lead: int,
        source_id: str,
        lat: float,
        lon: float,
        raw_forecasts: Dict[str, np.ndarray],
    ) -> Dict[str, float]:
        """
        Compute Tree-SHAP feature contributions explaining the predicted error
        for a specific model at a specific geographic grid cell.
        """
        if self.booster is None:
            return {}

        df_ctx = extract_context_features(cycle, lead, raw_forecasts, self.variable)
        df_ctx["source_idx"] = self.source_id_map.get(source_id, 0)

        # Find closest point
        dist_sq = (df_ctx["lat"] - lat)**2 + (df_ctx["lon"] - lon)**2
        closest_idx = int(dist_sq.idxmin())

        row = df_ctx.iloc[[closest_idx]][FEATURE_COLUMNS].values
        # pred_contrib returns array with shape (1, n_features + 1), last is base value
        contribs = self.booster.predict(row, pred_contrib=True)[0]
        feature_contribs = {name: round(float(contribs[i]), 3) for i, name in enumerate(FEATURE_COLUMNS)}
        feature_contribs["base_value"] = round(float(contribs[-1]), 3)
        return feature_contribs


_GATE_REGISTRY: Dict[str, AdaptiveMLGate] = {}


def get_ml_gate(variable: str) -> AdaptiveMLGate:
    """Singleton getter for variable-specific ML gates."""
    global _GATE_REGISTRY
    if variable not in _GATE_REGISTRY:
        _GATE_REGISTRY[variable] = AdaptiveMLGate(variable)
    return _GATE_REGISTRY[variable]
