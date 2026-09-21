"""Vobiz — the telephony provider behind the voice channel.

Everything provider-specific lives here. `telephony.py` holds the flow: a call
arrives, a citizen speaks, the recording becomes a signal. This module knows that
the flow is expressed as Vobiz Voice XML, that Vobiz signs its callbacks over the
URL rather than the body, and that its outbound call API is a form POST. Swapping
operator means writing a sibling of this file, not touching the flow.

Three facts about Vobiz that shaped the code
--------------------------------------------
**The webhook must answer in XML, not JSON.** An earlier version of the
missed-call endpoint returned a JSON object describing what it would like to
happen. No gateway reads that. Vobiz fetches the Answer URL and executes whatever
Voice XML comes back, so the endpoint's return value *is* the call flow.

**The signature covers the URL and a nonce, never the body.**
`base64(HMAC-SHA256(auth_token, base_url + "." + nonce))` for V3, the same
without the separator for V2. So the URL this service believes it was called at
has to match the URL Vobiz signed, exactly — which is why the public base URL is
configuration rather than something reconstructed from a proxied request, where
Cloud Run's TLS termination would hand us `http://` and a container hostname.

**The account auth token is the signing key.** There is no separate webhook
secret to invent: Vobiz signs with the same token that authenticates our API
calls. `CIVOS_TELEPHONY_SECRET` therefore does not apply to these endpoints; it
stays in use for a generic SMS gateway, which Vobiz is not — Vobiz carries voice
and WhatsApp, and has no SMS send API.

What the citizen's language does and does not depend on
-------------------------------------------------------
Vobiz text-to-speech offers `en-IN` and `hi-IN` for this country, which bounds the
*prompt* only. What the citizen says back is recorded as audio and understood by
the same Gemini multimodal call every other channel uses, so the languages CIVOS
accepts are unchanged by this integration. Where a prompt is needed in a language
Vobiz cannot speak, `<Play>` takes a pre-rendered file — the repository already
synthesises narration that way.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from urllib.parse import urlparse, urlunparse
from xml.sax.saxutils import escape

import httpx
from fastapi import HTTPException, Request

log = logging.getLogger("civos.vobiz")

API_ROOT = "https://api.vobiz.ai/api/v1"

# Vobiz speaks these two here. The list bounds the prompt, never the citizen.
SPEAK_LANGUAGES = ("hi-IN", "en-IN")


def auth_id() -> str:
    return os.environ.get("VOBIZ_AUTH_ID", "")


def auth_token() -> str:
    return os.environ.get("VOBIZ_AUTH_TOKEN", "")


def number() -> str:
    """The public number citizens dial. Country configuration, not a constant."""
    return os.environ.get("VOBIZ_NUMBER", "")


def public_base() -> str:
    """Origin Vobiz was configured to call, without a trailing slash.

    Configuration rather than inference: behind Cloud Run the request arrives
    over plain HTTP at a container hostname, so rebuilding the URL from it would
    produce a string Vobiz never signed and every callback would fail
    verification for the wrong reason.
    """
    return os.environ.get("CIVOS_PUBLIC_BASE_URL", "").rstrip("/")


def configured() -> bool:
    return bool(auth_id() and auth_token() and public_base())


def callback_url(path: str) -> str:
    return f"{public_base()}{path}"


# ── signature validation ────────────────────────────────────────────────────


def _base_url(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def _expected(token: str, base: str, nonce: str, sep: str) -> str:
    msg = f"{base}{sep}{nonce}".encode()
    return base64.b64encode(hmac.new(token.encode(), msg, hashlib.sha256).digest()).decode()


def verify(request: Request, path: str) -> None:
    """Reject anything that is not a signed Vobiz callback.

    Fails closed in both directions, which the Vobiz documentation explicitly
    warns about: signature headers are emitted only when the callback URL has
    credentials configured against it, so a missing signature is indistinguishable
    from a misconfiguration and must never be read as permission. An intake
    webhook that fell open would be a relay for fabricated citizen signals, and
    for a product whose entire claim is measurement integrity that is fatal.
    """
    token = auth_token()
    if not token or not public_base():
        raise HTTPException(503, "Voice channel is not configured.")

    base = _base_url(callback_url(path))
    v3 = request.headers.get("X-Vobiz-Signature-V3", "")
    n3 = request.headers.get("X-Vobiz-Signature-V3-Nonce", "")
    if v3 and n3 and hmac.compare_digest(v3, _expected(token, base, n3, ".")):
        return

    v2 = request.headers.get("X-Vobiz-Signature-V2", "")
    n2 = request.headers.get("X-Vobiz-Signature-V2-Nonce", "")
    if v2 and n2 and hmac.compare_digest(v2, _expected(token, base, n2, "")):
        return

    # V1 is HMAC-SHA1 and is not accepted. It exists for backwards compatibility
    # and there is no legacy here to be compatible with.
    log.warning("rejected unsigned or mis-signed callback on %s", path)
    raise HTTPException(403, "Bad signature.")


def sign_headers(path: str, nonce: str = "12345678901234567890") -> dict[str, str]:
    """Produce the headers Vobiz would send. Used by the simulator and tests."""
    base = _base_url(callback_url(path))
    return {
        "X-Vobiz-Signature-V3": _expected(auth_token(), base, nonce, "."),
        "X-Vobiz-Signature-V3-Nonce": nonce,
        "content-type": "application/x-www-form-urlencoded",
    }


# ── Voice XML ───────────────────────────────────────────────────────────────


def _xml(body: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<Response>{body}</Response>'


def empty() -> str:
    """What a handler returns when it must not redirect call control.

    `Record` is used with `redirect="false"`, so Vobiz posts the recording event
    and carries on with the flow it already has. Returning anything other than an
    empty response here would interrupt a call that has already moved past this
    point.
    """
    return _xml("")


def answer(prompt_hi: str, prompt_en: str, *, record_path: str, max_seconds: int = 90) -> str:
    """The call flow a citizen hears, as Vobiz executes it.

    Prompt in Hindi then English — short, because somebody who dialled to report a
    broken handpump did not call to listen. `playBeep` matters more than it looks:
    on a feature phone with no visual feedback the beep is the only signal that
    the system is now listening.

    `finishOnKey` is left at the Vobiz default so any key ends the recording, and
    `timeout` ends it on silence, so a caller who simply stops talking is handled
    without being asked to press anything.
    """
    return _xml(
        f'<Speak voice="WOMAN" language="hi-IN">{escape(prompt_hi)}</Speak>'
        f'<Speak voice="WOMAN" language="en-IN">{escape(prompt_en)}</Speak>'
        f'<Record action="{escape(callback_url(record_path))}" method="POST"'
        f' callbackUrl="{escape(callback_url(record_path))}" callbackMethod="POST"'
        f' maxLength="{max_seconds}" timeout="6" playBeep="true" fileFormat="mp3"'
        f' redirect="false"/>'
        f'<Speak voice="WOMAN" language="hi-IN">धन्यवाद। आपका संदेश दर्ज हो गया है।</Speak>'
        f"<Hangup/>"
    )


def unavailable(message_en: str) -> str:
    """Said aloud when the service cannot take the report right now.

    A citizen who dials and hears dead air concludes the number does not work and
    does not try again. Saying so costs one sentence.
    """
    return _xml(f'<Speak voice="WOMAN" language="en-IN">{escape(message_en)}</Speak><Hangup/>')


# ── outbound ────────────────────────────────────────────────────────────────


async def place_call(to: str, answer_path: str) -> dict:
    """Ring the citizen back so the report costs them nothing.

    The accessibility argument for a missed call only holds if the call back
    actually happens; otherwise "dial and hang up" is just a dropped call.
    """
    if not configured():
        raise HTTPException(503, "Voice channel is not configured.")
    payload = {
        "from": number(),
        "to": to,
        "answer_url": callback_url(answer_path),
        "answer_method": "POST",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            f"{API_ROOT}/Account/{auth_id()}/Call/",
            data=payload,
            headers={"X-Auth-ID": auth_id(), "X-Auth-Token": auth_token()},
        )
    if r.status_code >= 400:
        log.warning("vobiz call api %s", r.status_code)
        raise HTTPException(502, "Could not place the call back.")
    return r.json() if r.content else {}


async def fetch_recording(url: str, cap: int) -> bytes:
    """Pull the finished recording, with a hard ceiling on what we will buffer.

    Credentials are attached only for a Vobiz host. Vobiz hands back a URL and
    does not promise where it points; sending the account token to whatever
    hostname arrived in a webhook field would leak it to anyone who could forge
    one.
    """
    headers = {}
    if urlparse(url).netloc.endswith("vobiz.ai"):
        headers = {"X-Auth-ID": auth_id(), "X-Auth-Token": auth_token()}
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        async with client.stream("GET", url, headers=headers) as resp:
            resp.raise_for_status()
            buf = bytearray()
            async for chunk in resp.aiter_bytes():
                buf.extend(chunk)
                if len(buf) > cap:
                    raise HTTPException(413, "Recording exceeds the audio ceiling.")
            return bytes(buf)
