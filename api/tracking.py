"""Tracking tokens — telling a citizen what happened, without recording that they asked.

Why this exists
---------------
The loop was half built. A citizen who reports by SMS or missed call already gets
a token back, and then nothing ever comes of it. That is the failure the whole
participation argument turns on: somebody who hears nothing does not report again,
and every one of those silences is a data point the correction then has to
reconstruct from census covariates instead of being told directly.

The privacy property, which is the interesting part
---------------------------------------------------
The obvious implementation is a table mapping token to submitter. This is not
that. **The token encodes the need, not the person.** It is a reversible encoding
of (which district-sector the report belongs to, which language to answer in), so
a status lookup needs no stored record of who reported what, no database row per
citizen, and nothing that survives the SMS itself.

That means CIVOS can answer "what happened to the thing you told us about?"
while being structurally incapable of answering "what did this person tell us?".
For a system that holds grievances about the state, addressed to the state, that
is worth more than the convenience of a lookup table.

It also means tokens keep working across restarts, across instances and across
redeploys, because there is nothing to lose.

What the token is not
---------------------
Not a secret and not a capability. It reveals a district, a sector and a language
— the same three things the reply itself contains. Anyone who guesses a valid
token learns the public status of a public need, which is information this system
exists to publish. The check character exists to stop typos returning a confident
answer about the wrong district, not to stop an attacker.

Status is derived, never stored
-------------------------------
The answer is computed from the current allocation at a fixed cycle envelope, so
it is always the truth as of now rather than a stale row somebody forgot to
update. The envelope is fixed deliberately: a citizen's status must not flicker
because somebody in the console happened to drag the budget slider.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re

# Unambiguous over a bad phone line and when read aloud: no vowels, so a token
# can never spell a word, and no 0/O or 1/I.
ALPHABET = "23456789BCDFGHJKLMNPQRSTVWXYZ"
BASE = len(ALPHABET)  # 29
PAYLOAD_CHARS = 5
MODULUS = BASE**PAYLOAD_CHARS  # 20,511,149

# Multiplicative scramble so consecutive needs do not get consecutive tokens.
# Coprime with the modulus (29 is prime, and this is not a multiple of it), which
# is what makes it invertible.
_MULT = 7_368_787
_ADD = 1_234_577
_MULT_INV = pow(_MULT, -1, MODULUS)

TOKEN_RE = re.compile(rf"^[{ALPHABET}]{{{PAYLOAD_CHARS + 1}}}$")

# Reply languages the tracker can be asked for. Index is part of the token, so
# appending is safe and reordering is not — a reordered list would change what
# every token already in a citizen's inbox decodes to.
REPLY_LANGUAGES = [
    "en", "hi", "mr", "bn", "ta", "te", "kn", "gu", "or", "pa", "ml", "as",
]
LANG_SLOTS = 32  # reserved so the list can grow without invalidating tokens


class TokenError(ValueError):
    """The token was malformed, mistyped, or is not one of ours."""


def _secret() -> bytes:
    return (os.environ.get("CIVOS_TOKEN_SECRET") or "civos-token-dev").encode()


def _check_char(payload: int) -> str:
    digest = hmac.new(_secret(), str(payload).encode(), hashlib.sha256).digest()
    return ALPHABET[digest[0] % BASE]


def encode(need_index: int, language: str = "en") -> str:
    """Build the token a citizen is given for one reported need."""
    if need_index < 0:
        raise TokenError("That code does not match any area we cover.")
    lang_index = REPLY_LANGUAGES.index(language) if language in REPLY_LANGUAGES else 0
    payload = need_index * LANG_SLOTS + lang_index
    if payload >= MODULUS:
        raise TokenError("need index exceeds the token space")
    scrambled = (payload * _MULT + _ADD) % MODULUS

    out = []
    n = scrambled
    for _ in range(PAYLOAD_CHARS):
        out.append(ALPHABET[n % BASE])
        n //= BASE
    body = "".join(reversed(out))
    return body + _check_char(scrambled)


def decode(token: str) -> tuple[int, str]:
    """Recover (need index, reply language). Raises TokenError on anything else."""
    t = (token or "").strip().upper().replace(" ", "").replace("-", "")
    if not TOKEN_RE.match(t):
        # Citizen-facing wording. "not a tracking token" is true and useless to
        # somebody squinting at an SMS on a feature phone.
        raise TokenError(
            "That does not look like a tracking code. It is six characters, like BCD234."
        )
    body, check = t[:-1], t[-1]

    scrambled = 0
    for ch in body:
        scrambled = scrambled * BASE + ALPHABET.index(ch)
    if not hmac.compare_digest(check, _check_char(scrambled)):
        # Almost always a mistyped character rather than an attack, so the
        # message says so — a citizen reading it needs to know to check the SMS.
        raise TokenError(
            "That code was not recognised. Please check it against the message you were sent."
        )

    payload = ((scrambled - _ADD) * _MULT_INV) % MODULUS
    need_index, lang_index = divmod(payload, LANG_SLOTS)
    language = REPLY_LANGUAGES[lang_index] if lang_index < len(REPLY_LANGUAGES) else "en"
    return need_index, language


def looks_like_token(text: str) -> bool:
    """Is this inbound message a tracking enquiry rather than a new report?

    Deliberately strict: only a message that is *nothing but* a token counts. A
    citizen who writes a sentence that happens to contain six consonants is
    filing a report, and mistaking one for the other would silently swallow it.
    """
    return bool(TOKEN_RE.match((text or "").strip().upper().replace(" ", "").replace("-", "")))


# ── the need universe ───────────────────────────────────────────────────────


def need_index_of(needs: list[tuple[str, str]], unit_code: str, sector: str) -> int:
    return needs.index((unit_code, sector))


def build_need_table(data: dict) -> list[tuple[str, str]]:
    """Stable ordering of every (unit, sector) the fixture scores.

    Sorted rather than fixture-ordered, so regenerating the fixture does not
    renumber tokens already issued.
    """
    return sorted({(r["code"], r["sector"]) for r in data["rows"]})


# ── status, in words ────────────────────────────────────────────────────────

STATUS_TEXT = {
    "fund": "Approved for funding",
    "verify_first": "A field check is scheduled",
    "outreach": "An outreach visit is scheduled",
    "none": "Recorded and ranked, not selected this cycle",
    "no_data": "Recorded. No official indicator covers this area yet",
}

STATUS_DETAIL = {
    "fund": (
        "Your area's need was corroborated and has been selected for funding in the "
        "current cycle under a named central scheme."
    ),
    "verify_first": (
        "Your area's need ranks high enough to fund, but the evidence needs checking "
        "first. Someone will be sent to look. It has not been rejected."
    ),
    "outreach": (
        "Official data shows a severe gap here but very few people have reported it, "
        "so an outreach visit is scheduled before any money is committed."
    ),
    "none": (
        "Your report was recorded, de-duplicated and ranked against every other "
        "district. It was not selected in this cycle and stays in the ranking."
    ),
    "no_data": (
        "Your report was recorded. No official indicator has been reconciled onto this "
        "area for this sector, so it is disclosed rather than scored."
    ),
}
