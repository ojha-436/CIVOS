"""One cached read of the score fixture, shared by everything that needs it.

It was private to `api/main.py`, which was fine until the telephony channel also
needed district names to place an inbound SMS. Importing it from there would have
been circular, and a second loader would have meant a second multi-megabyte parse
per process and two caches that could disagree about what "current" means.
"""

from __future__ import annotations

import json
import os
import unicodedata
from functools import lru_cache

SCORES_PATH = os.path.dirname(os.path.dirname(__file__)) + "/console/public/data/scores.json"


@lru_cache(maxsize=1)
def load_scores() -> dict:
    """Read and parse the score fixture once per process.

    The file is multi-MB; re-parsing it per request turned a cheap read endpoint
    into a disk-and-CPU amplifier any unauthenticated caller could pin an
    instance with.
    """
    with open(SCORES_PATH) as f:
        return json.load(f)


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "".join(ch for ch in t.lower() if ch.isalnum())


@lru_cache(maxsize=1)
def _district_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for d in load_scores()["districts"]:
        key = _norm(d["name"])
        # A name that is not unique is dropped rather than resolved arbitrarily.
        # Two districts called Aurangabad in different states is exactly the case
        # where guessing sends a citizen's report to the wrong place, and a
        # report filed against the wrong district is worse than one not placed:
        # it is a wrong number in a scored output.
        idx[key] = "" if key in idx and idx[key] != d["code"] else d["code"]
    return {k: v for k, v in idx.items() if v}


def resolve_unit_by_name(text: str) -> str | None:
    """Best-effort district match from free text a citizen typed.

    Deliberately weak and deliberately strict: whole-word containment against
    unique district names only. This is the fallback path for a channel with no
    coordinates and no picker — an SMS. It is not a geocoder, and anything it
    cannot place confidently it declines to place at all, which is why the
    caller has to handle "unplaced" as a real outcome rather than an edge case.
    """
    if not text:
        return None
    hay = _norm(text)
    best: tuple[int, str] | None = None
    for name, code in _district_index().items():
        if len(name) >= 4 and name in hay:
            if best is None or len(name) > best[0]:
                best = (len(name), code)
    return best[1] if best else None
