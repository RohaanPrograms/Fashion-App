"""Reading and writing outfits and their items."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.core.supabase_client import get_service_client
from ml.paging import fetch_all_pages


class SupabaseOutfitStore:
    def __init__(self, client):
        self._client = client

    def create(self, user_id: str, name: str, items: list[tuple[str, str]]) -> str:
        """Save an outfit and its (product_id, slot) items; returns the outfit id."""
        outfit = (
            self._client.table("outfits").insert({"user_id": user_id, "name": name}).execute().data[0]
        )
        try:
            self._client.table("outfit_items").insert(
                [
                    {"outfit_id": outfit["id"], "product_id": product_id, "slot": slot}
                    for product_id, slot in items
                ]
            ).execute()
        except Exception:
            # Two requests, so not atomic: undo the half-made outfit rather
            # than leave an empty one behind, then let the error surface.
            self._client.table("outfits").delete().eq("id", outfit["id"]).eq(
                "user_id", user_id
            ).execute()
            raise
        return outfit["id"]

    def list(self, user_id: str) -> list[dict]:
        """This user's outfits, newest first, each with its items embedded."""
        return fetch_all_pages(
            lambda start, end: self._client.table("outfits")
            .select("id, name, created_at, outfit_items(product_id, slot)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(start, end)
            .execute()
            .data
        )

    def replace(self, user_id: str, outfit_id: str, name: str, items: list[tuple[str, str]]) -> bool:
        """Edit one of this user's outfits: new name, new (product_id, slot) items.

        False if the user has no such outfit (nothing is changed). The edit is
        three requests (rename, remove the old items, insert the new), so not
        atomic: if the insert fails, the old name and items are put back
        rather than leaving the set emptied, then the error surfaces.
        """
        found = (
            self._client.table("outfits")
            .select("id, name, outfit_items(product_id, slot)")
            .eq("id", outfit_id)
            .eq("user_id", user_id)
            .execute()
            .data
        )
        if not found:
            return False
        old_name = found[0]["name"]
        old_items = [(i["product_id"], i["slot"]) for i in found[0].get("outfit_items") or []]

        def rows(pairs):
            return [{"outfit_id": outfit_id, "product_id": p, "slot": s} for p, s in pairs]

        self._client.table("outfits").update({"name": name}).eq("id", outfit_id).eq(
            "user_id", user_id
        ).execute()
        self._client.table("outfit_items").delete().eq("outfit_id", outfit_id).execute()
        try:
            self._client.table("outfit_items").insert(rows(items)).execute()
        except Exception:
            if old_items:
                self._client.table("outfit_items").insert(rows(old_items)).execute()
            self._client.table("outfits").update({"name": old_name}).eq("id", outfit_id).eq(
                "user_id", user_id
            ).execute()
            raise
        return True

    def delete(self, user_id: str, outfit_id: str) -> bool:
        """True if an outfit of this user's was deleted (its items go with it)."""
        result = (
            self._client.table("outfits").delete().eq("id", outfit_id).eq("user_id", user_id).execute()
        )
        return bool(result.data)


def get_outfit_store() -> SupabaseOutfitStore:
    try:
        return SupabaseOutfitStore(get_service_client())
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
