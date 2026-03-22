"""
Aegis — FastAPI application entry point.

Run with: uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as pipeline_router
from app.db.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="Aegis API",
    description="Multi-agent AI pipeline for software generation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "https://*.vercel.app",   # Vercel deployments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline_router, prefix="/api/pipeline")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "aegis-backend"}
