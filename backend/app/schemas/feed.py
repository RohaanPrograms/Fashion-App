from typing import Literal

from pydantic import BaseModel

from app.recs.feed import Feed
from app.schemas.products import ProductOut


class LikedRef(BaseModel):
    id: str
    name: str


class ReasonOut(BaseModel):
    kind: Literal["popular", "similar", "explore"]
    similarity: float | None
    because_of: LikedRef | None


class FeedItemOut(BaseModel):
    product: ProductOut
    reason: ReasonOut


class FeedOut(BaseModel):
    personalised: bool
    likes: int
    likes_needed: int
    items: list[FeedItemOut]

    @classmethod
    def of(cls, feed: Feed) -> "FeedOut":
        return cls(
            personalised=feed.personalised,
            likes=feed.likes,
            likes_needed=feed.likes_needed,
            items=[
                FeedItemOut(
                    product=ProductOut.of(item.product),
                    reason=ReasonOut(
                        kind=item.reason.kind,
                        similarity=item.reason.similarity,
                        because_of=None
                        if item.reason.because_of is None
                        else LikedRef(id=item.reason.because_of.id, name=item.reason.because_of.name),
                    ),
                )
                for item in feed.items
            ],
        )
