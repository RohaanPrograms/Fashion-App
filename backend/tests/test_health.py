"""Health checks must distinguish "the process is up" from "the app can work".

The bug these tests exist to prevent: /health reported
    {"status":"ok", "supabase_configured": true}
while Supabase was completely unreachable. `supabase_configured` only checked
that two environment variable strings were non-empty, so a monitor watching
this endpoint would have shown green through a total outage.

Two endpoints, two jobs — this is the standard split:
  - /health        liveness  — "is the process alive?"  Never calls outward.
  - /health/ready  readiness — "can it actually serve?"  Really calls Supabase.

Liveness stays dependency-free on purpose: if it went red during a Supabase
outage, a host platform would kill and restart a process that was working fine.
"""


def test_health_is_liveness_only_and_never_calls_supabase(client, failing_supabase):
    """Even with Supabase hard down, liveness stays 200."""
    failing_supabase(OSError("[Errno 11001] getaddrinfo failed"))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_reports_503_when_supabase_is_unreachable(client, supabase_data):
    supabase_data(OSError("[Errno 11001] getaddrinfo failed"))

    response = client.get("/health/ready")

    assert response.status_code == 503, (
        "readiness must go red when the database it depends on is unreachable"
    )
    assert response.json()["detail"]["supabase_reachable"] is False


def test_readiness_reports_200_when_supabase_answers(client, supabase_data):
    supabase_data(None)  # healthy round trip

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["supabase_reachable"] is True


def test_health_does_not_claim_reachability_it_has_not_checked(client, failing_supabase):
    """`supabase_configured` must not be mistakable for `supabase_reachable`.

    Liveness may report that credentials are *present*, but it must never
    publish a field asserting the service is reachable, because it does not
    look. That conflation was the original defect.
    """
    failing_supabase(OSError("down"))

    body = client.get("/health").json()

    assert "supabase_reachable" not in body
