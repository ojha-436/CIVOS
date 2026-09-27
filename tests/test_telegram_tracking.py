"""The loop, over the one channel that actually carries a report today.

Telegram is now where a citizen gets a tracking code and where they send it back,
because it is the only intake with a live operator behind it. These tests pin the
two halves and the rule that separates them: a message that is *nothing but* a
code is a lookup, and anything else is a report.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import api.main as main
from api import tracking
from api.telegram import WELCOME, format_result, format_status

REPO = Path(__file__).resolve().parent.parent


class _Result:
    """The fields format_result reads off an ExtractionResult."""

    def __init__(self, **kw):
        self.raw_text = kw.get("raw_text", "")
        self.translation = kw.get("translation", "")
        self.sector = kw.get("sector")
        self.severity = kw.get("severity", 3)
        self.asset_type = kw.get("asset_type")
        self.condition_flags = kw.get("condition_flags", [])
        self.visual_description = kw.get("visual_description")
        self.geo_hint = kw.get("geo_hint")
        self.language = kw.get("language", "en")


# ── placing ─────────────────────────────────────────────────────────────────


def test_a_named_district_and_a_sector_produce_a_code():
    token, district = tracking.place(
        "water_sanitation", hint_text="no water in shrawasti for months", language="hi"
    )
    assert token and tracking.looks_like_token(token)
    assert district == "Shrawasti"
    idx, lang = tracking.decode(token)
    assert lang == "hi"
    assert main._need_table()[idx] == ("IN-UP-shrawasti", "water_sanitation")


def test_a_resolved_unit_beats_a_place_name_in_the_text():
    """EXIF gives a containment-tested unit; it must not be second-guessed."""
    token, district = tracking.place(
        "education", unit_code="IN-UP-shrawasti", hint_text="somewhere near bahraich"
    )
    idx, _ = tracking.decode(token)
    assert main._need_table()[idx] == ("IN-UP-shrawasti", "education")
    assert district == "Shrawasti"


def test_no_sector_means_no_code():
    assert tracking.place(None, hint_text="shrawasti") == (None, None)


def test_an_unplaceable_report_gets_no_code():
    assert tracking.place("education", hint_text="the school roof leaks") == (None, None)


# ── the receipt ─────────────────────────────────────────────────────────────


def test_the_receipt_shows_the_code_and_says_what_it_is_for():
    token, _ = tracking.place("water_sanitation", hint_text="shrawasti has no water")
    msg = format_result(_Result(sector="water_sanitation", raw_text="no water"),
                        "Shrawasti", "inferred", token)
    assert token in msg
    assert "tell you what happened" in msg
    assert "identifies the need, not you" in msg


def test_an_unplaced_report_asks_for_the_district_instead_of_inventing_a_code():
    msg = format_result(_Result(sector="education"), None, "inferred", None)
    assert "no tracking code" in msg
    assert "district name" in msg


def test_the_privacy_line_survives_either_way():
    for tok in (None, tracking.encode(3, "en")):
        msg = format_result(_Result(sector="health"), None, "inferred", tok)
        assert "analysed and deleted" in msg


def test_the_welcome_tells_people_the_code_is_coming():
    assert "tracking code" in WELCOME
    assert "what happened" in WELCOME


# ── the lookup ──────────────────────────────────────────────────────────────


def test_only_a_bare_code_is_treated_as_a_lookup():
    code = tracking.encode(11, "en")
    assert tracking.looks_like_token(code)
    assert not tracking.looks_like_token(f"my code is {code}")
    assert not tracking.looks_like_token("school building has no roof at all")


def test_status_message_names_the_place_and_the_outcome():
    lanes = main._cycle_lanes()
    outreach = next(k for k, (lane, _) in lanes.items() if lane == "outreach")
    token = tracking.encode(main._need_table().index(outreach), "en")
    msg = format_status(main.resolve_status(token))
    assert "outreach visit is scheduled" in msg.lower()
    assert "before any money is committed" in msg
    assert "the decision changed" in msg


def test_a_funded_status_names_the_scheme():
    lanes = main._cycle_lanes()
    funded = next((k for k, (lane, _) in lanes.items() if lane == "fund"), None)
    if funded is None:
        pytest.skip("no funded lane in this cycle")
    token = tracking.encode(main._need_table().index(funded), "en")
    msg = format_status(main.resolve_status(token))
    assert "Scheme:" in msg


def test_the_full_round_trip_report_then_ask():
    """Report a need, take the code from the receipt, ask what happened."""
    result = _Result(sector="education", raw_text="school has no roof",
                     translation="school has no roof", geo_hint="shrawasti")
    token, district = tracking.place(
        result.sector, hint_text=f"{result.geo_hint} {result.translation}",
        language=result.language,
    )
    receipt = format_result(result, district, "inferred", token)
    assert token in receipt

    status = main.resolve_status(token)
    assert status["district"] == "Shrawasti"
    assert status["sector"] == "education"
    assert status["lane"] in {"fund", "verify_first", "outreach", "none", "no_data"}
    assert "cannot produce one" in status["privacy"]
