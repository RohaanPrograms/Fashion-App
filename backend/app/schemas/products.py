from pydantic import BaseModel

from app.recs.catalog import Product


class ProductOut(BaseModel):
    id: str
    name: str
    brand: str | None
    price: float | None
    currency: str
    image_url: str | None
    category: str | None
    colour: str | None

    @classmethod
    def of(cls, product: Product) -> "ProductOut":
        return cls(**{name: getattr(product, name) for name in cls.model_fields})
