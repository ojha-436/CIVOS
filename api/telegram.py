"""CIVOS Telegram channel — webhook receiver.

Why a webhook rather than polling
---------------------------------
`scripts/telegram_bot.py` calls `Application.run_polling()`, a blocking loop
that owns the process for its lifetime. Cloud Run scales to zero and throttles
CPU outside a request, so a polling loop there either never starts (no request,
no container) or is frozen between requests. Telegram pushing updates to an
HTTPS endpoint is the serverless-native shape, and it costs nothing at idle.

The polling script is kept for local development, where it is the faster loop —
no public URL required. Both paths share `format_result` below so the citizen
sees an identical receipt either way.

Why raw httpx instead of python-telegram-bot
--------------------------------------------
PTB is a declared project dependency but is deliberately NOT installed into the
deployed image (see Dockerfile's explicit install list), and its `Application`
runtime is built around a long-lived process this endpoint does not have. The
Bot API is plain HTTPS+JSON; three calls are all this needs.

Security
--------
`setWebhook` registers a secret token which Telegram then echoes back in the
`X-Telegram-Bot-Api-Secret-Token` header of every update. This endpoint rejects
anything without it. Without that check the URL is an open relay: anyone who
guessed it could inject fabricated citizen signals into the corpus, which for a
system whose entire thesis is measurement integrity would be fatal.

SPEC §11 privacy is unchanged from the polling path: audio and images are held
in memory for the length of one extraction call and never written to disk or
persisted; EXIF GPS resolves an administrative unit and is then discarded.
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Header, Request

from api.extraction import extract
from api.geo import parse_exif_gps, resolve_district

log = logging.getLogger("civos.telegram")

router = APIRouter(prefix="/telegram", tags=["telegram"])

API_ROOT = "https://api.telegram.org"

# Generous but bounded. Cloud Run is deployed with --timeout 120; Telegram drops
# a webhook call after ~60s and retries, so anything slower than this would be
# reprocessed rather than reported.
_TIMEOUT = httpx.Timeout(45.0, connect=10.0)

# Telegram caps a message at 4096 characters.
_MAX_MSG = 3900


def _token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def _secret() -> str:
    return os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()


# ---------------------------------------------------------------------------
# The citizen-facing receipt — shared with scripts/telegram_bot.py
# ---------------------------------------------------------------------------


def format_result(result: Any, district_name: str | None, geo_confidence: str) -> str:
    """Build the citizen-facing confirmation message.

    The receipt exists so nobody is left wondering whether their report landed,
    and so the privacy guarantee is stated to the person it protects rather than
    only in a policy document they will never open.
    """
    sector_label = (result.sector or "unclassified").replace("_", " ").title()
    severity = result.severity or 0
    severity_dots = "●" * severity + "○" * (5 - severity)

    lines = ["✓ *Received and structured.*", ""]

    if result.raw_text:
        lines.append(f"*In your words:* {result.raw_text[:200]}")
    if result.translation and result.translation != result.raw_text:
        lines.append(f"*English:* {result.translation[:200]}")

    lines += ["", f"*Sector:* {sector_label}", f"*Severity:* {severity_dots}"]

    if result.asset_type:
        flags = (
            ", ".join(f.replace("_", " ") for f in result.condition_flags)
            if result.condition_flags
            else ""
        )
        lines.append(
            f"*Asset:* {result.asset_type.replace('_', ' ')}" + (f" — {flags}" if flags else "")
        )
    if result.visual_description:
        lines.append(f"*Seen:* {result.visual_description[:200]}")

    loc = district_name or result.geo_hint or "unknown"
    lines.append(f"*Registered in:* {loc} _(geo: {geo_confidence})_")

    lines += [
        "",
        "_Your audio/photo has been analysed and deleted. No image or recording is stored._",
        "_If GPS was present, it was used once to find your district and then discarded._",
    ]
    return "\n".join(lines)


WELCOME = (
    "👋 *CIVOS citizen intake*\n\n"
    "Tell me what your area needs — by voice note, photo, or text.\n\n"
    "No form, no department jargon required. Just say what is wrong, "
    "in whatever language you speak.\n\n"
    "_Nothing identifying about you is stored._"
)


# ---------------------------------------------------------------------------
# Bot API helpers
# ---------------------------------------------------------------------------


async def _send(client: httpx.AsyncClient, chat_id: int, text: str) -> None:
    """Send a message, degrading to plain text if Markdown fails to parse.

    Citizen text is echoed back inside the receipt and can legitimately contain
    `*`, `_` or `[` — which makes Telegram reject the whole message with a 400.
    Losing the emphasis is obviously better than losing the receipt.
    """
    body = {"chat_id": chat_id, "text": text[:_MAX_MSG], "parse_mode": "Markdown"}
    r = await client.post(f"{API_ROOT}/bot{_token()}/sendMessage", json=body)
    if r.status_code == 400:
        body.pop("parse_mode")
        r = await client.post(f"{API_ROOT}/bot{_token()}/sendMessage", json=body)
    if r.status_code >= 400:
        log.warning("sendMessage failed: %s %s", r.status_code, r.text[:300])


async def _download(client: httpx.AsyncClient, file_id: str) -> bytes:
    """Resolve a file_id to bytes. Held in memory only — never written to disk."""
    r = await client.get(f"{API_ROOT}/bot{_token()}/getFile", params={"file_id": file_id})
    r.raise_for_status()
    path = r.json()["result"]["file_path"]
    f = await client.get(f"{API_ROOT}/file/bot{_token()}/{path}")
    f.raise_for_status()
    return f.content


# ---------------------------------------------------------------------------
# Update handling
# ---------------------------------------------------------------------------


async def _handle_message(client: httpx.AsyncClient, msg: dict[str, Any]) -> None:
    chat_id = msg["chat"]["id"]

    # -- /start ------------------------------------------------------------
    text = msg.get("text") or ""
    if text.startswith("/start"):
        await _send(client, chat_id, WELCOME)
        return

    # -- photo (checked before text: a captioned photo carries both) -------
    if msg.get("photo"):
        await _send(client, chat_id, "Analysing your photo…")
        try:
            file_id = msg["photo"][-1]["file_id"]  # last entry is the largest
            image_bytes = await _download(client, file_id)

            district_name: str | None = None
            geo_confidence = "inferred"
            gps = parse_exif_gps(image_bytes)
            if gps:
                geo = resolve_district(*gps)
                if geo:
                    district_name = f"{geo.name}, {geo.state}"
                    geo_confidence = "high"

            caption = msg.get("caption") or None
            result = extract(image_bytes=image_bytes, text=caption)
            await _send(client, chat_id, format_result(result, district_name, geo_confidence))
        except Exception:
            log.exception("photo handling failed")
            await _send(client, chat_id, "⚠️ Could not process that photo. Please try again.")
        return

    # -- voice / audio ------------------------------------------------------
    voice = msg.get("voice") or msg.get("audio")
    if voice:
        await _send(client, chat_id, "Transcribing your voice note…")
        try:
            audio_bytes = await _download(client, voice["file_id"])
            mime = voice.get("mime_type") or "audio/ogg"
            result = extract(audio_bytes=audio_bytes, audio_mime=mime)
            await _send(client, chat_id, format_result(result, None, "inferred"))
        except Exception:
            log.exception("voice handling failed")
            await _send(client, chat_id, "⚠️ Could not process that voice note. Please try again.")
        return

    # -- text ---------------------------------------------------------------
    if text:
        await _send(client, chat_id, "Processing…")
        try:
            result = extract(text=text)
            await _send(client, chat_id, format_result(result, None, "inferred"))
        except Exception:
            log.exception("text handling failed")
            await _send(client, chat_id, "⚠️ Could not process that. Please try again.")
        return

    await _send(
        client,
        chat_id,
        "Send a voice note, a photo, or a line of text describing what your area needs.",
    )


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """Receive one Telegram update.

    Always answers 200, including on failure. A non-200 makes Telegram redeliver
    the same update on a backoff, which for an extraction pipeline means paying
    for the same Gemini call repeatedly and sending the citizen duplicate
    replies. Errors are logged and reported in-chat instead.
    """
    if not _token() or not _secret():
        log.error("telegram webhook hit but TELEGRAM_BOT_TOKEN/SECRET not configured")
        return {"ok": False, "reason": "not_configured"}

    # compare_digest: constant-time, so the check cannot be turned into an
    # oracle by timing repeated guesses.
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, _secret()
    ):
        log.warning("rejected telegram update with bad or missing secret header")
        return {"ok": False, "reason": "forbidden"}

    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    msg = update.get("message") or update.get("edited_message")
    if not msg or "chat" not in msg:
        return {"ok": True}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await _handle_message(client, msg)
    except Exception:
        log.exception("telegram update handling failed")

    return {"ok": True}


@router.get("/status")
async def telegram_status():
    """Is the channel configured, and does Telegram agree the webhook is live?

    Deliberately reports configuration state without ever echoing the token.
    """
    configured = bool(_token()) and bool(_secret())
    out: dict[str, Any] = {"configured": configured}
    if not configured:
        out["hint"] = "set TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET"
        return out

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            me = await client.get(f"{API_ROOT}/bot{_token()}/getMe")
            hook = await client.get(f"{API_ROOT}/bot{_token()}/getWebhookInfo")
        out["username"] = me.json().get("result", {}).get("username")
        info = hook.json().get("result", {})
        out["webhook_url"] = info.get("url") or None
        out["pending_updates"] = info.get("pending_update_count")
        out["last_error"] = info.get("last_error_message")
    except Exception as exc:
        out["error"] = str(exc)
    return out
