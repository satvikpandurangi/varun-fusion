"""
Main FastAPI application entrypoint for VARUN-FUSION.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routers import forecast, reports, system, verification
from app.core.config import get_config
from app.core.logging import logger
from app.db.session import init_db

DISCLAIMER_TEXT = "Forecaster guidance — not a public warning"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure database initialized
    logger.info("Initializing VARUN-FUSION backend...")
    init_db()
    logger.info("VARUN-FUSION backend online.")
    yield
    logger.info("Shutting down VARUN-FUSION backend.")


app = FastAPI(
    title="VARUN-FUSION Operational API",
    description=(
        "Adaptive AI–NWP Multi-Model Forecast Blending System for India.\n\n"
        f"**IMPORTANT OPERATIONAL NOTICE**: {DISCLAIMER_TEXT}.\n"
        "Smart India Hackathon 2026 | Problem Statement 26081 (MoES) | Team CodeX_2026 (Team ID 159951)."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for Next.js dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount versioned API routes (/api/v1)
app.include_router(system.router, prefix="/api/v1")
app.include_router(forecast.router, prefix="/api/v1")
app.include_router(verification.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")


@app.get("/")
def root():
    cfg = get_config()
    return {
        "system": cfg.system["name"],
        "tagline": cfg.system["tagline"],
        "version": cfg.system["version"],
        "docs": "/docs",
        "api_v1": "/api/v1",
        "disclaimer": DISCLAIMER_TEXT,
    }
