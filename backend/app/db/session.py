"""
Database session and initialization for VARUN-FUSION.
Supports SQLite (default local) and PostgreSQL.
"""
import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import get_config
from app.core.logging import logger
from app.db.models import Base, ModelSource

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        cfg = get_config()
        db_url = os.getenv("DATABASE_URL", cfg.storage.get("db_url", "sqlite:///./data/varun_fusion.db"))
        
        # If sqlite, ensure parent directory exists
        if db_url.startswith("sqlite:///"):
            sqlite_path = db_url.replace("sqlite:///", "")
            p = Path(sqlite_path).resolve().parent
            p.mkdir(parents=True, exist_ok=True)
            _engine = create_engine(db_url, connect_args={"check_same_thread": False})
        else:
            _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        eng = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and register initial model sources from configuration."""
    eng = get_engine()
    Base.metadata.create_all(bind=eng)
    logger.info("Database tables verified/created successfully.")

    cfg = get_config()
    factory = get_session_factory()
    with factory() as session:
        for src_id, src_cfg in cfg.sources.items():
            existing = session.query(ModelSource).filter(ModelSource.id == src_id).first()
            if not existing:
                src = ModelSource(
                    id=src_id,
                    name=src_cfg.name,
                    kind=src_cfg.kind,
                    provenance="CACHED",
                    color=src_cfg.color,
                    native_resolution=src_cfg.native_resolution,
                    is_active=src_cfg.enabled,
                )
                session.add(src)
            else:
                existing.name = src_cfg.name
                existing.kind = src_cfg.kind
                existing.color = src_cfg.color
                existing.native_resolution = src_cfg.native_resolution
                existing.is_active = src_cfg.enabled
        session.commit()
    logger.info("Model sources catalog initialized.")
