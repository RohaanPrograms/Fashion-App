"""Shared test fixtures.

`conftest.py` is a file pytest loads automatically before running tests in this
folder. Anything defined here (a "fixture" — a reusable piece of test setup) can
be requested by any test simply by naming it as an argument.

Nothing in here touches the real Supabase project. Every test that needs
Supabase to fail — or succeed — installs a stand-in client, so the suite runs
identically on your laptop and in CI, with or without a network connection.
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """A test client that calls the real app in-process.

    raise_server_exceptions=False makes an unhandled crash come back as a 500
    response instead of blowing up the test, which is what we want when the
    thing under test IS the error handling.
    """
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def deterministic_auth_config(monkeypatch):
    """Stop the suite from reading whatever backend/.env happens to exist.

    Whether a token is verified locally or over the network depends on
    SUPABASE_JWT_SECRET. Without this fixture that answer comes from the real
    .env on the machine running the tests, so the same commit passes on one
    laptop and fails on another. That is not hypothetical: four tests here went
    red the moment a valid secret was pasted into .env, with no code change.

    Default is "no secret configured", so tests exercise the network path.
    Tests that want local verification opt in explicitly via auth_settings.
    """
    from app.core import security
    from app.core.config import Settings

    neutral = Settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_ANON_KEY="",
        SUPABASE_JWT_SECRET="",
    )
    for target in ("app.core.security.get_settings", "app.api.deps.get_settings"):
        monkeypatch.setattr(target, lambda: neutral, raising=False)
    security.uses_local_verification.cache_clear()

    yield

    security.uses_local_verification.cache_clear()


class _StubAuth:
    """Stands in for `client.auth`, raising a chosen error from every method."""

    def __init__(self, exc: Exception):
        self._exc = exc

    def sign_up(self, *args, **kwargs):
        raise self._exc

    def sign_in_with_password(self, *args, **kwargs):
        raise self._exc

    def refresh_session(self, *args, **kwargs):
        raise self._exc

    def get_user(self, *args, **kwargs):
        raise self._exc


class _StubClient:
    def __init__(self, exc: Exception):
        self.auth = _StubAuth(exc)


@pytest.fixture
def failing_supabase(monkeypatch):
    """Make every Supabase auth call raise the error you pass in.

    Usage:
        failing_supabase(httpx.ConnectError("boom"))

    monkeypatch is pytest's built-in tool for temporarily replacing something;
    it puts the original back automatically when the test finishes.
    """

    def _install(exc: Exception):
        stub = _StubClient(exc)
        # Patch where the name is *used*, not where it is defined — the auth
        # module and the deps module each imported it into their own namespace.
        monkeypatch.setattr("app.api.v1.auth.get_anon_client", lambda: stub)
        monkeypatch.setattr("app.api.deps.get_anon_client", lambda: stub)
        return stub

    return _install


@pytest.fixture
def auth_settings(monkeypatch):
    """Point the token code at a throwaway JWT secret of our own.

    Tests never use the real project secret. We mint a secret here, sign an
    "anon key" with it, and hand both to the code under test — so the suite
    proves the logic, not the contents of anyone's .env file.

    Pass jwt_secret="" to simulate the secret not being configured, or a
    different secret than the one signing the anon key to simulate the wrong
    value being pasted in.
    """
    import jwt as pyjwt

    from app.core.config import Settings

    def _install(jwt_secret: str, anon_signed_with: str | None = None):
        signer = anon_signed_with if anon_signed_with is not None else jwt_secret
        anon_key = (
            pyjwt.encode({"iss": "supabase", "role": "anon"}, signer, algorithm="HS256")
            if signer
            else ""
        )
        stub = Settings(
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_ANON_KEY=anon_key,
            SUPABASE_JWT_SECRET=jwt_secret,
        )
        for target in (
            "app.core.security.get_settings",
            "app.api.deps.get_settings",
        ):
            monkeypatch.setattr(target, lambda: stub, raising=False)
        # The "does this secret match the project" answer is cached; clear it
        # so each test starts from a clean slate.
        from app.core import security

        security.uses_local_verification.cache_clear()
        return stub

    yield _install

    from app.core import security

    security.uses_local_verification.cache_clear()


@pytest.fixture
def no_network(monkeypatch):
    """Make ANY call to Supabase an immediate test failure.

    Used to prove local verification really is local: if the code falls back to
    the network, the test fails loudly instead of quietly passing.
    """

    def _boom():
        raise AssertionError("Supabase was called — token verification was not local")

    monkeypatch.setattr("app.api.deps.get_anon_client", _boom)
    return _boom


class _StubQuery:
    """Minimal stand-in for the Supabase query builder chain."""

    def __init__(self, exc: Exception | None):
        self._exc = exc

    def select(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        if self._exc:
            raise self._exc
        return {"data": []}


class _StubDataClient:
    def __init__(self, exc: Exception | None):
        self._exc = exc

    def table(self, *args, **kwargs):
        return _StubQuery(self._exc)


@pytest.fixture
def supabase_data(monkeypatch):
    """Control whether a data query to Supabase succeeds or fails.

    Pass an exception to simulate the project being unreachable, or None to
    simulate a healthy round trip.
    """

    def _install(exc: Exception | None):
        stub = _StubDataClient(exc)
        monkeypatch.setattr("app.main.get_service_client", lambda: stub)
        return stub

    return _install


@pytest.fixture
def item_vectors() -> np.ndarray:
    """Four items in 2-D, hand-placed so similarity results are obvious.

    Items 0 and 1 point almost the same way ("casual"); items 2 and 3 point
    almost the same way ("dressy"); the two groups are orthogonal.
    """
    return np.array(
        [
            [1.0, 0.0],   # 0 — casual
            [0.9, 0.1],   # 1 — casual
            [0.0, 1.0],   # 2 — dressy
            [0.1, 0.9],   # 3 — dressy
        ]
    )


@pytest.fixture
def product_groups() -> list[str]:
    """Colourway grouping for the four fixture items: 0 and 1 are the same
    garment in two colours."""
    return ["A", "A", "B", "C"]
