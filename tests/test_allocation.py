"""The allocator and the trust model, pinned on the cases that carry the argument.

Two of these tests exist to stop a future change from quietly breaking an ethical
commitment rather than a computation:

  * `test_camera_less_district_still_clears_the_floor` pins the rule that absence
    of photographic evidence must not push a genuinely corroborated need into the
    verification queue. If somebody raises the evidence weight, this fails.
  * `test_silent_need_is_never_funded` pins SPEC §8. If somebody "improves" the
    allocator by letting high-deficit silent units into the funding lane, this
    fails, and it should.
"""

from __future__ import annotations

import pytest

from core.allocation import (
    Candidate,
    Constraints,
    Lane,
    TrustSignals,
    allocate,
    assess,
    assign_lane,
)
from core.allocation.trust import TrustFlag


# ── trust ───────────────────────────────────────────────────────────────────


def test_ten_people_beat_one_person_repeating():
    crowd = assess(TrustSignals(total_reports=10, distinct_submitters=10, deficit_pct=60))
    one = assess(TrustSignals(total_reports=10, distinct_submitters=1, deficit_pct=60))
    assert crowd.confidence > one.confidence
    assert TrustFlag.SINGLE_SUBMITTER in one.flags
    assert TrustFlag.SINGLE_SUBMITTER not in crowd.flags


def test_camera_less_district_still_clears_the_floor():
    """No photographs, no verified coordinates — still trusted on corroboration.

    This is the w5 argument made executable. A district where nobody owns a camera
    must not be punished twice.
    """
    a = assess(
        TrustSignals(
            total_reports=9,
            distinct_submitters=9,
            image_backed=0,
            geo_verified=0,
            deficit_pct=70,
            mean_severity=4.0,
        )
    )
    assert a.confidence >= 55.0
    assert not a.review_required
    # The location flag may be raised for information, but must not force review.
    assert TrustFlag.UNVERIFIED_LOCATION in a.flags


def test_recycled_imagery_collapses_confidence():
    a = assess(
        TrustSignals(
            total_reports=8, distinct_submitters=8, image_backed=8, reused_images=8, deficit_pct=50
        )
    )
    assert TrustFlag.RECYCLED_IMAGERY in a.flags
    assert a.review_required


def test_coordinated_burst_is_flagged():
    a = assess(
        TrustSignals(total_reports=40, distinct_submitters=38, burst_share=0.97, deficit_pct=40)
    )
    assert TrustFlag.COORDINATED_BURST in a.flags


def test_plausibility_never_bottoms_out_on_an_expectation_gap():
    """A citizen contradicting a stale dataset is a finding, not a lie."""
    a = assess(
        TrustSignals(total_reports=12, distinct_submitters=12, deficit_pct=0.0, mean_severity=5.0)
    )
    assert a.components["plausibility"] >= 0.35
    assert a.confidence > 0


def test_missing_official_data_is_neutral_not_punitive():
    known = assess(TrustSignals(total_reports=6, distinct_submitters=6, deficit_pct=55))
    unknown = assess(TrustSignals(total_reports=6, distinct_submitters=6, deficit_pct=None))
    assert unknown.confidence > 0
    assert abs(unknown.confidence - known.confidence) < 25


# ── allocator ───────────────────────────────────────────────────────────────


def _cand(cid, *, cost, priority, benef=100_000, quad="act_now", conf=80.0, deprived=False,
          sector="s1", group="g1", unit=None):
    return Candidate(
        candidate_id=cid,
        unit_code=unit or cid,
        group_key=group,
        sector=sector,
        scheme_key="scheme",
        units=10,
        unit_cost=cost // 10 or 1,
        cost=cost,
        priority=priority,
        quadrant=quad,
        confidence=conf,
        beneficiaries=benef,
        deprived=deprived,
    )


def test_silent_need_is_never_funded():
    """SPEC §8: the system flags silence for outreach. It never buys concrete on it."""
    c = _cand("a", cost=1_000_000, priority=99, quad="silent_need")
    lane, why = assign_lane(c, Constraints(budget=10_000_000))
    assert lane is Lane.OUTREACH
    assert "before funding" in why

    out = allocate([c], Constraints(budget=10_000_000))
    assert not out.funded
    assert len(out.outreach) == 1


def test_low_confidence_goes_to_verification_not_the_bin():
    c = _cand("a", cost=1_000_000, priority=90, conf=20.0)
    out = allocate([c], Constraints(budget=10_000_000))
    assert not out.funded
    assert len(out.verify) == 1
    assert out.verify[0].lane is Lane.VERIFY_FIRST


