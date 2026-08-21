"""Request guards: upload size caps, rate limiting, and safe error surfaces.

Why this module exists
----------------------
`/signal` and `/dossier` each invoke Gemini, and the service is deployed
`--allow-unauthenticated` with `CORS: *` so the public demo works from anywhere.
That combination means an unauthenticated stranger can spend the project's money
and exhaust a 1 GiB Cloud Run instance. Three controls make that survivable
without putting a login in front of a citizen-facing intake form:

1. **Size caps.** `await upload.read()` with no bound reads the whole body into
   memory. One 2 GiB POST is an out-of-memory kill, which is a denial of service
   costing the attacker a single request.
2. **Rate limits.** Both a global per-instance budget and a best-effort per-IP
   budget — see the honest caveat on `client_key` below.
3. **Opaque errors.** Exception text is logged, never returned. An exception
   message can carry a URL, a project id, a prompt, or a bot token.

What this is NOT
----------------
This is per-instance, in-memory state. Cloud Run runs up to `--max-instances 3`,
so the effective global ceiling is 3x what is configured here, and a restart
resets the counters. It is a cost-blast-radius control, not a quota system. A
real quota needs shared state (Redis / Cloud Armor / API Gateway). That gap is
recorded in docs/SECURITY-REVIEW.md rather than papered over.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from collections import deque
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, UploadFile

log = logging.getLogger("civos.guards")

# ── Upload ceilings ─────────────────────────────────────────────────────────
# Chosen against what the channel can actually deliver, so a legitimate citizen
# never hits them: Telegram caps a voice note well under 20 MB, and a phone
# photo is single-digit MB. Anything larger is not a citizen report.
MAX_AUDIO_BYTES = int(os.environ.get("CIVOS_MAX_AUDIO_BYTES", 12 * 1024 * 1024))
MAX_IMAGE_BYTES = int(os.environ.get("CIVOS_MAX_IMAGE_BYTES", 12 * 1024 * 1024))
MAX_CSV_BYTES = int(os.environ.get("CIVOS_MAX_CSV_BYTES", 8 * 1024 * 1024))
MAX_TEXT_CHARS = int(os.environ.get("CIVOS_MAX_TEXT_CHARS", 4000))
MAX_CSV_ROWS = int(os.environ.get("CIVOS_MAX_CSV_ROWS", 20000))

# ── Rate limits ─────────────────────────────────────────────────────────────
# Per IP, then per instance. The global one is the important one: it is the only
# figure an attacker cannot inflate by rotating source addresses.
RATE_PER_IP = int(os.environ.get("CIVOS_RATE_PER_IP", 20))
RATE_PER_IP_WINDOW = int(os.environ.get("CIVOS_RATE_PER_IP_WINDOW", 60))
RATE_GLOBAL = int(os.environ.get("CIVOS_RATE_GLOBAL", 120))
RATE_GLOBAL_WINDOW = int(os.environ.get("CIVOS_RATE_GLOBAL_WINDOW", 60))

# Bound the key space so the limiter cannot itself become the memory leak that
# exhausts the instance — the exact failure it exists to prevent.
MAX_TRACKED_IPS = 4096


@dataclass
class _Window:
    """Sliding-window counter. Timestamps only; no request contents retained."""

    limit: int
    window: int
    hits: deque[float] = field(default_factory=deque)

    def allow(self, now: float) -> bool:
        cutoff = now - self.window
        while self.hits and self.hits[0] < cutoff:
            self.hits.popleft()
        if len(self.hits) >= self.limit:
            return False
        self.hits.append(now)
        return True


_per_ip: dict[str, _Window] = {}
_global = _Window(RATE_GLOBAL, RATE_GLOBAL_WINDOW)


def client_key(request: Request) -> str:
    """Best-effort client identity for rate limiting.

    On Cloud Run the caller's address is the first entry of X-Forwarded-For.
    A client can prepend its own XFF, so this value is **spoofable** and the
    per-IP limit is therefore a fairness measure, not a security boundary. The
    global limiter is what actually bounds spend. Stated plainly because a
    per-IP limit described as DoS protection is worse than none: it invites
    trust it cannot carry.
    """
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]


def rate_limit(request: Request) -> None:
    """Raise 429 when either the per-IP or the per-instance budget is spent."""
    now = time.monotonic()

    if not _global.allow(now):
        log.warning("global rate limit hit (%d/%ds)", RATE_GLOBAL, RATE_GLOBAL_WINDOW)
        raise HTTPException(429, "Service is busy. Please retry in a minute.")

    key = client_key(request)
    win = _per_ip.get(key)
    if win is None:
        if len(_per_ip) >= MAX_TRACKED_IPS:
            # Drop the coldest tracked key rather than grow without bound.
            oldest = min(_per_ip, key=lambda k: _per_ip[k].hits[-1] if _per_ip[k].hits else 0)
            _per_ip.pop(oldest, None)
        win = _per_ip[key] = _Window(RATE_PER_IP, RATE_PER_IP_WINDOW)
    if not win.allow(now):
        log.info("per-ip rate limit hit")
        raise HTTPException(429, "Too many requests. Please slow down.")


async def read_capped(upload: UploadFile, cap: int, label: str) -> bytes:
    """Read an upload, refusing anything over `cap` bytes.

    Two checks, because either alone is insufficient. Content-Length is a cheap
    pre-flight reject but a client may lie about it or omit it entirely under
    chunked transfer encoding; the streaming loop is the one that actually holds,
    and it stops at cap+1 bytes rather than after buffering the whole body.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > cap:
            raise HTTPException(
                413, f"{label} exceeds the {cap // (1024 * 1024)} MB limit."
            )
        chunks.append(chunk)
    return b"".join(chunks)


def check_content_length(request: Request, cap: int) -> None:
    """Reject an oversized body before a single byte is buffered."""
    raw = request.headers.get("content-length")
    if not raw:
        return
    try:
        declared = int(raw)
    except ValueError:
        raise HTTPException(400, "Malformed Content-Length.") from None
    if declared > cap:
        raise HTTPException(413, f"Request body exceeds the {cap // (1024 * 1024)} MB limit.")


def clamp_text(value: str | None, limit: int = MAX_TEXT_CHARS) -> str | None:
    """Truncate free text. Unbounded text is both a cost and a prompt-size risk."""
    if value is None:
        return None
    value = value.replace("\x00", "")
    return value[:limit]


def client_fingerprint(request: Request) -> str:
    """A stable, non-reversible tag for one caller.

    Access logs need to distinguish callers to be useful for abuse
    investigation, but SPEC 11 says CIVOS does not retain where a citizen was.
    An IP is personal data in most of the jurisdictions this is aimed at, so the
    log gets a salted digest instead: two requests from one caller match, and the
    log never carries the address.

    The salt defaults to the process start rather than a constant, so a digest
    cannot be correlated across restarts or rainbow-tabled from the 4-billion
    IPv4 space.
    """
    return hashlib.sha256(f"{_LOG_SALT}:{client_key(request)}".encode()).hexdigest()[:12]


_LOG_SALT = os.environ.get("CIVOS_LOG_SALT") or secrets.token_hex(16)


def safe_detail(exc: Exception, public: str) -> str:
    """Log the real error; hand the caller a message that reveals nothing.

    `str(exc)` from an httpx or google-genai failure routinely contains the full
    request URL — which for the Telegram Bot API embeds the bot token in the
    path, and for Vertex embeds the project and location.
    """
    log.exception("%s: %s: %s", public, type(exc).__name__, exc)
    return public
