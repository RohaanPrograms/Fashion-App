"""FastAPI application entrypoint.

Run locally:
    cd backend
    uvicorn app.main:app --reload

Interactive docs at http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Fashion App API",
    version="0.1.0",
    description="Backend for the fashion discovery app (Phase 0 skeleton).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/v1")


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness probe + quick config sanity check."""
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "supabase_configured": settings.supabase_configured,
    }
