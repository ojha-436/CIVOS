"""The /allocate endpoint against the real fixture."""

from __future__ import annotations

from fastapi.testclient import TestClient

import api.main as main

client = TestClient(main.app)


def test_allocate_returns_three_lanes():
    r = client.post("/allocate", json={"budget": 1_000_000_000})
    assert r.status_code == 200
    j = r.json()
    for lane in ("funded", "verify", "outreach"):
        assert lane in j
    assert j["summary"]["funded_cost"] <= 1_000_000_000


def test_silent_need_only_ever_appears_in_outreach():
    """The SPEC §8 rule, checked against real data rather than a fixture stub."""
    r = client.post("/allocate", json={"budget": 4_000_000_000})
    j = r.json()
    assert j["outreach"], "outreach lane must be populated — it is the product's distinctive claim"
    for a in j["outreach"]:
        assert "before funding" in a["rationale"]


def test_budget_is_never_exceeded():
    for budget in (100_000_000, 1_000_000_000, 8_000_000_000):
        j = client.post("/allocate", json={"budget": budget}).json()
        assert j["summary"]["total_cost"] <= budget


def test_shrinking_the_envelope_never_funds_more():
    big = client.post("/allocate", json={"budget": 4_000_000_000}).json()
    small = client.post("/allocate", json={"budget": 400_000_000}).json()
    assert small["summary"]["funded_cost"] <= big["summary"]["funded_cost"]
    assert small["summary"]["beneficiaries"] <= big["summary"]["beneficiaries"]


def test_every_funded_award_carries_its_evidence():
    j = client.post("/allocate", json={"budget": 1_000_000_000}).json()
    for a in j["funded"][:25]:
        assert a["scheme"]
        assert a["district"]
        assert a["beneficiaries"] is not None, "a funded award must have a countable reach"
        assert 0 <= a["confidence"] <= 100


def test_constraints_are_reported_either_way():
    j = client.post("/allocate", json={"budget": 200_000_000, "equity_floor_share": 0.9}).json()
    names = {c["name"] for c in j["constraints"]}
    assert {"budget", "equity_floor", "geographic_spread", "sector_cap"} <= names


def test_rejections_carry_reasons():
    j = client.post("/allocate", json={"budget": 200_000_000}).json()
    assert j["dropped_total"] > 0
    assert all(d["reason"] for d in j["dropped_sample"])


def test_absurd_budget_is_refused():
    assert client.post("/allocate", json={"budget": 0}).status_code == 422
    assert client.post("/allocate", json={"budget": -5}).status_code == 422
