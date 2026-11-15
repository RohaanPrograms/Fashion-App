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
    # For the card's "About this piece" panel.
    type: str | None  # "Vest top"
    pattern: str | None  # "Solid"
    description: str | None
    colour_family: str | None  # "Beige" for "Light Beige": the wardrobe's Colour filter

    @classmethod
    def of(cls, product: Product) -> "ProductOut":
        return cls(
            id=product.id,
            name=product.name,
            brand=product.brand,
            price=product.price,
            currency=product.currency,
            image_url=product.image_url,
            category=product.category,
            colour=product.colour,
            type=product.product_type,
            pattern=product.pattern,
            description=product.description,
            colour_family=product.colour_family,
        )