def test_unknown_population_is_disclosed_never_assumed_zero():
    c = Candidate(
        candidate_id="a", unit_code="u", group_key="g", sector="s", scheme_key="k",
        units=1, unit_cost=100, cost=100, priority=90, quadrant="act_now",
        confidence=90, beneficiaries=None,
    )
    out = allocate([c], Constraints(budget=1_000_000))
    assert not out.funded
    assert any("Population unavailable" in d.reason for d in out.dropped)


def test_budget_is_respected_and_every_drop_has_a_reason():
    cands = [_cand(f"c{i}", cost=400_000, priority=50 + i, unit=f"u{i}") for i in range(20)]
    out = allocate(cands, Constraints(budget=2_000_000, sector_cap_share=1.0, equity_floor_share=0.0,
                                      min_groups=1, outreach_reserve_share=0.0))
    assert out.funded_cost <= 2_000_000
    assert out.dropped
    assert all(d.reason for d in out.dropped)


def test_higher_value_per_rupee_wins_over_higher_priority():
    """The whole reason to optimise a portfolio instead of funding down a ranking."""
    cheap_broad = _cand("broad", cost=1_000_000, priority=60, benef=500_000, unit="u1")
    dear_acute = _cand("acute", cost=5_000_000, priority=95, benef=2_000, unit="u2")
    out = allocate([cheap_broad, dear_acute],
                   Constraints(budget=5_000_000, sector_cap_share=1.0, equity_floor_share=0.0,
                               min_groups=1, outreach_reserve_share=0.0))
    ids = {a.candidate.candidate_id for a in out.funded}
    assert "broad" in ids


def test_equity_floor_pulls_in_deprived_units():
    rich = [_cand(f"r{i}", cost=1_000_000, priority=90, benef=900_000, unit=f"r{i}") for i in range(5)]
    poor = [_cand(f"p{i}", cost=1_000_000, priority=70, benef=200_000, deprived=True, unit=f"p{i}")
            for i in range(5)]
    k = Constraints(budget=5_000_000, sector_cap_share=1.0, equity_floor_share=0.4,
                    min_groups=1, outreach_reserve_share=0.0)
    out = allocate(rich + poor, k)
    spend_deprived = sum(a.cost for a in out.funded if a.candidate.deprived)
    assert spend_deprived >= int(5_000_000 * 0.4)
    assert next(c for c in out.constraints if c.name == "equity_floor").satisfied


def test_geographic_spread_is_repaired():
    one_group = [_cand(f"a{i}", cost=900_000, priority=95, benef=800_000, group="g1", unit=f"a{i}")
                 for i in range(6)]
    others = [_cand(f"b{i}", cost=900_000, priority=40, benef=100_000, group=f"g{i + 2}", unit=f"b{i}")
              for i in range(3)]
    k = Constraints(budget=5_400_000, sector_cap_share=1.0, equity_floor_share=0.0,
                    min_groups=3, outreach_reserve_share=0.0)
    out = allocate(one_group + others, k)
    groups = {a.candidate.group_key for a in out.funded}
    assert len(groups) >= 3


def test_sector_cap_prevents_monoculture():
    water = [_cand(f"w{i}", cost=1_000_000, priority=95, benef=900_000, sector="water", unit=f"w{i}")
             for i in range(10)]
    roads = [_cand(f"r{i}", cost=1_000_000, priority=60, benef=400_000, sector="roads", unit=f"r{i}")
             for i in range(10)]
    k = Constraints(budget=10_000_000, sector_cap_share=0.4, equity_floor_share=0.0,
                    min_groups=1, outreach_reserve_share=0.0)
    out = allocate(water + roads, k)
    by_sector: dict[str, int] = {}
    for a in out.funded:
        by_sector[a.candidate.sector] = by_sector.get(a.candidate.sector, 0) + a.cost
    for spend in by_sector.values():
        assert spend <= int(10_000_000 * 0.4)


def test_competing_schemes_for_one_unit_sector_are_mutually_exclusive():
    a = _cand("a", cost=500_000, priority=90, unit="u1", sector="water")
    b = _cand("b", cost=500_000, priority=88, unit="u1", sector="water")
    out = allocate([a, b], Constraints(budget=10_000_000, sector_cap_share=1.0,
                                       equity_floor_share=0.0, min_groups=1,
                                       outreach_reserve_share=0.0))
    assert len(out.funded) == 1
    assert any("competing scheme" in d.reason.lower() for d in out.dropped)


def test_infeasible_equity_floor_is_surfaced_not_hidden():
    rich = [_cand(f"r{i}", cost=1_000_000, priority=90, unit=f"r{i}") for i in range(5)]
    k = Constraints(budget=5_000_000, sector_cap_share=1.0, equity_floor_share=0.5,
                    min_groups=1, outreach_reserve_share=0.0)
    out = allocate(rich, k)
    assert out.infeasible
    assert any("Equity floor unreachable" in m for m in out.infeasible)


