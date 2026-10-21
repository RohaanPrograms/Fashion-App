"""The swipe feed and card details.

GET /v1/feed?limit=10     — the next cards, best-sellers until 3 likes, then personalised
GET /v1/products/{id}     — one garment's details

The style vector is recomputed on every request from the user's history: one
query plus a few hundred microseconds of numpy. Nothing is cached, so the feed
can never fall out of step with the swipes.
"""

from dataclasses import replace
from uuid import UUID

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_catalog, get_current_user, get_rng
from app.db.interactions import get_interaction_store
from app.recs.catalog import Catalog
from app.recs.feed import build_feed
from app.recs.history import summarise
from app.schemas.auth import UserOut
from app.schemas.feed import FeedOut
from app.schemas.products import ProductOut
from ml import constants

router = APIRouter(tags=["feed"])


@router.get("/feed", response_model=FeedOut)
def feed(
    limit: int = Query(constants.FEED_BATCH_SIZE, ge=1, le=50),
    # The app fetches the next batch before the current one is fully swiped.
    # It lists the cards it still holds so they are not sent twice. Not a vote:
    # nothing is saved, they are only left out of this one response.
    exclude: list[UUID] = Query(default=[], max_length=50),
    user: UserOut = Depends(get_current_user),
    catalog: Catalog = Depends(get_catalog),
    store=Depends(get_interaction_store),
    rng: np.random.Generator = Depends(get_rng),
) -> FeedOut:
    history = summarise(store.history_rows(user.id))
    if exclude:
        history = replace(history, hidden=history.hidden | {str(p) for p in exclude})
    return FeedOut.of(build_feed(catalog, history, limit, rng))


@router.get("/products/{product_id}", response_model=ProductOut)
def product(
    product_id: UUID,
    user: UserOut = Depends(get_current_user),
    catalog: Catalog = Depends(get_catalog),
) -> ProductOut:
    found = catalog.product(str(product_id))
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such product")
    return ProductOut.of(found)
