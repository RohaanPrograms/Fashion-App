"""The wardrobe: every garment the user has liked.

GET    /v1/wardrobe               — liked garments, most recent first
DELETE /v1/wardrobe/{product_id}  — take one out

Every swipe-right enters the wardrobe; there is no separate save. Removing a
garment records a 'remove' interaction rather than deleting the like: the
garment still counts toward the user's taste, and after a cool-down it may
reappear in the feed (see app/recs/history.py).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_catalog, get_current_user
from app.db.interactions import get_interaction_store
from app.recs.catalog import Catalog
from app.recs.history import REMOVE, summarise
from app.schemas.auth import UserOut
from app.schemas.products import ProductOut
from app.schemas.wardrobe import WardrobeOut

router = APIRouter(prefix="/wardrobe", tags=["wardrobe"])


@router.get("", response_model=WardrobeOut)
def wardrobe(
    user: UserOut = Depends(get_current_user),
    catalog: Catalog = Depends(get_catalog),
    store=Depends(get_interaction_store),
) -> WardrobeOut:
    history = summarise(store.history_rows(user.id))
    products = [catalog.product(p) for p in history.wardrobe]
    items = [ProductOut.of(p) for p in products if p is not None]
    return WardrobeOut(count=len(items), items=items)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(
    product_id: UUID,
    user: UserOut = Depends(get_current_user),
    store=Depends(get_interaction_store),
) -> Response:
    product_id_str = str(product_id)
    history = summarise(store.history_rows(user.id))
    if product_id_str not in history.wardrobe:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not in your wardrobe")
    store.add(user.id, product_id_str, REMOVE, source="wardrobe")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
