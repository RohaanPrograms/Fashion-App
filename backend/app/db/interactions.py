"""Reading and writing the interactions table (every swipe)."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.core.supabase_client import get_service_client
from ml.paging import fetch_all_pages


class SupabaseInteractionStore:
    def __init__(self, client):
        self._client = client

    def history_rows(self, user_id: str) -> list[dict]:
        """All of this user's interactions, oldest first."""
        return fetch_all_pages(
            lambda start, end: self._client.table("interactions")
            .select("product_id, type, created_at")
            .eq("user_id", user_id)
            .order("created_at")
            .range(start, end)
            .execute()
            .data
        )

    def add(
        self,
        user_id: str,
        product_id: str,
        kind: str,
        source: str,
        dwell_time_ms: int | None = None,
    ) -> None:
        self._client.table("interactions").insert(
            {
                "user_id": user_id,
                "product_id": product_id,
                "type": kind,
                "source": source,
                "dwell_time_ms": dwell_time_ms,
            }
        ).execute()

    def clear(self, user_id: str) -> int:
        """Delete every interaction this user has; returns how many."""
        result = self._client.table("interactions").delete().eq("user_id", user_id).execute()
        return len(result.data or [])


def get_interaction_store() -> SupabaseInteractionStore:
    try:
        return SupabaseInteractionStore(get_service_client())
    except RuntimeError as exc:  # Supabase credentials not configured
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
