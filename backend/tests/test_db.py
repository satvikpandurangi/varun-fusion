"""
Unit tests for VARUN-FUSION database models and session.
"""
from datetime import datetime
import pytest
from app.db.models import ForecastCycle, ForecastRun, ModelSource, SkillScore, FallbackEvent
from app.db.session import get_session_factory, init_db


def test_database_initialization_and_seeding():
    init_db()
    factory = get_session_factory()
    with factory() as session:
        sources = session.query(ModelSource).all()
        assert len(sources) >= 4
        source_ids = {s.id for s in sources}
        assert "ecmwf_ifs" in source_ids
        assert "ecmwf_aifs" in source_ids
        assert "noaa_gfs" in source_ids
        assert "ncmrwf" in source_ids


def test_run_and_fallback_logging():
    init_db()
    factory = get_session_factory()
    test_cycle = datetime(2029, 1, 15, 0, 0, 0)

    with factory() as session:
        # Clean up any previous test artifacts to ensure test idempotency
        session.query(FallbackEvent).filter(FallbackEvent.cycle == test_cycle).delete()
        session.query(ForecastRun).filter(ForecastRun.cycle == test_cycle).delete()
        session.query(ForecastCycle).filter(ForecastCycle.cycle == test_cycle).delete()
        session.query(SkillScore).filter(SkillScore.cycle == test_cycle).delete()
        session.commit()

        cycle_obj = ForecastCycle(
            cycle=test_cycle,
            sources_present='["ecmwf_ifs", "ecmwf_aifs", "noaa_gfs"]',
            sources_missing='["ncmrwf"]',
            is_complete=False,
        )
        session.add(cycle_obj)
        session.commit()

        run_obj = ForecastRun(
            cycle=test_cycle,
            cycle_id=cycle_obj.id,
            status="SUCCESS",
            active_fallback=True,
            fallback_reason="Missing NCMRWF source; renormalized remaining weights",
            method_used="inverse_error",
        )
        session.add(run_obj)
        session.commit()

        fb_event = FallbackEvent(
            run_id=run_obj.id,
            cycle=test_cycle,
            variable="rain24_mm",
            lead=24,
            from_method="adaptive",
            to_method="inverse_error",
            reason="Missing source ncmrwf triggers B2 fallback",
        )
        session.add(fb_event)

        skill_obj = SkillScore(
            cycle=test_cycle,
            source_id="ecmwf_ifs",
            variable="rain24_mm",
            lead=24,
            region="coastal",
            metric="RMSE",
            value=8.45,
            sample_size=30,
        )
        session.add(skill_obj)
        session.commit()

        # Query back and verify
        saved_run = session.query(ForecastRun).filter(ForecastRun.id == run_obj.id).first()
        assert saved_run is not None
        assert saved_run.active_fallback is True
        assert len(saved_run.fallbacks) == 1
        assert saved_run.fallbacks[0].to_method == "inverse_error"

        saved_skill = session.query(SkillScore).filter(
            SkillScore.cycle == test_cycle,
            SkillScore.source_id == "ecmwf_ifs",
            SkillScore.metric == "RMSE"
        ).first()
        assert saved_skill is not None
        assert pytest.approx(saved_skill.value, 0.01) == 8.45
