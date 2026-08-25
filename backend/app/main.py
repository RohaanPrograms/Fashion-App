"""FastAPI application entrypoint.

Run locally:
    cd backend
    uvicorn app.main:app --reload

Interactive docs at http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth
from app.core.config import get_settings
from app.core.errors import log_upstream_failure
from app.core.supabase_client import get_service_client

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
    """Liveness — "is this process alive?"

    Deliberately makes no outbound calls. If liveness went red during a Supabase
    outage, a host platform would restart a process that is working perfectly.

    `supabase_configured` reports only that the credentials are *present*. It is
    not a claim that Supabase is reachable — that is what /health/ready is for.
    """
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "supabase_configured": settings.supabase_configured,
    }


@app.get("/health/ready", tags=["meta"])
def readiness() -> dict:
    """Readiness — "can this process actually serve requests?"

    Really queries Supabase. Returns 503 when it cannot, so a monitor watching
    this endpoint sees an outage instead of a green light.

    The previous /health could not do this job: it reported
    `supabase_configured: true` — two non-empty environment strings — while the
    project was paused and every request was failing.
    """
    try:
        get_service_client().table("products").select("id").limit(1).execute()
    except Exception as exc:  # noqa: BLE001 — any failure means "not ready"
        log_upstream_failure("readiness check", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "supabase_reachable": False},
        ) from exc
    return {"status": "ok", "supabase_reachable": True}
