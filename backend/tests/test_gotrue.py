"""The three Supabase Auth calls made as the signed-in user.

Nothing here touches the network: `_send` (the one function that does) is
replaced with a fake that records the request and returns a canned answer.
"""

from types import SimpleNamespace

import httpx
import pytest

from app.core import gotrue
from app.core.config import Settings


@pytest.fixture
def sent(monkeypatch):
    """Record every request; answer with whatever the test passes to `reply`."""
    calls = []
    state = {"reply": httpx.Response(200, json={})}

    def fake_send(method, url, headers, body):
        calls.append({"method": method, "url": url, "headers": headers, "body": body})
        return state["reply"]

    monkeypatch.setattr(gotrue, "_send", fake_send)
    monkeypatch.setattr(
        gotrue,
        "get_settings",
        lambda: Settings(SUPABASE_URL="https://proj.supabase.co/", SUPABASE_ANON_KEY="anon-key"),
    )
    return SimpleNamespace(calls=calls, reply=lambda response: state.update(reply=response))


def test_an_email_change_is_requested_as_the_user(sent):
    gotrue.request_email_change("user-token", "a@example.com")

    [call] = sent.calls
    assert (call["method"], call["url"]) == ("PUT", "https://proj.supabase.co/auth/v1/user")
    assert call["headers"] == {"apikey": "anon-key", "Authorization": "Bearer user-token"}
    assert call["body"] == {"email": "a@example.com"}


def test_the_code_is_checked_as_an_email_change(sent):
    sent.reply(httpx.Response(200, json={"access_token": "a", "user": {"id": "u"}}))

    session = gotrue.verify_email_change("a@example.com", "123456")

    [call] = sent.calls
    assert (call["method"], call["url"]) == ("POST", "https://proj.supabase.co/auth/v1/verify")
    assert call["body"] == {"type": "email_change", "email": "a@example.com", "token": "123456"}
    assert session == {"access_token": "a", "user": {"id": "u"}}


def test_the_password_is_set_as_the_user(sent):
    gotrue.set_password("user-token", "correct-horse-battery")

    [call] = sent.calls
    assert call["headers"]["Authorization"] == "Bearer user-token"
    assert call["body"] == {"password": "correct-horse-battery"}


def test_a_refusal_becomes_a_gotrue_error_with_its_code(sent):
    sent.reply(
        httpx.Response(422, json={"code": 422, "error_code": "email_exists", "msg": "already registered"})
    )

    with pytest.raises(gotrue.GoTrueError) as caught:
        gotrue.request_email_change("t", "a@example.com")

    assert (caught.value.status, caught.value.code, caught.value.message) == (
        422,
        "email_exists",
        "already registered",
    )


def test_a_refusal_that_is_not_json_is_still_a_gotrue_error(sent):
    sent.reply(httpx.Response(502, text="<html>Bad gateway</html>"))

    with pytest.raises(gotrue.GoTrueError) as caught:
        gotrue.set_password("t", "correct-horse-battery")

    assert caught.value.status == 502
    assert caught.value.code is None


def test_a_network_failure_is_not_disguised(monkeypatch, sent):
    def unreachable(*args):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(gotrue, "_send", unreachable)

    with pytest.raises(httpx.ConnectError):
        gotrue.request_email_change("t", "a@example.com")


def test_unconfigured_supabase_is_a_runtime_error(monkeypatch, sent):
    monkeypatch.setattr(gotrue, "get_settings", lambda: Settings(SUPABASE_URL="", SUPABASE_ANON_KEY=""))

    with pytest.raises(RuntimeError):
        gotrue.request_email_change("t", "a@example.com")
