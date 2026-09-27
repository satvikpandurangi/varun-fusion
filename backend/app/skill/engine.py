"""
Rolling Skill Engine for VARUN-FUSION.
Computes and aggregates continuous, categorical, and spatial verification metrics
over rolling verification windows across pilot sub-regions.
"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import xarray as xr
from app.adapters.factory import get_adapter
from app.core.config import get_config
from app.core.logging import logger
from app.db.models import SkillScore
from app.db.session import get_session_factory
from app.skill.metrics import (
    compute_bias,
    compute_csi,
    compute_far,
    compute_fss_2d,
    compute_mae,
    compute_pod,
    compute_rmse,
)
from app.skill.regions import get_subregion_masks


class RollingSkillEngine:
    """
    Evaluates forecast skill against truth observations over rolling time horizons.
    Persists granular metrics into SQLite/PostgreSQL and Parquet for rapid indexing.
    """

    def __init__(self):
        self.cfg = get_config()
        self.parquet_path = Path("data/skill_history.parquet")
        self.parquet_path.parent.mkdir(parents=True, exist_ok=True)
        self.subregion_masks = get_subregion_masks()

    def get_verified_pairs(
        self,
        ref_cycle: datetime,
        window_days: int = 14,
    ) -> List[Tuple[datetime, datetime, int]]:
        """
        Find (forecast_cycle, valid_time, lead) pairs in the verification window
        where observations are already available.
        """
        pairs = []
        leads = self.cfg.lead_times_hours
        start_date = ref_cycle - timedelta(days=window_days)

        curr = start_date
        while curr <= ref_cycle:
            for lead in leads:
                valid_time = curr + timedelta(hours=lead)
                # Only evaluate if valid_time is strictly in the past or on ref_cycle
                if valid_time <= ref_cycle + timedelta(hours=max(leads)):
                    pairs.append((curr, valid_time, lead))
            curr += timedelta(days=1)
        return pairs

    def compute_rolling_skill(
        self,
        eval_cycle: datetime,
        window_days: int = 14,
        persist_db: bool = True,
    ) -> pd.DataFrame:
        """
        Compute rolling skill metrics for all active models, variables, leads, and regions.
        """
        logger.info(f"Computing rolling skill for cycle {eval_cycle.strftime('%Y-%m-%d')} (window={window_days}d)")
        models = [m for m in self.cfg.sources.keys() if self.cfg.sources[m].enabled]
        variables = list(self.cfg.variables.keys())
        leads = self.cfg.lead_times_hours
        regions = list(self.subregion_masks.keys())

        # Load truth adapter
        truth_adapter = get_adapter("truth")

        records = []
        db_records = []

        # Iterate over each model
        for model_id in models:
            adapter = get_adapter(model_id)

            for var_name in variables:
                for lead in leads:
                    # Accumulate forecast and observation values over rolling window
                    fcst_list = []
                    obs_list = []
                    fss_scores = {1: [], 3: [], 5: [], 9: []}

                    # Collect past cycles in rolling window
                    for d in range(1, window_days + 1):
                        past_cycle = eval_cycle - timedelta(days=d)
                        try:
                            ds_fcst = adapter.fetch(past_cycle, leads=[lead], variables=[var_name])
                            ds_truth = truth_adapter.fetch(past_cycle, leads=[lead], variables=[var_name])

                            f_arr = ds_fcst[var_name].sel(lead=lead).values  # (lat, lon)
                            o_arr = ds_truth[var_name].sel(lead=lead).values  # (lat, lon)

                            fcst_list.append(f_arr)
                            obs_list.append(o_arr)

                            # Spatial FSS for rain
                            if var_name == "rain24_mm":
                                th_heavy = self.cfg.thresholds["rain"]["heavy"]
                                for scale in [1, 3, 5, 9]:
                                    s_val = compute_fss_2d(f_arr, o_arr, threshold=th_heavy, window_size=scale)
                                    fss_scores[scale].append(s_val)
                        except Exception as e:
                            logger.debug(f"Missing past verification pair for {model_id} cycle {past_cycle}: {e}")
                            continue

                    if not fcst_list:
                        continue

                    # Stack across time: (n_cycles, lat, lon)
                    f_stack = np.array(fcst_list)
                    o_stack = np.array(obs_list)
                    sample_size = len(fcst_list)

                    # Compute metrics for each sub-region
                    for region_name, mask in self.subregion_masks.items():
                        # Extract points within region mask: (n_cycles, n_masked_points)
                        f_sub = f_stack[:, mask]
                        o_sub = o_stack[:, mask]

                        rmse_val = compute_rmse(f_sub, o_sub)
                        mae_val = compute_mae(f_sub, o_sub)
                        bias_val = compute_bias(f_sub, o_sub)

                        base_row = {
                            "cycle": eval_cycle,
                            "source_id": model_id,
                            "variable": var_name,
                            "lead": lead,
                            "region": region_name,
                            "sample_size": sample_size,
                            "RMSE": round(rmse_val, 3),
                            "MAE": round(mae_val, 3),
                            "BIAS": round(bias_val, 3),
                        }

                        # Threshold-specific event metrics
                        if var_name == "rain24_mm":
                            th_heavy = self.cfg.thresholds["rain"]["heavy"]
                            pod_heavy = compute_pod(f_sub, o_sub, th_heavy)
                            far_heavy = compute_far(f_sub, o_sub, th_heavy)
                            csi_heavy = compute_csi(f_sub, o_sub, th_heavy)
                            base_row.update({
                                "POD_heavy": round(pod_heavy, 3),
                                "FAR_heavy": round(far_heavy, 3),
                                "CSI_heavy": round(csi_heavy, 3),
                                "FSS_1": round(float(np.mean(fss_scores[1])), 3) if fss_scores[1] else 1.0,
                                "FSS_3": round(float(np.mean(fss_scores[3])), 3) if fss_scores[3] else 1.0,
                                "FSS_5": round(float(np.mean(fss_scores[5])), 3) if fss_scores[5] else 1.0,
                                "FSS_9": round(float(np.mean(fss_scores[9])), 3) if fss_scores[9] else 1.0,
                            })
                        elif var_name == "t2m_max_c":
                            th_heat = self.cfg.thresholds["t2m_max"]["heatwave"]
                            base_row.update({
                                "POD_heat": round(compute_pod(f_sub, o_sub, th_heat), 3),
                                "FAR_heat": round(compute_far(f_sub, o_sub, th_heat), 3),
                                "CSI_heat": round(compute_csi(f_sub, o_sub, th_heat), 3),
                            })
                        elif var_name == "ws10_ms":
                            th_wind = self.cfg.thresholds["ws10"]["squall"]
                            base_row.update({
                                "POD_squall": round(compute_pod(f_sub, o_sub, th_wind), 3),
                                "FAR_squall": round(compute_far(f_sub, o_sub, th_wind), 3),
                                "CSI_squall": round(compute_csi(f_sub, o_sub, th_wind), 3),
                            })

                        records.append(base_row)

                        if persist_db:
                            for metric_key in ["RMSE", "MAE", "BIAS"]:
                                db_records.append(
                                    SkillScore(
                                        cycle=eval_cycle,
                                        source_id=model_id,
                                        variable=var_name,
                                        lead=lead,
                                        region=region_name,
                                        metric=metric_key,
                                        value=base_row[metric_key],
                                        sample_size=sample_size,
                                    )
                                )
                            if var_name == "rain24_mm":
                                for m_key in ["CSI_heavy", "POD_heavy", "FAR_heavy", "FSS_3"]:
                                    db_records.append(
                                        SkillScore(
                                            cycle=eval_cycle,
                                            source_id=model_id,
                                            variable=var_name,
                                            lead=lead,
                                            region=region_name,
                                            metric=m_key,
                                            value=base_row[m_key],
                                            sample_size=sample_size,
                                        )
                                    )

        df = pd.DataFrame(records)

        # Save to Parquet
        if not df.empty:
            if self.parquet_path.exists():
                try:
                    existing_df = pd.read_parquet(self.parquet_path)
                    combined_df = pd.concat([existing_df, df], ignore_index=True).drop_duplicates(
                        subset=["cycle", "source_id", "variable", "lead", "region"],
                        keep="last"
                    )
                    combined_df.to_parquet(self.parquet_path, index=False)
                except Exception as e:
                    logger.warning(f"Could not merge parquet skill store: {e}")
                    df.to_parquet(self.parquet_path, index=False)
            else:
                df.to_parquet(self.parquet_path, index=False)

        # Persist to database
        if persist_db and db_records:
            factory = get_session_factory()
            with factory() as session:
                for rec in db_records:
                    # Avoid duplicate inserts
                    existing = session.query(SkillScore).filter(
                        SkillScore.cycle == rec.cycle,
                        SkillScore.source_id == rec.source_id,
                        SkillScore.variable == rec.variable,
                        SkillScore.lead == rec.lead,
                        SkillScore.region == rec.region,
                        SkillScore.metric == rec.metric,
                    ).first()
                    if existing:
                        existing.value = rec.value
                        existing.sample_size = rec.sample_size
                    else:
                        session.add(rec)
                session.commit()

        logger.info(f"Skill computation finished: {len(records)} regional metric rows recorded.")
        return df

    def compute_gridcell_rmse(
        self,
        eval_cycle: datetime,
        source_id: str,
        variable: str,
        lead: int,
        window_days: int = 14,
    ) -> np.ndarray:
        """
        Compute 2D spatial array of rolling RMSE for a given model, variable, and lead.
        Shape: (n_lat, n_lon). Used directly in inverse-error spatial weighting.
        """
        adapter = get_adapter(source_id)
        truth_adapter = get_adapter("truth")

        diffs = []
        for d in range(1, window_days + 1):
            past_cycle = eval_cycle - timedelta(days=d)
            try:
                ds_f = adapter.fetch(past_cycle, leads=[lead], variables=[variable])
                ds_o = truth_adapter.fetch(past_cycle, leads=[lead], variables=[variable])
                f_arr = ds_f[variable].sel(lead=lead).values
                o_arr = ds_o[variable].sel(lead=lead).values
                diffs.append((f_arr - o_arr) ** 2)
            except Exception:
                continue

        if not diffs:
            # Fallback to nominal default error if no history
            lats = self.cfg.domain.lats
            lons = self.cfg.domain.lons
            return np.full((len(lats), len(lons)), 5.0, dtype=np.float32)

        mean_sq = np.mean(np.array(diffs), axis=0)
        return np.sqrt(mean_sq).astype(np.float32)
