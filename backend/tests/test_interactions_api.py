import httpx

from app.db.interactions import get_interaction_store
from app.main import app
from conftest import USER_A, USER_B


def test_a_like_is_recorded_for_the_signed_in_user(api, ids):
    response = api.client.post(
        "/v1/interactions", json={"product_id": ids["jeans"], "type": "like", "dwell_time_ms": 1500}
    )

    assert response.status_code == 201
    assert response.json() == {"product_id": ids["jeans"], "type": "like"}
    (row,) = api.interactions.rows
    assert row["user_id"] == USER_A and row["product_id"] == ids["jeans"]
    assert row["type"] == "like" and row["source"] == "feed" and row["dwell_time_ms"] == 1500


def test_an_unknown_product_is_404_and_nothing_is_saved(api):
    response = api.client.post(
        "/v1/interactions",
        json={"product_id": "99999999-0000-4000-8000-000000000000", "type": "like"},
    )

    assert response.status_code == 404
    assert api.interactions.rows == []


def test_only_like_and_dislike_are_accepted(api, ids):
    response = api.client.post("/v1/interactions", json={"product_id": ids["jeans"], "type": "superlike"})

    assert response.status_code == 422


def test_dwell_time_over_a_minute_is_rejected(api, ids):
    response = api.client.post(
        "/v1/interactions", json={"product_id": ids["jeans"], "type": "like", "dwell_time_ms": 70_000}
    )

    assert response.status_code == 422


def test_swiping_requires_signing_in(api, ids):
    from app.api.deps import get_current_user

    del app.dependency_overrides[get_current_user]

    response = api.client.post("/v1/interactions", json={"product_id": ids["jeans"], "type": "like"})

    assert response.status_code in (401, 403)


def test_start_over_deletes_only_my_swipes(api, ids):
    api.client.post("/v1/interactions", json={"product_id": ids["jeans"], "type": "like"})
    api.sign_in_as(USER_B)
    api.client.post("/v1/interactions", json={"product_id": ids["dress"], "type": "like"})
    api.sign_in_as(USER_A)

    response = api.client.delete("/v1/interactions")

    assert response.status_code == 200 and response.json() == {"deleted": 1}
    assert [r["user_id"] for r in api.interactions.rows] == [USER_B]


def test_a_supabase_outage_is_503_not_500(api, ids):
    class DownStore:
        def add(self, *args, **kwargs):
            raise httpx.ConnectError("connection refused")

    app.dependency_overrides[get_interaction_store] = lambda: DownStore()

    response = api.client.post("/v1/interactions", json={"product_id": ids["jeans"], "type": "like"})

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]


def test_without_the_catalogue_swipes_are_503(api, ids):
    from app.recs.catalog import catalog_state

    catalog_state.set(None)

    response = api.client.post("/v1/interactions", json={"product_id": ids["jeans"], "type": "like"})

    assert response.status_code == 503
