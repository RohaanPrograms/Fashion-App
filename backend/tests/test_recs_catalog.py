import numpy as np
import pytest

from app.recs.catalog import CatalogError, CatalogState, build_catalog, load_catalog
from conftest import RecordingClient, product_row


def _vector_row(product_id, vector, version="als-2f-v1"):
    return {"product_id": product_id, "vector": vector, "model_version": version}


def _rows(n):
    products = [product_row(f"p{i:03d}", f"item{i}", "Shoes", f"C{i}", i, 9.99) for i in range(n)]
    vectors = [_vector_row(f"p{i:03d}", [float(i), 1.0]) for i in range(n)]
    return products, vectors


def test_each_vector_stays_with_its_own_product_whatever_order_rows_arrive_in():
    """The failure this guards against is silent: vectors attached to the
    wrong garments still rank something, just the wrong things."""
    products, vectors = _rows(6)
    rng = np.random.default_rng(0)

    catalog = build_catalog(
        [products[i] for i in rng.permutation(6)], [vectors[i] for i in rng.permutation(6)]
    )

    for i in range(6):
        position = catalog.position(f"p{i:03d}")
        assert catalog.vectors[position].tolist() == [float(i), 1.0]
        assert catalog.products[position].id == f"p{i:03d}"


def test_products_without_a_vector_are_left_out():
    products, vectors = _rows(3)

    catalog = build_catalog(products, vectors[:2])

    assert len(catalog) == 2
    assert catalog.position("p002") is None


def test_mixed_model_versions_are_refused():
    products, vectors = _rows(2)
    vectors[1]["model_version"] = "als-64f-v1"

    with pytest.raises(CatalogError, match="model version"):
        build_catalog(products, vectors)


def test_no_vectors_at_all_is_refused():
    products, _ = _rows(2)

    with pytest.raises(CatalogError, match="empty"):
        build_catalog(products, [])


def test_vectors_of_different_widths_are_refused():
    products, vectors = _rows(2)
    vectors[1]["vector"] = [1.0, 2.0, 3.0]

    with pytest.raises(CatalogError, match="width"):
        build_catalog(products, vectors)


def test_unit_rows_have_length_one():
    products, vectors = _rows(4)

    catalog = build_catalog(products, vectors)

    assert np.allclose(np.linalg.norm(catalog.unit, axis=1), 1.0)


def test_product_fields_are_parsed_for_the_cards():
    row = product_row("p1", "Jade jeans", "Garment Lower body", "B1", 7, "41.27")
    row["attributes"] = {"colour": "Dark Blue"}
    row["popularity"] = None

    catalog = build_catalog([row], [_vector_row("p1", [1.0, 0.0])])
    product = catalog.product("p1")

    assert product.price == 41.27  # Postgres numeric can arrive as a string
    assert product.colour == "Dark Blue"
    assert product.popularity == 0
    assert catalog.groups == ["B1"]


def test_loading_reads_past_supabase_s_1000_row_limit():
    products, vectors = _rows(2345)
    client = RecordingClient({"products": products, "product_vectors": vectors})

    catalog = load_catalog(client)

    assert len(catalog) == 2345
    assert catalog.model_version == "als-2f-v1"


def test_a_loaded_catalogue_is_reused_without_reloading():
    calls = []
    products, vectors = _rows(2)
    state = CatalogState(lambda: calls.append(1) or build_catalog(products, vectors))

    first, second = state.get(), state.get()

    assert first is second
    assert len(calls) == 1


def test_a_failed_load_does_not_raise_and_is_retried_only_after_the_wait():
    now = [100.0]
    attempts = []

    def loader():
        attempts.append(now[0])
        raise RuntimeError("Supabase is paused")

    state = CatalogState(loader, retry_seconds=30, clock=lambda: now[0])

    assert state.get() is None
    now[0] = 110.0
    assert state.get() is None  # too soon: no second download attempt
    now[0] = 131.0
    assert state.get() is None

    assert attempts == [100.0, 131.0]
