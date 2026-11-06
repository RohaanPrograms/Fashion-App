from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.recs.outfits import MAX_ITEMS, MIN_ITEMS
from app.schemas.products import ProductOut


class OutfitIn(BaseModel):
    # Strip surrounding spaces first, so "   " counts as empty.
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=60)
    product_ids: list[UUID] = Field(min_length=MIN_ITEMS, max_length=MAX_ITEMS)


class OutfitItemOut(BaseModel):
    slot: str
    product: ProductOut


class OutfitOut(BaseModel):
    id: str
    name: str
    items: list[OutfitItemOut]
    total_price: float | None
    currency: str


class OutfitListOut(BaseModel):
    outfits: list[OutfitOut]
