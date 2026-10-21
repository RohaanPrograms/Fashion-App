"""Recording swipes.

POST   /v1/interactions — one like or dislike
DELETE /v1/interactions — forget every swipe (the demo's "start over")
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_catalog, get_current_user
from app.db.interactions import get_interaction_store
from app.recs.catalog import Catalog
from app.schemas.auth import UserOut
from app.schemas.interactions import ClearedOut, InteractionIn, InteractionOut

router = APIRouter(prefix="/interactions", tags=["interactions"])


@router.post("", response_model=InteractionOut, status_code=status.HTTP_201_CREATED)
def record(
    body: InteractionIn,
    user: UserOut = Depends(get_current_user),
    catalog: Catalog = Depends(get_catalog),
    store=Depends(get_interaction_store),
) -> InteractionOut:
    product_id = str(body.product_id)
    # Checked here rather than left to the database's foreign key, so a bad id
    # is a clear 404 instead of a constraint error.
    if catalog.position(product_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such product")
    store.add(user.id, product_id, body.type, source="feed", dwell_time_ms=body.dwell_time_ms)
    return InteractionOut(product_id=body.product_id, type=body.type)


@router.delete("", response_model=ClearedOut)
def start_over(
    user: UserOut = Depends(get_current_user), store=Depends(get_interaction_store)
) -> ClearedOut:
    return ClearedOut(deleted=store.clear(user.id))
