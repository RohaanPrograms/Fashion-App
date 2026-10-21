from pydantic import BaseModel

from app.schemas.products import ProductOut


class WardrobeOut(BaseModel):
    count: int
    items: list[ProductOut]
