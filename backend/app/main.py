"""
Aegis — FastAPI application entry point.

Run with: uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Aegis API",
    description="Multi-agent AI pipeline for software generation",
    version="0.1.0",
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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "aegis-backend"}


# API routes will be added here as they're built:
# from app.api.routes import router
# app.include_router(router, prefix="/api")
