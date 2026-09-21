"""The Vobiz voice channel.

The signature tests matter most. Vobiz signs the URL and a nonce, never the body,
so a scheme that hashes the payload will verify nothing — and the documentation
warns that callbacks arrive with no signature headers at all when credentials are
not configured on the URL. Both of those are ways to end up accepting anything,
on an endpoint whose job is to inject citizen reports into a scored output.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

import api.main as main
from api.channels import vobiz

TOKEN = "vobiz-test-token"
BASE = "https://civos-api.example.run.app"


@pytest.fixture
def cfg(monkeypatch):
    monkeypatch.setenv("VOBIZ_AUTH_ID", "MATEST123")
    monkeypatch.setenv("VOBIZ_AUTH_TOKEN", TOKEN)
    monkeypatch.setenv("CIVOS_PUBLIC_BASE_URL", BASE)
    monkeypatch.setenv("CIVOS_SUBMITTER_SALT", "salt")
    return TestClient(main.app)


def _v3(path: str, nonce: str = "11111111112222222222") -> dict[str, str]:
    msg = f"{BASE}{path}.{nonce}".encode()
    sig = base64.b64encode(hmac.new(TOKEN.encode(), msg, hashlib.sha256).digest()).decode()
    return {
        "X-Vobiz-Signature-V3": sig,
        "X-Vobiz-Signature-V3-Nonce": nonce,
        "content-type": "application/x-www-form-urlencoded",
    }


def _v2(path: str, nonce: str = "33333333334444444444") -> dict[str, str]:
    msg = f"{BASE}{path}{nonce}".encode()
    sig = base64.b64encode(hmac.new(TOKEN.encode(), msg, hashlib.sha256).digest()).decode()
    return {
        "X-Vobiz-Signature-V2": sig,
        "X-Vobiz-Signature-V2-Nonce": nonce,
        "content-type": "application/x-www-form-urlencoded",
    }


# ── signatures ──────────────────────────────────────────────────────────────


def test_v3_signature_matches_the_documented_construction(cfg):
    """base64(HMAC-SHA256(auth_token, base_url + "." + nonce))."""
    path = "/channel/voice/answer"
    body = urlencode({"CallUUID": "abc", "From": "+919812345678", "To": "+918065354620"}).encode()
    r = cfg.post(path, content=body, headers=_v3(path))
    assert r.status_code == 200


def test_v2_signature_is_accepted_too(cfg):
    """Same construction without the separator, for accounts still emitting V2."""
    path = "/channel/voice/answer"
    r = cfg.post(path, content=b"CallUUID=abc", headers=_v2(path))
    assert r.status_code == 200


def test_an_unsigned_callback_is_refused(cfg):
    r = cfg.post("/channel/voice/answer", data={"CallUUID": "abc"})
    assert r.status_code == 403


def test_a_signature_for_a_different_path_is_refused(cfg):
    """The URL is the signed material, so a valid signature is path-specific."""
    r = cfg.post(
        "/channel/voice/answer", content=b"CallUUID=abc",
        headers=_v3("/channel/voice/recording"),
    )
    assert r.status_code == 403


def test_a_tampered_nonce_is_refused(cfg):
    h = _v3("/channel/voice/answer")
    h["X-Vobiz-Signature-V3-Nonce"] = "99999999999999999999"
    r = cfg.post("/channel/voice/answer", content=b"CallUUID=abc", headers=h)
    assert r.status_code == 403


def test_legacy_v1_sha1_is_not_accepted(cfg):
    """V1 is HMAC-SHA1 and exists for backwards compatibility we do not have."""
    path = "/channel/voice/answer"
    sig = base64.b64encode(hmac.new(TOKEN.encode(), f"{BASE}{path}".encode(), hashlib.sha1).digest()).decode()
    r = cfg.post(path, content=b"CallUUID=abc", headers={"X-Vobiz-Signature": sig})
    assert r.status_code == 403


def test_unconfigured_refuses_rather_than_falling_open(monkeypatch):
    """A missing signature and a missing configuration look identical from here."""
    for var in ("VOBIZ_AUTH_ID", "VOBIZ_AUTH_TOKEN", "CIVOS_PUBLIC_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    c = TestClient(main.app)
    assert c.post("/channel/voice/answer", data={"CallUUID": "x"}).status_code == 503


# ── the call flow ───────────────────────────────────────────────────────────


def test_answer_returns_voice_xml_not_json(cfg):
    """The return value IS the call flow. JSON here is a call that drops."""
    path = "/channel/voice/answer"
    r = cfg.post(path, content=b"CallUUID=abc", headers=_v3(path))
    assert r.headers["content-type"].startswith("application/xml")
    xml = r.text
    assert xml.startswith('<?xml version="1.0"')
    assert "<Response>" in xml and "</Response>" in xml
    assert "<Record " in xml and "<Hangup/>" in xml


def test_the_prompt_asks_for_the_district(cfg):
    """Placing the report depends on it, and an SMS-less voice call has no picker."""
    path = "/channel/voice/answer"
    xml = cfg.post(path, content=b"CallUUID=abc", headers=_v3(path)).text
    assert "district" in xml.lower()
    assert 'language="hi-IN"' in xml and 'language="en-IN"' in xml


def test_record_points_back_at_this_service_and_does_not_redirect(cfg):
    path = "/channel/voice/answer"
    xml = cfg.post(path, content=b"CallUUID=abc", headers=_v3(path)).text
    assert f'callbackUrl="{BASE}/channel/voice/recording"' in xml
    # redirect="false" means the action handler must return an empty Response, or
    # it interrupts a call that has already moved on.
    assert 'redirect="false"' in xml
    assert 'playBeep="true"' in xml


def test_the_action_request_carries_no_file_and_is_answered_with_silence(cfg):
    """Record fires `action` near the start, before any file exists."""
    path = "/channel/voice/recording"
    r = cfg.post(path, content=urlencode({"RecordingID": "r1"}).encode(), headers=_v3(path))
    assert r.status_code == 200
    assert r.text.strip().endswith("<Response></Response>")


def test_a_processing_failure_still_returns_valid_xml(cfg, monkeypatch):
    """A crash mid-extraction must not leave the operator without a response."""
    async def boom(*a, **k):
        raise RuntimeError("gemini is down")

    monkeypatch.setattr(vobiz, "fetch_recording", boom)
    path = "/channel/voice/recording"
    body = urlencode({"Event": "RecordStop", "RecordUrl": "https://api.vobiz.ai/x.mp3",
                      "From": "+919812345678"}).encode()
    r = cfg.post(path, content=body, headers=_v3(path))
    assert r.status_code == 200
    assert "<Response>" in r.text


# ── the account token must not leak ─────────────────────────────────────────


def test_credentials_are_sent_only_to_a_vobiz_host(cfg, monkeypatch):
    """A webhook field naming another host must not be handed the account token."""
    seen: dict = {}

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        async def aiter_bytes(self):
            yield b"audio"

    class FakeStream:
        def __init__(self, headers): seen.update(headers or {})
        async def __aenter__(self): return FakeResp()
        async def __aexit__(self, *a): return False

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        def stream(self, method, url, headers=None): return FakeStream(headers)

    monkeypatch.setattr(vobiz.httpx, "AsyncClient", FakeClient)
    import anyio

    seen.clear()
    anyio.run(vobiz.fetch_recording, "https://evil.example.com/x.mp3", 1_000_000)
    assert "X-Auth-Token" not in seen

    seen.clear()
    anyio.run(vobiz.fetch_recording, "https://api.vobiz.ai/x.mp3", 1_000_000)
    assert seen.get("X-Auth-Token") == TOKEN


# ── status ──────────────────────────────────────────────────────────────────


def test_status_reports_the_number_only_when_it_could_work(cfg, monkeypatch):
    async def owned(_e164):
        return True

    monkeypatch.setattr(vobiz, "owns_number", owned)
    j = cfg.get("/channel/status").json()
    assert j["voice"]["provider"] == "vobiz"
    assert j["voice"]["ready"] is True
    assert j["voice"]["number"] == "+918065354620"
    assert j["voice"]["answer_url"] == f"{BASE}/channel/voice/answer"


def test_credentials_alone_do_not_make_a_number_dialable(cfg, monkeypatch):
    """The failure this guard exists for, found in production.

    A trial account holding a shared number looks identical from inside this
    service: credentials present, answer URL configured, everything green — and
    a caller hears nothing, because the operator does not route that number to
    us. The site was advertising it. Ownership is now asked of the operator.
    """

    async def not_owned(_e164):
        return False

    monkeypatch.setattr(vobiz, "owns_number", not_owned)
    j = cfg.get("/channel/status").json()["voice"]
    assert j["credentials_configured"] is True
    assert j["number_on_account"] is False
    assert j["ready"] is False
    assert j["number"] is None
    assert "not held by this operator account" in j["note"]


def test_an_unreachable_operator_is_not_a_yes(cfg, monkeypatch):
    """Any failure in the check must answer no, never default to advertising."""

    class Boom:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, *a, **k): raise RuntimeError("operator down")

    monkeypatch.setattr(vobiz.httpx, "AsyncClient", Boom)
    vobiz._OWNERSHIP.clear()
    j = cfg.get("/channel/status").json()["voice"]
    assert j["ready"] is False
    assert j["number"] is None


def test_status_withholds_the_number_when_unconfigured(monkeypatch):
    for var in ("VOBIZ_AUTH_ID", "VOBIZ_AUTH_TOKEN", "CIVOS_PUBLIC_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    j = TestClient(main.app).get("/channel/status").json()
    assert j["voice"]["ready"] is False
    assert j["voice"]["number"] is None, "printing a number that cannot be answered is worse than none"


def test_status_does_not_claim_an_sms_channel(cfg):
    """Vobiz carries voice and WhatsApp. It has no SMS send API."""
    j = cfg.get("/channel/status").json()
    assert j["sms"]["provider"] is None
    assert "no SMS send API" in j["sms"]["note"]