def test_shrinking_the_budget_never_increases_spend():
    cands = [_cand(f"c{i}", cost=700_000, priority=50 + i, benef=100_000 * (i + 1), unit=f"u{i}")
             for i in range(15)]
    k = Constraints(sector_cap_share=1.0, equity_floor_share=0.0, min_groups=1,
                    outreach_reserve_share=0.0, budget=10_000_000)
    big = allocate(cands, k)
    small = allocate(cands, Constraints(budget=3_000_000, sector_cap_share=1.0,
                                        equity_floor_share=0.0, min_groups=1,
                                        outreach_reserve_share=0.0))
    assert small.funded_cost <= big.funded_cost
    assert small.funded_cost <= 3_000_000


def test_summary_reports_cost_per_beneficiary():
    out = allocate([_cand("a", cost=1_000_000, priority=80, benef=50_000)],
                   Constraints(budget=2_000_000, sector_cap_share=1.0, equity_floor_share=0.0,
                               min_groups=1, outreach_reserve_share=0.0))
    s = out.summary()
    assert s["beneficiaries"] == 50_000
    assert s["cost_per_beneficiary"] == pytest.approx(20.0)
    assert "not proven optimal" in s["optimality_note"]


# ── regressions ─────────────────────────────────────────────────────────────
#
# Each of these pins a bug found by reviewing the engine after it was first
# written and passing. They are the tests most likely to matter later, because
# all three failures were silent: the allocator returned a confident, plausible
# portfolio that violated a constraint it claimed to hold.


def test_spread_repair_never_breaks_the_sector_cap():
    """Reaching the group minimum must not be bought by breaching a ceiling.

    The first implementation pushed a sector to double its cap to reach the group
    minimum, then reported `sector_cap` as violated while printing a message that
    said nothing exceeded it.
    """
    dense = [_cand(f"a{i}", cost=100_000, priority=95, benef=900_000, sector="water",
                   group="g1", unit=f"a{i}") for i in range(8)]
    remote = [_cand(f"b{i}", cost=400_000, priority=10, benef=1_000, sector="water",
                    group=f"g{i + 2}", unit=f"b{i}") for i in range(2)]
    k = Constraints(budget=2_000_000, sector_cap_share=0.40, equity_floor_share=0.0,
                    min_groups=3, outreach_reserve_share=0.0, verify_reserve_share=0.0)
    out = allocate(dense + remote, k)

    spend: dict[str, int] = {}
    for a in out.funded:
        spend[a.candidate.sector] = spend.get(a.candidate.sector, 0) + a.cost
    cap = int(2_000_000 * 0.40)
    for sector, v in spend.items():
        assert v <= cap, f"{sector} breached the cap: {v} > {cap}"
    # Unreachable spread must be declared, not silently bought.
    groups = {a.candidate.group_key for a in out.funded}
    if len(groups) < 3:
        assert any("spread unreachable" in m for m in out.infeasible)


def test_equity_repair_never_breaks_the_sector_cap():
    """The eviction path checked the budget but not the ceiling it would leave."""
    rich = [_cand(f"r{i}", cost=500_000, priority=90, benef=900_000, sector="roads",
                  unit=f"r{i}") for i in range(6)]
    poor = [_cand(f"p{i}", cost=500_000, priority=60, benef=50_000, sector="water",
                  deprived=True, unit=f"p{i}") for i in range(6)]
    k = Constraints(budget=3_000_000, sector_cap_share=0.35, equity_floor_share=0.6,
                    min_groups=1, outreach_reserve_share=0.0, verify_reserve_share=0.0)
    out = allocate(rich + poor, k)

    spend: dict[str, int] = {}
    for a in out.funded:
        spend[a.candidate.sector] = spend.get(a.candidate.sector, 0) + a.cost
    cap = int(3_000_000 * 0.35)
    for sector, v in spend.items():
        assert v <= cap, f"{sector} breached the cap during equity repair: {v} > {cap}"


def test_a_violated_constraint_never_prints_a_reassuring_message():
    """A status line that contradicts its own boolean is worse than none."""
    dense = [_cand(f"a{i}", cost=100_000, priority=95, benef=900_000, sector="water",
                   group="g1", unit=f"a{i}") for i in range(8)]
    remote = [_cand(f"b{i}", cost=400_000, priority=10, benef=1_000, sector="water",
                    group=f"g{i + 2}", unit=f"b{i}") for i in range(2)]
    out = allocate(dense + remote,
                   Constraints(budget=2_000_000, sector_cap_share=0.40, equity_floor_share=0.0,
                               min_groups=3, outreach_reserve_share=0.0, verify_reserve_share=0.0))
    for c in out.constraints:
        if not c.satisfied:
            assert not c.detail.startswith("No sector exceeds"), c.detail


