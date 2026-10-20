"""The catalogue the feed ranks, held in memory.

WHY IN MEMORY
-------------
5,000 garments x 128 numbers is about 2.6 MB. Loading it once at startup means
a feed request needs no product lookups at all: ranking is one numpy operation
and every card's details are already at hand.

WHY ROW ORDER IS EVERYTHING
---------------------------
products[i] and vectors[i] must describe the same garment. They are built in
one place from one ordering, and positions are looked up through position() —
never by assuming two lists happen to line up.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from app.core.supabase_client import get_service_client
from ml.paging import fetch_all_pages

logger = logging.getLogger(__name__)

PRODUCT_COLUMNS = (
    "id, name, brand, price, currency, image_url, category, product_code, "
    "popularity, attributes"
)


class CatalogError(RuntimeError):
    """The data in Supabase cannot be turned into a usable catalogue."""


@dataclass(frozen=True)
class Product:
    """What a card needs to show one garment."""

    id: str
    name: str
    brand: str | None
    price: float | None
    currency: str
    image_url: str | None
    category: str | None
    product_code: str | None
    popularity: int
    colour: str | None


@dataclass(frozen=True)
class Catalog:
    products: list[Product]
    vectors: np.ndarray  # shape (n, factors); row i belongs to products[i]
    model_version: str
    unit: np.ndarray = field(init=False, repr=False)  # rows scaled to length 1
    groups: list[str | None] = field(init=False, repr=False)  # product_code per row
    popularity: np.ndarray = field(init=False, repr=False)
    _positions: dict[str, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if len(self.products) != len(self.vectors):
            raise CatalogError("products and vectors must have one row each")
        norms = np.linalg.norm(self.vectors, axis=1, keepdims=True)
        # frozen=True blocks normal assignment; object.__setattr__ is the
        # standard way to fill derived fields once, at construction.
        object.__setattr__(self, "unit", self.vectors / np.where(norms == 0, 1.0, norms))
        object.__setattr__(self, "groups", [p.product_code for p in self.products])
        object.__setattr__(
            self, "popularity", np.array([p.popularity for p in self.products], dtype=float)
        )
        object.__setattr__(
            self, "_positions", {p.id: i for i, p in enumerate(self.products)}
        )

    def __len__(self) -> int:
        return len(self.products)

    def position(self, product_id: str) -> int | None:
        return self._positions.get(product_id)

    def product(self, product_id: str) -> Product | None:
        position = self.position(product_id)
        return None if position is None else self.products[position]


def _product(row: dict) -> Product:
    attributes = row.get("attributes") or {}
    price = row.get("price")
    return Product(
        id=row["id"],
        name=row["name"],
        brand=row.get("brand"),
        price=None if price is None else float(price),
        currency=row.get("currency") or "GBP",
        image_url=row.get("image_url"),
        category=row.get("category"),
        product_code=row.get("product_code"),
        popularity=int(row.get("popularity") or 0),
        colour=attributes.get("colour"),
    )


def build_catalog(product_rows: list[dict], vector_rows: list[dict]) -> Catalog:
    """Pair every product with its vector. Pure: rows in, Catalog out."""
    if not vector_rows:
        raise CatalogError("product_vectors is empty — run scripts.train_model first")
    versions = {row["model_version"] for row in vector_rows}
    if len(versions) != 1:
        raise CatalogError(
            f"product_vectors mixes model versions {sorted(versions)}; "
            "vectors from different runs cannot be compared"
        )
    widths = {len(row["vector"]) for row in vector_rows}
    if len(widths) != 1:
        raise CatalogError(f"vectors have different widths {sorted(widths)}")

    vector_by_product = {row["product_id"]: row["vector"] for row in vector_rows}
    products: list[Product] = []
    vectors: list[list[float]] = []
    for row in sorted(product_rows, key=lambda r: r["id"]):
        vector = vector_by_product.get(row["id"])
        if vector is None:
            continue
        products.append(_product(row))
        vectors.append(vector)

    if not products:
        raise CatalogError("no product has a vector")
    skipped = len(product_rows) - len(products)
    if skipped:
        logger.warning("%d products have no vector and are left out of the feed", skipped)
    return Catalog(
        products=products,
        vectors=np.asarray(vectors, dtype=np.float32),
        model_version=versions.pop(),
    )


def load_catalog(client) -> Catalog:
    """Download every product and vector, page by page, and build the catalogue."""
    products = fetch_all_pages(
        lambda start, end: client.table("products")
        .select(PRODUCT_COLUMNS)
        .order("id")
        .range(start, end)
        .execute()
        .data
    )
    vectors = fetch_all_pages(
        lambda start, end: client.table("product_vectors")
        .select("product_id, vector, model_version")
        .order("product_id")
        .range(start, end)
        .execute()
        .data
    )
    catalog = build_catalog(products, vectors)
    logger.info("catalogue loaded: %d products, %s", len(catalog), catalog.model_version)
    return catalog


class CatalogState:
    """Holds the one in-memory catalogue, loading it when it is missing.

    A failed load at startup (Supabase paused, credentials missing) must not
    stop the server booting — /health has to keep answering. Instead, the next
    request that needs the catalogue tries again, at most once every
    `retry_seconds`, so an outage does not turn every request into a
    5,000-row download attempt.
    """

    def __init__(
        self,
        loader: Callable[[], Catalog],
        retry_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._loader = loader
        self._retry_seconds = retry_seconds
        self._clock = clock
        self._catalog: Catalog | None = None
        self._last_attempt: float | None = None
        # FastAPI runs plain `def` endpoints on several threads at once; the
        # lock stops two of them downloading the catalogue simultaneously.
        self._lock = threading.Lock()

    def get(self) -> Catalog | None:
        if self._catalog is not None:
            return self._catalog
        with self._lock:
            if self._catalog is not None:
                return self._catalog
            now = self._clock()
            if self._last_attempt is not None and now - self._last_attempt < self._retry_seconds:
                return None
            self._last_attempt = now
            try:
                self._catalog = self._loader()
            except Exception:  # noqa: BLE001 — any failure means "not loaded yet"
                logger.exception(
                    "could not load the catalogue; retrying in %.0fs", self._retry_seconds
                )
            return self._catalog

    def set(self, catalog: Catalog | None) -> None:
        """Install a catalogue directly (tests) or clear it."""
        with self._lock:
            self._catalog = catalog
            self._last_attempt = None


catalog_state = CatalogState(lambda: load_catalog(get_service_client()))
