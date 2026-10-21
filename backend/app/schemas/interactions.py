from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class InteractionIn(BaseModel):
    product_id: UUID
    type: Literal["like", "dislike"]
    # Capped at 60 s, matching the database: longer means the phone was put down.
    dwell_time_ms: int | None = Field(default=None, ge=0, le=60_000)


class InteractionOut(BaseModel):
    product_id: UUID
    type: str


class ClearedOut(BaseModel):
    deleted: int
