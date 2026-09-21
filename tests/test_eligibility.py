"""Scheme eligibility — a scheme may only pay for what its scope actually covers.

The bug this pins: the allocator matched a scheme to a need on sector alone, and
proposed AMRUT 2.0 — whose published scope is statutory towns — for Karbi Anglong,
Dima Hasao and Dhemaji, which are rural hill districts. The eligibility text was in
the adapter the whole time as prose nothing could read.

The test at the bottom is the one that matters most: it reads the real adapter and
asserts the real consequence, so if somebody later adds an urban indicator (or
quietly relabels the roads one), the expectation has to be updated deliberately
rather than drifting.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from api.candidates import DEFAULT_WEIGHTS, build_candidates, eligible

REPO = Path(__file__).resolve().parent.parent


def test_urban_scheme_is_refused_by_a_rural_indicator():
    assert not eligible({"applies_to": "urban"}, {"measures": "rural"})


def test_rural_scheme_is_refused_by_an_urban_indicator():
    assert not eligible({"applies_to": "rural"}, {"measures": "urban"})


def test_overlap_is_enough_not_equality():
    """A rural scheme against an indicator covering both settlements is fine.

    The rural half of that measurement is real need the scheme can serve, so
    demanding an exact match would reject every legitimate pairing in the adapter.
    """
    assert eligible({"applies_to": "rural"}, {"measures": "both"})
    assert eligible({"applies_to": "urban"}, {"measures": "both"})
    assert eligible({"applies_to": "both"}, {"measures": "rural"})


def test_a_missing_field_does_not_break_another_country_adapter():
    assert eligible({}, {})
    assert eligible({"applies_to": "rural"}, {})


def test_the_adapter_declares_a_scope_for_every_scheme_and_sector():
    """A new scheme without a scope would silently be treated as unrestricted."""
    schemes = yaml.safe_load((REPO / "adapters/in/schemes.yaml").read_text())["schemes"]
    sectors = yaml.safe_load((REPO / "adapters/in/sectors.yaml").read_text())["sectors"]
    allowed = {"rural", "urban", "both"}
    for s in schemes:
        assert s.get("applies_to") in allowed, f"{s['key']} has no applies_to"
        assert s.get("beneficiaries_per_unit"), f"{s['key']} has no beneficiaries_per_unit"
    for s in sectors:
        assert s["indicator"].get("measures") in allowed, f"{s['key']} indicator has no measures"


def test_no_urban_roads_scheme_is_proposed_against_a_village_indicator():
    """The real consequence, checked against the real fixture.

    The roads indicator is the Census Village Directory, which counts villages and
    has no urban universe at all. So no urban roads scheme is justifiable anywhere
    in this build — AMRUT proposes zero projects. That is the correct answer to the
    question being asked, not a coverage gap.
    """
    data = json.loads((REPO / "console/public/data/scores.json").read_text())
    cands = build_candidates(data, DEFAULT_WEIGHTS)
    assert cands, "fixture produced no candidates at all"

    urban_only = {
        s["name"]
        for sec in data["sectors"]
        for s in sec["schemes"]
        if s.get("applies_to") == "urban" and sec.get("measures") == "rural"
    }
    assert urban_only, "expected at least one urban scheme bound to a rural indicator"
    proposed = {c.scheme_key for c in cands}
    assert not (urban_only & proposed), f"urban scheme proposed on rural evidence: {urban_only & proposed}"

    # And the schemes that remain are still a real spread, not an empty set.
    assert len(proposed) >= 8
