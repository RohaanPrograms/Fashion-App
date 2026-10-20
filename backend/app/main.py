"""FastAPI application entrypoint.

Run locally:
    cd backend
    uvicorn app.main:app --reload

Interactive docs at http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.api.v1 import auth
from app.core.config import get_settings
from app.core.errors import log_upstream_failure
from app.core.supabase_client import get_service_client
from app.recs.catalog import catalog_state

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Load the catalogue once at boot, so the first visitor does not wait.

    A failure is logged inside get() and retried on demand; the server still
    starts, and /health/ready reports the catalogue as not loaded.
    """
    await run_in_threadpool(catalog_state.get)
    yield


app = FastAPI(
    title="Fashion App API",
    version="0.1.0",
    description="Backend for the fashion discovery app.",
    lifespan=lifespan,
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

    catalog = catalog_state.get()
    if catalog is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "supabase_reachable": True, "catalog_loaded": False},
        )
    return {
        "status": "ok",
        "supabase_reachable": True,
        "catalog_loaded": True,
        "products": len(catalog),
        "model_version": catalog.model_version,
    }
