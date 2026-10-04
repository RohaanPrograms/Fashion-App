from ml.catalog import PRICE_BANDS, build_product_row, image_url, price_for


def _record(**overrides) -> dict:
    record = {
        "article_id": "0706016001",
        "product_code": "0706016",
        "prod_name": "Jade HW Skinny Denim TRS",
        "product_group_name": "Garment Lower body",
        "colour_group_name": "Black",
        "garment_group_name": "Trousers",
        "department_name": "Trousers",
        "graphical_appearance_name": "Solid",
        "popularity": 10903,
    }
    record.update(overrides)
    return record


def test_price_is_stable_across_calls():
    """Re-running the loader must not reshuffle every price in the catalog."""
    assert price_for("0706016001", "Shoes") == price_for("0706016001", "Shoes")


def test_price_stays_inside_its_category_band():
    for category, (low, high) in PRICE_BANDS.items():
        for n in range(200):
            price = price_for(f"{n:010d}", category)
            assert low <= price <= high
            assert price == round(price, 2)


def test_unknown_category_uses_the_default_band():
    for n in range(200):
        assert 10 <= price_for(f"{n:010d}", "Something new") <= 50


def test_image_url_points_at_the_public_bucket_object():
    assert image_url("https://abc.supabase.co", "product-images", "0706016001") == (
        "https://abc.supabase.co/storage/v1/object/public/product-images/0706016001.webp"
    )


def test_builds_a_row_matching_the_products_table():
    row = build_product_row(_record(), "https://abc.supabase.co", "product-images")

    assert row["source"] == "hm"
    assert row["source_id"] == "0706016001"
    assert row["name"] == "Jade HW Skinny Denim TRS"
    assert row["product_code"] == "0706016"
    assert row["popularity"] == 10903
    assert row["category"] == "Garment Lower body"
    assert row["image_url"].endswith("/product-images/0706016001.webp")
    assert row["url"] == "https://www2.hm.com/en_gb/productpage.0706016001.html"
    assert row["attributes"]["colour"] == "Black"
    # The database client sends JSON; numpy integers are not JSON-serialisable.
    assert type(row["popularity"]) is int


def test_missing_name_falls_back_to_the_article_id():
    """pandas reads an empty cell as NaN, which is truthy, so `or` alone is not enough."""
    row = build_product_row(
        _record(prod_name=float("nan")), "https://abc.supabase.co", "product-images"
    )
    assert row["name"] == "Article 0706016001"
