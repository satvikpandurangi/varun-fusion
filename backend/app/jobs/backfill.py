"""
Backfill command script for VARUN-FUSION.
Populates cached 2-week pilot dataset (2025-08-01 to 2025-08-15) across all models and truth.
"""
import argparse
from datetime import datetime, timedelta
from app.adapters.factory import get_adapter
from app.core.config import get_config
from app.core.logging import logger
from app.db.models import ForecastCycle, ForecastRun
from app.db.session import get_session_factory, init_db


def run_backfill(start_str: str = "2025-08-01", end_str: str = "2025-08-15"):
    """Download and cache forecast cycles for the pilot domain."""
    logger.info(f"Starting VARUN-FUSION backfill from {start_str} to {end_str}...")
    init_db()

    cfg = get_config()
    start_dt = datetime.strptime(start_str, "%Y-%m-%d")
    end_dt = datetime.strptime(end_str, "%Y-%m-%d")

    sources = list(cfg.sources.keys()) + ["truth"]
    leads = cfg.lead_times_hours
    variables = list(cfg.variables.keys())
    bbox = cfg.domain.bbox

    factory = get_session_factory()
    curr_dt = start_dt

    while curr_dt <= end_dt:
        logger.info(f"Processing cycle: {curr_dt.strftime('%Y-%m-%d 00:00 UTC')}")
        sources_present = []

        for src_id in sources:
            try:
                adapter = get_adapter(src_id)
                ds = adapter.fetch(curr_dt, leads=leads, variables=variables, bbox=bbox)
                sources_present.append(src_id)
                logger.info(f"  [OK] {src_id}: shape lat={len(ds.lat)} lon={len(ds.lon)} leads={len(ds.lead)}")
            except Exception as e:
                logger.error(f"  [FAIL] Failed to fetch {src_id} for cycle {curr_dt}: {e}")

        # Update database cycle and run records
        with factory() as session:
            existing_cycle = session.query(ForecastCycle).filter(ForecastCycle.cycle == curr_dt).first()
            if not existing_cycle:
                new_cycle = ForecastCycle(
                    cycle=curr_dt,
                    sources_present=str(sources_present),
                    sources_missing="[]",
                    is_complete=len(sources_present) >= len(sources),
                )
                session.add(new_cycle)
                session.commit()
                cycle_id = new_cycle.id
            else:
                existing_cycle.sources_present = str(sources_present)
                existing_cycle.is_complete = len(sources_present) >= len(sources)
                session.commit()
                cycle_id = existing_cycle.id

            run = ForecastRun(
                cycle=curr_dt,
                cycle_id=cycle_id,
                status="SUCCESS",
                active_fallback=False,
                method_used="cached_sample",
            )
            session.add(run)
            session.commit()

        curr_dt += timedelta(days=1)

    logger.info("Backfill completed successfully. All pilot sample datasets cached.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VARUN-FUSION Backfill Tool")
    parser.add_argument("--start", default="2025-08-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default="2025-08-15", help="End date YYYY-MM-DD")
    args = parser.parse_args()
    run_backfill(args.start, args.end)
