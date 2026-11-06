"""Outfits ("sets"): 2–5 garments, at most one per slot.

GET    /v1/outfits        — my outfits, newest first
POST   /v1/outfits        — create one
DELETE /v1/outfits/{id}   — delete one of mine

The rules live in app/recs/outfits.py. Total price is computed from current
catalogue prices on every read and never stored.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_catalog, get_current_user
from app.db.outfits import get_outfit_store
from app.recs.catalog import Catalog, Product
from app.recs.outfits import (
    SLOT_ORDER,
    OutfitRuleError,
    UnknownProductError,
    plan_outfit,
    total_price,
)
from app.schemas.auth import UserOut
from app.schemas.outfits import OutfitIn, OutfitItemOut, OutfitListOut, OutfitOut
from app.schemas.products import ProductOut

router = APIRouter(prefix="/outfits", tags=["outfits"])


def _outfit_out(outfit_id: str, name: str, items: list[tuple[Product, str]]) -> OutfitOut:
    items = sorted(items, key=lambda item: SLOT_ORDER.index(item[1]))
    products = [product for product, _ in items]
    return OutfitOut(
        id=outfit_id,
        name=name,
        items=[OutfitItemOut(slot=slot, product=ProductOut.of(p)) for p, slot in items],
        total_price=total_price(products),
        currency=products[0].currency if products else "GBP",
    )


@router.get("", response_model=OutfitListOut)
def list_outfits(
    user: UserOut = Depends(get_current_user),
    catalog: Catalog = Depends(get_catalog),
    store=Depends(get_outfit_store),
) -> OutfitListOut:
    outfits = []
    for row in store.list(user.id):
        items = [
            (catalog.product(item["product_id"]), item["slot"]) for item in row["outfit_items"]
        ]
        # A garment that has left the catalogue is skipped rather than failing the list.
        items = [(p, slot) for p, slot in items if p is not None]
        outfits.append(_outfit_out(row["id"], row["name"], items))
    return OutfitListOut(outfits=outfits)


@router.post("", response_model=OutfitOut, status_code=status.HTTP_201_CREATED)
def create_outfit(
    body: OutfitIn,
    user: UserOut = Depends(get_current_user),
    catalog: Catalog = Depends(get_catalog),
    store=Depends(get_outfit_store),
) -> OutfitOut:
    try:
        planned = plan_outfit(catalog, [str(p) for p in body.product_ids])
    except UnknownProductError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"No such product: {exc.product_id}") from exc
    except OutfitRuleError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    outfit_id = store.create(user.id, body.name, [(p.id, slot) for p, slot in planned])
    return _outfit_out(outfit_id, body.name, planned)


@router.delete("/{outfit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_outfit(
    outfit_id: UUID,
    user: UserOut = Depends(get_current_user),
    store=Depends(get_outfit_store),
) -> Response:
    if not store.delete(user.id, str(outfit_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such outfit")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
