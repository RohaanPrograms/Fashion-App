"""Error answers must reach the web app.

The web app and the API live at different addresses, so a browser only lets
the app read an answer that carries CORS headers ("Access-Control-Allow-
Origin"). An error answer without them is thrown away by the browser, and the
app can only say "couldn't reach the server", which is wrong when the server
did answer, e.g. a 503 because Supabase dropped a connection.
"""

import httpx

from app.db.interactions import get_interaction_store
from app.main import app

ORIGIN = "http://localhost:8081"


class _DroppedConnectionStore:
    """Every database call fails the way a dropped Supabase connection does."""

    def history_rows(self, user_id):
        raise httpx.WriteError("[WinError 10054] An existing connection was forcibly closed")

    def add(self, *args, **kwargs):
        raise httpx.WriteError("[WinError 10054] An existing connection was forcibly closed")


def test_an_outage_is_a_503_the_browser_can_read(api):
    app.dependency_overrides[get_interaction_store] = lambda: _DroppedConnectionStore()

    response = api.client.get("/v1/wardrobe", headers={"Origin": ORIGIN})

    assert response.status_code == 503
    assert response.json() == {"detail": "The service is temporarily unavailable. Please try again shortly."}
    assert response.headers.get("access-control-allow-origin") in (ORIGIN, "*")


def test_a_failed_swipe_is_a_503_the_browser_can_read(api, ids):
    app.dependency_overrides[get_interaction_store] = lambda: _DroppedConnectionStore()

    response = api.client.post(
        "/v1/interactions",
        json={"product_id": ids["jeans"], "type": "like"},
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 503
    assert response.headers.get("access-control-allow-origin") in (ORIGIN, "*")


def test_a_bug_is_a_500_the_browser_can_read(api, monkeypatch):
    """Not an outage: a plain bug. Still JSON, still readable, no stack trace."""

    class _Broken:
        def history_rows(self, user_id):
            raise KeyError("product_id")

    app.dependency_overrides[get_interaction_store] = lambda: _Broken()

    response = api.client.get("/v1/wardrobe", headers={"Origin": ORIGIN})

    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong on our side."}
    assert response.headers.get("access-control-allow-origin") in (ORIGIN, "*")
