"""SMS intake — the text channel for a citizen with no smartphone.

SPEC §4 Persona 1 is Asha, who "owns a feature phone". The web widget, the
Telegram bot and even the image-only Tier D fallback all need a smartphone and a
data connection, so the citizen the participation correction exists to serve
could not reach the system. This is the channel that would.

Honest status: no operator is attached, and one is not obtainable here for free.
A number a citizen can dial requires, in this country, a KYC-verified account and
a purchased DID — a trial account refuses inbound routing outright, by policy
rather than by any gap in this code. Voice was built against a real provider and
then removed rather than shipped as a channel that answers nothing; the commit
that removes it records what it took, so re-attaching an operator is a known
quantity rather than a fresh investigation.

What remains is the provider-agnostic half, which is the part worth keeping. The
webhook normalises the field spellings the common Indian gateways use, the
extraction behind it is the same single Gemini call every other channel runs, and
the tracking token it issues is what lets a citizen ask later what happened.
Attaching a gateway is configuration: point it at `/channel/sms` and set the
signing secret.

Privacy (SPEC §11)
------------------
The sender's number is salted-hashed on arrival and the original is never stored,
never logged, and never returned. The hash exists so the trust model can count
distinct people without knowing any of them — which is exactly what
`TrustSignals.distinct_submitters` needs and the only reason identity is touched
at all.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from api import tracking
from api.extraction import extract
from api.fixture import load_scores, resolve_unit_by_name
from api.guards import rate_limit, safe_detail

log = logging.getLogger("civos.telephony")

router = APIRouter(prefix="/channel", tags=["telephony"])

# GSM-7 fits 160 characters per part. The moment a message contains one character
# outside that alphabet the encoding becomes UCS-2 and the limit collapses to 70,
# which is less than a single Devanagari sentence. So confirmations are built to
# fit 70 and the tracking token is placed first, where truncation cannot reach it.
SMS_UCS2_LIMIT = 70

# Field spellings seen across the common Indian gateways, most specific first.
_FROM_KEYS = ("From", "from", "CallFrom", "caller_id", "msisdn", "source", "sender")
_BODY_KEYS = ("Body", "body", "text", "message", "SmsText", "content")
_CALLSID_KEYS = ("CallSid", "call_sid", "CallId", "sid", "MessageSid")


def _pick(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for k in keys:
        v = payload.get(k)
        if v not in (None, ""):
            return str(v)
    return None


def _normalise(payload: dict[str, Any]) -> dict[str, str | None]:
    """One shape out of whichever gateway posted in.

    The common Indian gateways all post form-encoded webhooks carrying the same
    handful of fields under different names, so switching provider is a mapping
    entry rather than a rewrite.
    """
    return {
        "from": _pick(payload, _FROM_KEYS),
        "body": _pick(payload, _BODY_KEYS),
        "call_sid": _pick(payload, _CALLSID_KEYS),
    }


def _salt() -> str:
    """Per-deployment salt. A missing salt must not silently degrade to no salt.

    An unsalted hash of a ten-digit number is reversible by brute force in
    seconds, so a deployment without a configured salt gets a random one at
    process start: distinct-submitter counting still works within an instance,
    and nothing durable is written that could be cracked later.
    """
    s = os.environ.get("CIVOS_SUBMITTER_SALT")
    if not s:
        if not hasattr(_salt, "_ephemeral"):
            _salt._ephemeral = secrets.token_hex(32)  # type: ignore[attr-defined]
            log.warning("CIVOS_SUBMITTER_SALT unset — using an ephemeral per-process salt")
        return _salt._ephemeral  # type: ignore[attr-defined]
    return s


def submitter_hash(identifier: str) -> str:
    """Salted hash of a phone number. The number itself never leaves this function."""
    digits = "".join(ch for ch in identifier if ch.isdigit())[-10:]
    return hashlib.sha256(f"{_salt()}|{digits}".encode()).hexdigest()[:32]


def _token() -> str:
    """Short, unambiguous tracking token. No vowels, so it cannot spell anything,
    and no 0/O or 1/I, because it gets read aloud over a bad line."""
    alphabet = "23456789BCDFGHJKLMNPQRSTVWXYZ"
    return "".join(secrets.choice(alphabet) for _ in range(6))


def build_sms_reply(token: str | None, district: str | None, sector: str | None) -> str:
    """A receipt that survives a 70-character UCS-2 message.

    Token first: if a gateway truncates, the citizen keeps the one thing they need
    to follow the report up. Acknowledgement is not decoration — a citizen who
    hears nothing back does not report again, and every one of those is a data
    point the participation correction then has to reconstruct.

    When the report could not be placed there is no token, because a token that
    resolves to nothing is worse than none: the citizen texts it back, gets an
    error, and concludes the system lost their report. Instead the receipt asks
    for the one thing that would fix it.
    """
    if not token:
        return "Received. Reply with your district name so we can place it."[:SMS_UCS2_LIMIT]
    parts = [token]
    if district:
        parts.append(district)
    if sector:
        parts.append(sector.replace("_", " "))
    return " · ".join(parts)[:SMS_UCS2_LIMIT]


def build_status_reply(status: dict) -> str:
    """The answer to a citizen texting their token back."""
    head = status["headline"]
    place = status.get("district") or ""
    msg = f"{status['token']} {place}: {head}"
    return msg[:SMS_UCS2_LIMIT]


def place_report(result, text: str | None) -> tuple[str | None, str | None]:
    """Work out which need this report belongs to, and mint its token.

    Returns (token, district name), either of which may be None. Placing is
    best-effort by design on this channel: an SMS carries no coordinates and no
    picker, so the only signal is whatever place name the citizen mentioned. A
    report that cannot be placed is still extracted, still acknowledged and still
    counted — it simply cannot be tracked yet, and the receipt says so rather
    than issuing a token pointing at a district nobody named.
    """
    if not result.sector:
        return None, None
    haystack = " ".join(filter(None, [result.geo_hint, result.translation, result.raw_text, text]))
    code = resolve_unit_by_name(haystack)
    if not code:
        return None, None
    data = load_scores()
    table = tracking.build_need_table(data)
    try:
        index = table.index((code, result.sector))
    except ValueError:
        return None, None
    language = (result.language or "en").split("-")[0].lower()
    district = next((d["name"] for d in data["districts"] if d["code"] == code), None)
    return tracking.encode(index, language), district


def _verify_signature(request: Request, raw: bytes) -> None:
    """Reject anything not from the configured gateway.

    Same reasoning as the Telegram secret-token check: an unauthenticated intake
    URL is an open relay for fabricated signals, and fabricated signals are fatal
    to a product whose entire claim is measurement integrity. When no secret is
    configured the endpoint refuses rather than falling open.
    """
    secret = os.environ.get("CIVOS_TELEPHONY_SECRET")
    if not secret:
        raise HTTPException(503, "Telephony channel is not configured.")
    sent = request.headers.get("X-Civos-Signature", "")
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sent, expected):
        raise HTTPException(403, "Bad signature.")


async def ingest(
    *,
    channel: str,
    caller: str | None,
    text: str | None = None,
    audio: bytes | None = None,
    audio_mime: str = "audio/wav",
) -> dict[str, Any]:
    """The one path both telephony flows converge on.

    Deliberately the same `extract()` call the web widget and Telegram use: a new
    channel must not mean a new pipeline, or the claim that channels are cheap to
    add stops being true the first time someone checks.
    """
    if not text and not audio:
        raise HTTPException(422, "Neither speech nor text arrived on this call.")
    try:
        result = extract(audio_bytes=audio, audio_mime=audio_mime, text=text or None)
    except Exception as exc:
        raise HTTPException(502, safe_detail(exc, "Extraction failed.")) from exc

    token, district = place_report(result, text)
    return {
        "signal_id": str(uuid.uuid4()),
        "token": token,
        "district": district,
        "placed": token is not None,
        "channel": channel,
        "submitter_hash": submitter_hash(caller) if caller else None,
        "language": result.language,
        "raw_text": result.raw_text,
        "translation": result.translation,
        "sector": result.sector,
        "severity": result.severity,
        "geo_hint": result.geo_hint,
        "relevance": result.relevance,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "reply": build_sms_reply(token, district, result.sector),
        "carrier_leg": "unproven — no telephony account on this build; see api/channels/telephony.py",
    }


@router.post("/sms")
async def sms_webhook(request: Request, _: None = Depends(rate_limit)):
    """Inbound SMS. Either a new report, or a token being texted back.

    The same number does both, because asking a citizen on a feature phone to
    remember a second shortcode is asking them not to bother. A message that is
    *nothing but* a token is a status enquiry; anything else is a report. The
    test for that is strict on purpose — a sentence that happens to contain six
    consonants is a report, and mistaking one for the other would swallow it.
    """
    raw = await request.body()
    _verify_signature(request, raw)
    form = dict((await request.form()).items())
    n = _normalise(form)
    if not n["body"]:
        raise HTTPException(422, "Empty message.")
    body = str(n["body"])[:1000]

    if tracking.looks_like_token(body):
        # Imported here rather than at module scope: api.main imports this
        # router, so a module-level import would close the circle.
        from api.main import resolve_status

        try:
            status = resolve_status(body)
        except tracking.TokenError as exc:
            return {
                "kind": "status",
                "found": False,
                "reply": str(exc)[:SMS_UCS2_LIMIT],
            }
        return {
            "kind": "status",
            "found": True,
            "status": status,
            "reply": build_status_reply(status),
        }

    out = await ingest(channel="sms", caller=n["from"], text=body)
    out["kind"] = "report"
    return out


@router.get("/status")
async def telephony_status():
    """What this channel is, and why no operator is attached.

    A phone channel needs a number, and in this country a number a citizen can
    dial needs KYC and a paid DID — on a trial account inbound routing is
    refused outright, which no amount of code changes. Rather than ship a
    channel that answers nothing, CIVOS states the position and points at the
    two that work today.
    """
    return {
        "provider": None,
        "configured": bool(os.environ.get("CIVOS_TELEPHONY_SECRET")),
        "salt_configured": bool(os.environ.get("CIVOS_SUBMITTER_SALT")),
        "note": (
            "No telephony operator is attached. The webhook contract, the extraction behind it "
            "and the tracking loop are implemented and tested; a gateway posting to /channel/sms "
            "in the documented shape works without code changes. Inbound voice additionally "
            "requires a KYC-verified account and a purchased number, which is a deployment "
            "decision rather than a build one."
        ),
        "working_today": ["telegram", "web"],
    }
