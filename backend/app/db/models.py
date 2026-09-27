"""
SQLAlchemy DB models for VARUN-FUSION.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now():
    return datetime.now(timezone.utc)


class ModelSource(Base):
    __tablename__ = "model_sources"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    kind = Column(String(20), nullable=False)  # nwp, ai, ensemble
    provenance = Column(String(20), nullable=False, default="CACHED")  # LIVE, CACHED, SYNTHETIC
    color = Column(String(20), nullable=False, default="#3B82F6")
    native_resolution = Column(Float, nullable=False, default=0.25)
    is_active = Column(Boolean, nullable=False, default=True)
    last_available_cycle = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "provenance": self.provenance,
            "color": self.color,
            "native_resolution": self.native_resolution,
            "is_active": self.is_active,
            "last_available_cycle": self.last_available_cycle.isoformat() if self.last_available_cycle else None,
        }


class ForecastCycle(Base):
    __tablename__ = "forecast_cycles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle = Column(DateTime, nullable=False, unique=True, index=True)
    sources_present = Column(Text, nullable=False, default="[]")  # JSON encoded list
    sources_missing = Column(Text, nullable=False, default="[]")  # JSON encoded list
    is_complete = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    runs = relationship("ForecastRun", back_populates="cycle_rel")


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle = Column(DateTime, nullable=False, index=True)
    cycle_id = Column(Integer, ForeignKey("forecast_cycles.id"), nullable=True)
    run_time = Column(DateTime, default=utc_now, nullable=False)
    status = Column(String(20), nullable=False, default="SUCCESS")  # SUCCESS, FAILED, RUNNING
    active_fallback = Column(Boolean, default=False)
    fallback_reason = Column(Text, nullable=True)
    method_used = Column(String(50), default="adaptive")
    metadata_json = Column(Text, nullable=True)

    cycle_rel = relationship("ForecastCycle", back_populates="runs")
    fallbacks = relationship("FallbackEvent", back_populates="run_rel")

    def to_dict(self):
        return {
            "id": self.id,
            "cycle": self.cycle.isoformat() if self.cycle else None,
            "run_time": self.run_time.isoformat() if self.run_time else None,
            "status": self.status,
            "active_fallback": self.active_fallback,
            "fallback_reason": self.fallback_reason,
            "method_used": self.method_used,
            "metadata_json": self.metadata_json,
        }


class SkillScore(Base):
    __tablename__ = "skill_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle = Column(DateTime, nullable=False, index=True)
    source_id = Column(String(50), nullable=False, index=True)
    variable = Column(String(50), nullable=False, index=True)
    lead = Column(Integer, nullable=False, index=True)
    region = Column(String(50), nullable=False, default="all", index=True)
    metric = Column(String(50), nullable=False, index=True)  # RMSE, MAE, BIAS, CSI, POD, FAR, FSS_3
    value = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False, default=1)
    computed_at = Column(DateTime, default=utc_now)

    def to_dict(self):
        return {
            "id": self.id,
            "cycle": self.cycle.isoformat() if self.cycle else None,
            "source_id": self.source_id,
            "variable": self.variable,
            "lead": self.lead,
            "region": self.region,
            "metric": self.metric,
            "value": self.value,
            "sample_size": self.sample_size,
        }


class FallbackEvent(Base):
    __tablename__ = "fallback_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("forecast_runs.id"), nullable=True)
    cycle = Column(DateTime, nullable=False, index=True)
    variable = Column(String(50), nullable=False)
    lead = Column(Integer, nullable=False)
    from_method = Column(String(50), nullable=False)
    to_method = Column(String(50), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    run_rel = relationship("ForecastRun", back_populates="fallbacks")

    def to_dict(self):
        return {
            "id": self.id,
            "cycle": self.cycle.isoformat() if self.cycle else None,
            "variable": self.variable,
            "lead": self.lead,
            "from_method": self.from_method,
            "to_method": self.to_method,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
