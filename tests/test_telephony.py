"""The feature-phone channels, and the privacy rule they exist under.

The tests that matter most here are the negative ones. An intake webhook that
accepts unsigned requests is an open relay for fabricated citizen signals, and
fabricated signals are fatal to a product whose entire claim is measurement
integrity. So "refuses when unconfigured" and "refuses a bad signature" are
pinned as hard as the happy path.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import pytest
from fastapi.testclient import TestClient

import api.main as main
from api.channels.telephony import SMS_UCS2_LIMIT, build_sms_reply, submitter_hash

SECRET = "test-secret"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CIVOS_TELEPHONY_SECRET", SECRET)
    monkeypatch.setenv("CIVOS_SUBMITTER_SALT", "test-salt")
    return TestClient(main.app)


def _sign(body: bytes) -> dict[str, str]:
    return {"X-Civos-Signature": hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()}


# ── privacy ────────────────────────────────────────────────────────────────


def test_phone_number_never_survives_hashing(monkeypatch):
    monkeypatch.setenv("CIVOS_SUBMITTER_SALT", "test-salt")
    number = "+919812345678"
    h = submitter_hash(number)
    assert "9812345678" not in h
    assert number not in h
    assert len(h) == 32


def test_same_caller_hashes_stably_different_callers_do_not(monkeypatch):
    """Distinct-submitter counting depends on this, and nothing else does."""
    monkeypatch.setenv("CIVOS_SUBMITTER_SALT", "test-salt")
    assert submitter_hash("+919812345678") == submitter_hash("09812345678")
    assert submitter_hash("+919812345678") != submitter_hash("+919812345679")


def test_salt_changes_the_hash(monkeypatch):
    monkeypatch.setenv("CIVOS_SUBMITTER_SALT", "salt-a")
    a = submitter_hash("9812345678")
    monkeypatch.setenv("CIVOS_SUBMITTER_SALT", "salt-b")
    assert submitter_hash("9812345678") != a


# ── the SMS receipt ────────────────────────────────────────────────────────


def test_reply_fits_a_single_ucs2_message():
    msg = build_sms_reply("BCD234", "Shrawasti", "water_sanitation")
    assert len(msg) <= SMS_UCS2_LIMIT


def test_token_survives_truncation():
    """Token first, because a truncated receipt must still be actionable."""
    msg = build_sms_reply("BCD234", "A" * 200, "education")
    assert msg.startswith("BCD234")
    assert len(msg) <= SMS_UCS2_LIMIT


# ── webhook authentication ─────────────────────────────────────────────────


def test_unconfigured_channel_refuses_rather_than_falling_open(monkeypatch):
    monkeypatch.delenv("CIVOS_TELEPHONY_SECRET", raising=False)
    c = TestClient(main.app)
    r = c.post("/channel/sms", data={"From": "+919812345678", "Body": "no water"})
    assert r.status_code == 503


def test_bad_signature_is_rejected(client):
    r = client.post(
        "/channel/sms",
        data={"From": "+919812345678", "Body": "no water"},
        headers={"X-Civos-Signature": "deadbeef"},
    )
    assert r.status_code == 403


def test_missing_signature_is_rejected(client):
    r = client.post("/channel/sms", data={"From": "+919812345678", "Body": "no water"})
    assert r.status_code == 403


# ── provider-agnostic field mapping ────────────────────────────────────────


def test_missed_call_asks_for_a_callback(client):
    body = b"From=%2B919812345678&CallSid=abc123"
    r = client.post(
        "/channel/voice/missed-call",
        content=body,
        headers={**_sign(body), "content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["action"] == "callback"
    assert j["recording_webhook"] == "/channel/voice/recording"
    # The caller's number must not come back out.
    assert "9812345678" not in r.text


def test_alternate_gateway_spelling_is_accepted(client):
    """Exotel says CallFrom, Twilio says From. Both must work."""
    body = b"CallFrom=09812345678&call_sid=xyz"
    r = client.post(
        "/channel/voice/missed-call",
        content=body,
        headers={**_sign(body), "content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    assert r.json()["action"] == "callback"


def test_empty_sms_is_rejected(client):
    body = b"From=%2B919812345678&Body="
    r = client.post(
        "/channel/sms",
        content=body,
        headers={**_sign(body), "content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 422


def test_status_admits_the_carrier_leg_is_unproven():
    """If somebody ever quietly flips this to True without a carrier, fail."""
    c = TestClient(main.app)
    j = c.get("/channel/status").json()
    assert j["carrier_account"] is False
    assert "unproven" in j["note"]
