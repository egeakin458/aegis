"""
Aegis — FastAPI application entry point.

Run with: uvicorn app.main:app --reload --port 8000
"""

import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as pipeline_router
from app.config import settings
from app.db.database import close_db, init_db
from app.launcher import app_launcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    settings.validate_required()
    await init_db()
    yield
    await app_launcher.shutdown()
    await close_db()


app = FastAPI(
    title="Aegis API",
    description="Multi-agent AI pipeline for software generation",
    version="0.1.0",
    lifespan=lifespan,
)


# CORS — allow the Next.js frontend to connect.
# localhost is matched exactly; an optional production domain (settings.allowed_origin)
# is matched via regex-escaped exact match (Starlette's allow_origins does NOT support globs).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=re.escape(settings.allowed_origin) if settings.allowed_origin else None,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(pipeline_router, prefix="/api/pipeline")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "aegis-backend"}
