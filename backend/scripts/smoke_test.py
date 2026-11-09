"""Check a deployed API end to end, as a first-time visitor would use it.

    cd backend
    python -m scripts.smoke_test --base-url https://<your-app>.up.railway.app

Creates one guest account, fetches a feed, likes three garments, checks the
feed personalises and the wardrobe fills, removes one garment from the
wardrobe, then clears its swipes. Each run leaves one empty guest account
behind in Supabase. Uses only the standard library, so it runs anywhere.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


def call(base: str, method: str, path: str, token: str | None = None, body: dict | None = None):
    request = urllib.request.Request(
        base.rstrip("/") + path,
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}
        | ({"Authorization": f"Bearer {token}"} if token else {}),
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        # Show what the server said, not just "HTTP Error 503".
        detail = exc.read().decode(errors="replace")
        raise SystemExit(f"{method} {path} failed with {exc.code}: {detail}") from None
    took = (time.perf_counter() - started) * 1000
    print(f"{method:6} {path:44} {status}  {took:6.0f} ms")
    return json.loads(raw) if raw else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    base = parser.parse_args().base_url

    assert call(base, "GET", "/health")["status"] == "ok"
    ready = call(base, "GET", "/health/ready")
    assert ready["catalog_loaded"] and ready["products"] == 5000, ready

    guest = call(base, "POST", "/v1/auth/anonymous")
    token = guest["session"]["access_token"]
    assert call(base, "GET", "/v1/auth/me", token)["is_anonymous"] is True

    first = call(base, "GET", "/v1/feed", token)
    assert len(first["items"]) == 10 and not first["personalised"]

    liked = [item["product"]["id"] for item in first["items"][:3]]
    for product_id in liked:
        call(base, "POST", "/v1/interactions", token, {"product_id": product_id, "type": "like"})

    second = call(base, "GET", "/v1/feed", token)
    assert second["personalised"], "three likes should personalise the feed"
    assert not {i["product"]["id"] for i in second["items"]} & set(liked)
    assert call(base, "GET", "/v1/wardrobe", token)["count"] == 3

    call(base, "DELETE", f"/v1/wardrobe/{liked[0]}", token)
    assert call(base, "GET", "/v1/wardrobe", token)["count"] == 2
    assert call(base, "GET", "/v1/feed?limit=3", token)["likes"] == 3  # removed, still a like

    # 3 likes + 1 remove
    assert call(base, "DELETE", "/v1/interactions", token)["deleted"] == 4
    print("\nall checks passed")


if __name__ == "__main__":
    main()