def test_the_stated_reserve_is_the_actual_reserve():
    """A 5% dial withheld 8.37% because verification reused the outreach share."""
    cands = (
        [_cand(f"f{i}", cost=1_000_000, priority=70, benef=400_000, unit=f"f{i}") for i in range(30)]
        + [_cand(f"s{i}", cost=1_000_000, priority=70, quad="silent_need", unit=f"s{i}") for i in range(30)]
        + [_cand(f"v{i}", cost=1_000_000, priority=70, conf=10.0, unit=f"v{i}") for i in range(30)]
    )
    budget = 100_000_000
    out = allocate(cands, Constraints(budget=budget, sector_cap_share=1.0, equity_floor_share=0.0,
                                      min_groups=1, outreach_reserve_share=0.05,
                                      verify_reserve_share=0.03))
    assert out.outreach_cost <= int(budget * 0.05)
    assert out.verify_cost <= int(budget * 0.03)
    assert out.funded_cost <= budget - out.outreach_cost - out.verify_cost


def test_every_selection_survives_an_independent_audit():
    """Re-derive the constraints from the awards themselves, trusting nothing."""
    cands = [
        _cand(f"c{i}", cost=200_000 + (i % 7) * 90_000, priority=40 + (i % 50),
              benef=10_000 * (i % 30 + 1), sector=f"sec{i % 4}", group=f"g{i % 9}",
              deprived=(i % 3 == 0), unit=f"u{i}")
        for i in range(400)
    ]
    k = Constraints(budget=20_000_000, sector_cap_share=0.35, equity_floor_share=0.25,
                    min_groups=5, outreach_reserve_share=0.0, verify_reserve_share=0.0)
    out = allocate(cands, k)

    assert out.funded_cost <= 20_000_000
    by_sector: dict[str, int] = {}
    for a in out.funded:
        by_sector[a.candidate.sector] = by_sector.get(a.candidate.sector, 0) + a.cost
    for v in by_sector.values():
        assert v <= int(20_000_000 * 0.35)
    # One award per unit and sector.
    slots = [(a.candidate.unit_code, a.candidate.sector) for a in out.funded]
    assert len(slots) == len(set(slots))
    # Constraint flags must match reality.
    for c in out.constraints:
        if c.name == "sector_cap":
            assert c.satisfied is all(v <= int(20_000_000 * 0.35) for v in by_sector.values())


def test_solve_is_deterministic():
    cands = [_cand(f"c{i}", cost=300_000, priority=50 + (i % 33), benef=5_000 * (i % 20 + 1),
                   sector=f"s{i % 3}", group=f"g{i % 6}", unit=f"u{i}") for i in range(300)]
    k = Constraints(budget=9_000_000, outreach_reserve_share=0.0, verify_reserve_share=0.0)
    a = [x.candidate.candidate_id for x in allocate(cands, k).funded]
    b = [x.candidate.candidate_id for x in allocate(cands, k).funded]
    assert a == b


def test_one_visit_per_unit_and_sector_not_one_per_scheme():
    """Outreach and verification buy a visit to a place, not to a programme.

    Two competing schemes for the same district and sector produced two outreach
    entries, which sent two enumerators to ask the same village about the same
    schools and doubled the money reserved for it.
    """
    silent = [
        _cand("a", cost=500_000, priority=70, quad="silent_need", unit="u1", sector="education"),
        _cand("b", cost=900_000, priority=65, quad="silent_need", unit="u1", sector="education"),
    ]
    low = [
        _cand("c", cost=500_000, priority=70, conf=10.0, unit="u2", sector="health"),
        _cand("d", cost=900_000, priority=60, conf=10.0, unit="u2", sector="health"),
    ]
    out = allocate(silent + low, Constraints(budget=50_000_000))
    assert len(out.outreach) == 1
    assert len(out.verify) == 1
    # The stronger case is the one kept.
    assert out.outreach[0].candidate.candidate_id == "a"
    assert out.verify[0].candidate.candidate_id == "c"
    # The fold is disclosed, not silently discarded.
    assert any("Folded into one visit" in d.reason for d in out.dropped)


def test_constraints_carry_their_numbers_for_a_renderer():
    out = allocate([_cand("a", cost=1_000_000, priority=80, benef=40_000)],
                   Constraints(budget=5_000_000))
    by = {c.name: c for c in out.constraints}
    assert by["budget"].kind == "currency"
    assert by["budget"].value is not None and by["budget"].limit is not None
    assert by["geographic_spread"].kind == "count"
