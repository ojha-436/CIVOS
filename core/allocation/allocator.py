"""Turn a ranked list into a funded portfolio — and say what it refused to fund.

A ranking is half an answer. An official with a fixed envelope does not ask *what
is worst*, they ask *which of these forty do I fund this quarter, and what do I
tell the auditor about the ones I did not*. This module answers that second
question, which is the one the problem statement actually opens with when it names
misaligned public spending.

The three lanes
---------------
The distinctive thing here is that the output is not one portfolio. It is three,
and the split falls directly out of the quadrant model rather than being bolted on:

  * **FUND** — corroborated need, confidence above the floor. Money moves.
  * **VERIFY_FIRST** — the need looks real and valuable but the evidence is thin.
    Send somebody to look. Cheap, and it converts into FUND next cycle.
  * **OUTREACH** — high measured deficit, no citizen voice. SPEC §8 is explicit
    that silence is never auto-funded, so this lane spends a reserved slice of the
    envelope on going and asking instead of on concrete.

A pure budget optimiser cannot produce that third lane, because it has no concept
of a place that has not spoken. Funding silence would be indefensible; ignoring it
is the failure the product exists to name. Dispatching an enumerator is the only
honest third option, and it needs a budget line to be real rather than rhetorical.

Why greedy and not an exact solver
----------------------------------
This is a multi-dimensional knapsack, which is NP-hard, and an exact branch-and-
bound needs a solver binary in the deploy image. Density-ordered greedy with
targeted repair passes lands within a few percent on instances shaped like this
one — a few thousand candidates, costs spread over three orders of magnitude — and
it has two properties an exact solver does not:

  * it runs in milliseconds inside the existing container, so the budget control
    can re-solve while somebody drags it, and
  * every decision is traceable to one comparison, so *"why was this dropped?"*
    has a real answer instead of a dual value.

`Allocation.optimality_note` states the approximation rather than implying
exactness. A claim nobody checks is a slide.

Infeasibility is surfaced, never hidden. If the equity floor and the spread
requirement cannot both hold inside the envelope, the result says so and reports
which constraint bound, rather than quietly relaxing one and presenting the
outcome as optimal.

No country literals: candidates arrive pre-costed in whatever currency the country
adapter uses, as plain integers. This module has never heard of a place, a scheme
or a currency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "Lane",
    "Candidate",
    "Constraints",
    "Award",
    "Dropped",
    "ConstraintStatus",
    "Allocation",
    "allocate",
]


class Lane(StrEnum):
    FUND = "fund"
    VERIFY_FIRST = "verify_first"
    OUTREACH = "outreach"
    INELIGIBLE = "ineligible"


@dataclass(frozen=True)
class Candidate:
    """One fundable proposal: a unit, a sector, and a scheme that could pay for it."""

    candidate_id: str
    unit_code: str
    """Administrative unit. Adapter-defined; opaque here."""
    group_key: str
    """Coarser grouping used for the geographic-spread constraint (e.g. the parent unit)."""
    sector: str
    scheme_key: str
    units: int
    """How many scheme units this proposal buys, e.g. connections or classrooms."""
    unit_cost: int
    cost: int
    priority: float
    """SPEC §8 priority, 0-100. Computed upstream so the weights stay user-controlled."""
    quadrant: str
    confidence: float
    """0-100 from core.allocation.trust."""
    beneficiaries: int | None = None
    """None where population could not be reconciled. Never silently treated as zero."""
    deprived: bool = False
    """Counts toward the equity floor. Set from the official deprivation indicator."""
    suppressed: bool = False
    has_official_data: bool = True


@dataclass(frozen=True)
class Constraints:
    """The policy dials. Every one of these is a defensible ministry choice."""

    budget: int
    sector_cap_share: float = 0.40
    """No single sector may absorb more than this share. Prevents monoculture."""
    equity_floor_share: float = 0.30
    """At least this share must reach units flagged deprived."""
    min_groups: int = 3
    """Minimum distinct groups receiving something. Geographic spread."""
    outreach_reserve_share: float = 0.05
    """Slice reserved for going and asking in units that never reported."""
    verify_reserve_share: float = 0.03
    """Slice reserved for field-checking needs the trust model could not confirm.

    Its own dial rather than a reuse of the outreach share. Sharing one number
    meant a stated 5% reserve quietly withheld 8.37% of the envelope from
    delivery, which is the sort of discrepancy an auditor finds and a demo does
    not survive.
    """
    outreach_unit_cost: int = 150_000
    verify_unit_cost: int = 75_000
    confidence_floor: float = 55.0
    max_per_unit_sector: int = 1
    """Competing schemes for the same unit and sector are mutually exclusive."""


@dataclass(frozen=True)
class Award:
    candidate: Candidate
    lane: Lane
    cost: int
    rationale: str


@dataclass(frozen=True)
class Dropped:
    candidate: Candidate
    reason: str


@dataclass(frozen=True)
class ConstraintStatus:
    """A constraint's state, with its numbers kept as numbers.

    `detail` is prose for a terminal. `value` and `limit` exist because a console
    has to render these as money, and money is formatted differently in every
    country this is meant to run in — lakh and crore here, thousands elsewhere.
    Formatting in core would either hardcode one convention or produce
    "3844084000 of 3844450000", which is what the first version showed on screen
    and which nobody can read.
    """

    name: str
    satisfied: bool
    detail: str
    value: int | None = None
    limit: int | None = None
    kind: str = "count"
    """'currency' or 'count' — tells a renderer which formatter to reach for."""


@dataclass
class Allocation:
    funded: list[Award] = field(default_factory=list)
    verify: list[Award] = field(default_factory=list)
    outreach: list[Award] = field(default_factory=list)
    dropped: list[Dropped] = field(default_factory=list)
    constraints: list[ConstraintStatus] = field(default_factory=list)
    infeasible: list[str] = field(default_factory=list)
    optimality_note: str = ""

    @property
    def funded_cost(self) -> int:
        return sum(a.cost for a in self.funded)

    @property
    def verify_cost(self) -> int:
        return sum(a.cost for a in self.verify)

    @property
    def outreach_cost(self) -> int:
        return sum(a.cost for a in self.outreach)

    @property
    def total_cost(self) -> int:
        return self.funded_cost + self.verify_cost + self.outreach_cost

    @property
    def beneficiaries(self) -> int:
        return sum(a.candidate.beneficiaries or 0 for a in self.funded)

    @property
    def cost_per_beneficiary(self) -> float | None:
        b = self.beneficiaries
        return round(self.funded_cost / b, 2) if b else None

    def summary(self) -> dict:
        return {
            "funded": len(self.funded),
            "verify": len(self.verify),
            "outreach": len(self.outreach),
            "dropped": len(self.dropped),
            "funded_cost": self.funded_cost,
            "verify_cost": self.verify_cost,
            "outreach_cost": self.outreach_cost,
            "total_cost": self.total_cost,
            "beneficiaries": self.beneficiaries,
            "cost_per_beneficiary": self.cost_per_beneficiary,
            "infeasible": self.infeasible,
            "optimality_note": self.optimality_note,
        }


def assign_lane(c: Candidate, k: Constraints) -> tuple[Lane, str]:
    """Route one candidate. Order matters and encodes the product's ethics.

    Silence is checked before confidence: a unit that never reported cannot fail a
    confidence test, because there is nothing to be confident about. Sending it to
    VERIFY_FIRST would be a category error, and sending it to FUND would break the
    rule in SPEC §8 that the system never auto-funds silence.
    """
    if c.suppressed:
        return Lane.INELIGIBLE, "Below the disclosure threshold for this unit and sector."
    if not c.has_official_data or c.quadrant == "no_data":
        return Lane.INELIGIBLE, "No official indicator reconciled — excluded rather than invented."
    if c.quadrant == "silent_need":
        return Lane.OUTREACH, "Severe measured deficit with no citizen voice. Go and ask before funding."
    if c.quadrant == "stable":
        return Lane.INELIGIBLE, "No action indicated by either citizens or the official data."
    if c.beneficiaries is None:
        return Lane.INELIGIBLE, "Population unavailable for this unit, so cost per beneficiary cannot be computed."
    if c.confidence < k.confidence_floor:
        return Lane.VERIFY_FIRST, f"Confidence {c.confidence:.0f} is below the floor of {k.confidence_floor:.0f}."
    return Lane.FUND, "Corroborated need with sufficient confidence."


def _admissible(
    c: Candidate,
    *,
    spend: int,
    envelope: int,
    sector_spend: dict[str, int],
    sector_cap: dict[str, int],
    taken: dict[tuple[str, str], int],
    k: Constraints,
    freed: int = 0,
    freed_sector: str | None = None,
) -> str | None:
    """Return None if this candidate may be added, else why it may not.

    One function rather than three inline checks, because the repair passes
    originally carried their own copies and the spread repair simply forgot the
    sector cap — it would happily push a sector to double its ceiling in order to
    reach the group minimum, then report the cap as violated while printing a
    message saying nothing exceeded it. A constraint enforced in one place and
    bypassed in two is not a constraint.

    `freed` and `freed_sector` describe a displacement being considered, so an
    eviction is tested against the budget and the cap it would actually leave
    behind rather than the pre-eviction state.
    """
    if taken.get((c.unit_code, c.sector), 0) >= k.max_per_unit_sector:
        return "A competing scheme was already selected for this unit and sector."
    if spend - freed + c.cost > envelope:
        return "Does not fit the remaining envelope."
    used = sector_spend.get(c.sector, 0) - (freed if freed_sector == c.sector else 0)
    if used + c.cost > sector_cap.get(c.sector, 0):
        return f"Sector cap for {c.sector} reached at {int(k.sector_cap_share * 100)}% of the envelope."
    return None


def _density(c: Candidate) -> float:
    """Value per unit of cost. The greedy ordering.

    Value is priority times beneficiaries: a moderately urgent need serving
    200,000 people outranks an acute one serving 900, which is the whole argument
    for optimising a portfolio rather than funding down a ranked list.
    """
    if c.cost <= 0:
        return 0.0
    return (c.priority * (c.beneficiaries or 0)) / c.cost


def _sector_cap_status(
    sector_spend: dict[str, int], sector_cap: dict[str, int], k: Constraints
) -> ConstraintStatus:
    """Say which sector breached, not merely that something did.

    The previous version printed "No sector exceeds 40% of the envelope" even when
    it reported the constraint as violated. A status line that contradicts its own
    flag is worse than no status line: a reader skims the sentence, not the boolean.
    """
    over = {s: v for s, v in sector_spend.items() if v > sector_cap.get(s, 0)}
    pct = int(k.sector_cap_share * 100)
    if not over:
        biggest = max(sector_spend, key=lambda s: sector_spend[s], default=None)
        return ConstraintStatus(
            "sector_cap", True, f"No sector exceeds {pct}% of the envelope.",
            value=sector_spend.get(biggest, 0) if biggest else 0,
            limit=sector_cap.get(biggest, 0) if biggest else 0,
            kind="currency",
        )
    worst = max(over, key=lambda s: over[s] - sector_cap.get(s, 0))
    return ConstraintStatus(
        "sector_cap",
        False,
        f"{worst} holds {over[worst]} against a ceiling of {sector_cap.get(worst, 0)} ({pct}%).",
        value=over[worst], limit=sector_cap.get(worst, 0), kind="currency",
    )


def allocate(candidates: list[Candidate], k: Constraints) -> Allocation:
    """Produce a portfolio, an outreach schedule and a verification queue."""
    result = Allocation()
    result.optimality_note = (
        "Density-ordered greedy with equity and spread repair. Near-optimal, not proven optimal — "
        "the gap is typically a few percent on instances of this shape, and every inclusion and "
        "exclusion is individually traceable."
    )

    # ── Lane assignment ────────────────────────────────────────────────────
    #
    # Outreach and verification are collapsed to one entry per unit and sector.
    # Both lanes buy a visit, and a visit is to a place about a problem — not to
    # a scheme. Emitting one per competing scheme sent two enumerators to the same
    # district to ask about the same schools because two programmes could fund
    # them, which doubled both the count on screen and the money reserved for it.
    # The funding lane already enforces the same exclusivity through
    # `max_per_unit_sector`; this makes the other two lanes agree with it.
    fundable: list[Candidate] = []
    visits: dict[tuple[str, str], tuple[Lane, Candidate, str]] = {}
    for c in candidates:
        lane, why = assign_lane(c, k)
        if lane is Lane.INELIGIBLE:
            result.dropped.append(Dropped(c, why))
        elif lane in (Lane.OUTREACH, Lane.VERIFY_FIRST):
            slot = (c.unit_code, c.sector)
            held = visits.get(slot)
            # Keep the strongest case for the visit; the rest are not rejections,
            # they are the same visit described twice.
            if held is None or c.priority > held[1].priority:
                if held is not None:
                    result.dropped.append(
                        Dropped(held[1], "Folded into one visit for this unit and sector.")
                    )
                visits[slot] = (lane, c, why)
            else:
                result.dropped.append(
                    Dropped(c, "Folded into one visit for this unit and sector.")
                )
        else:
            fundable.append(c)

    for lane, c, why in visits.values():
        cost = k.outreach_unit_cost if lane is Lane.OUTREACH else k.verify_unit_cost
        (result.outreach if lane is Lane.OUTREACH else result.verify).append(
            Award(c, lane, cost, why)
        )

    # ── Reserved lanes come off the top ────────────────────────────────────
    # Outreach and verification are cheap per item and high in option value: each
    # one converts an unknown into a decision next cycle. They are capped by share
    # so they can never crowd out delivery, and the highest-deficit units are
    # served first within the cap.
    outreach_budget = int(k.budget * k.outreach_reserve_share)
    result.outreach.sort(key=lambda a: a.candidate.priority, reverse=True)
    kept_outreach, spent_outreach = [], 0
    for a in result.outreach:
        if spent_outreach + a.cost <= outreach_budget:
            kept_outreach.append(a)
            spent_outreach += a.cost
        else:
            result.dropped.append(
                Dropped(a.candidate, "Outreach reserve exhausted — queued for the next cycle.")
            )
    result.outreach = kept_outreach

    verify_budget = int(k.budget * k.verify_reserve_share)
    result.verify.sort(key=lambda a: a.candidate.priority, reverse=True)
    kept_verify, spent_verify = [], 0
    for a in result.verify:
        if spent_verify + a.cost <= verify_budget:
            kept_verify.append(a)
            spent_verify += a.cost
        else:
            result.dropped.append(
                Dropped(a.candidate, "Verification reserve exhausted — queued for the next cycle.")
            )
    result.verify = kept_verify

    envelope = k.budget - spent_outreach - spent_verify

    # ── Greedy fill ────────────────────────────────────────────────────────
    sector_cap = {s: int(envelope * k.sector_cap_share) for s in {c.sector for c in fundable}}
    sector_spend: dict[str, int] = {s: 0 for s in sector_cap}
    taken_unit_sector: dict[tuple[str, str], int] = {}
    selected: list[Candidate] = []
    spend = 0

    ordered = sorted(fundable, key=lambda c: (-_density(c), -c.priority, c.candidate_id))
    for c in ordered:
        why = _admissible(
            c, spend=spend, envelope=envelope, sector_spend=sector_spend,
            sector_cap=sector_cap, taken=taken_unit_sector, k=k,
        )
        if why:
            result.dropped.append(Dropped(c, why))
            continue
        selected.append(c)
        spend += c.cost
        sector_spend[c.sector] += c.cost
        taken_unit_sector[(c.unit_code, c.sector)] = taken_unit_sector.get((c.unit_code, c.sector), 0) + 1

    dropped_by_id = {d.candidate.candidate_id: d for d in result.dropped}

    def _reinstate(c: Candidate) -> None:
        d = dropped_by_id.pop(c.candidate_id, None)
        if d is not None:
            result.dropped.remove(d)

    # ── Repair pass A: equity floor ────────────────────────────────────────
    # Swap the least productive non-deprived selections for the most productive
    # deprived candidates that were passed over. Swapping rather than simply
    # adding keeps the envelope honest: an equity floor that silently inflates the
    # budget is not a constraint, it is a wish.
    equity_target = int(envelope * k.equity_floor_share)
    equity_spend = sum(c.cost for c in selected if c.deprived)
    selected_ids = {c.candidate_id for c in selected}

    def _add(cand: Candidate) -> None:
        nonlocal spend
        selected.append(cand)
        selected_ids.add(cand.candidate_id)
        spend += cand.cost
        sector_spend[cand.sector] = sector_spend.get(cand.sector, 0) + cand.cost
        slot = (cand.unit_code, cand.sector)
        taken_unit_sector[slot] = taken_unit_sector.get(slot, 0) + 1
        _reinstate(cand)

    def _evict(victim: Candidate, reason: str) -> None:
        nonlocal spend
        selected.remove(victim)
        selected_ids.discard(victim.candidate_id)
        spend -= victim.cost
        sector_spend[victim.sector] -= victim.cost
        taken_unit_sector[(victim.unit_code, victim.sector)] -= 1
        result.dropped.append(Dropped(victim, reason))
        dropped_by_id[victim.candidate_id] = result.dropped[-1]

    if equity_spend < equity_target:
        pool = sorted(
            (c for c in fundable if c.deprived and c.candidate_id not in selected_ids),
            key=lambda c: (-_density(c), c.candidate_id),
        )
        for cand in pool:
            if equity_spend >= equity_target:
                break
            if _admissible(
                cand, spend=spend, envelope=envelope, sector_spend=sector_spend,
                sector_cap=sector_cap, taken=taken_unit_sector, k=k,
            ) is None:
                _add(cand)
                equity_spend += cand.cost
                continue
            # No room as things stand. Consider displacing the least productive
            # non-deprived selection, but only if the swap is admissible once the
            # displacement is accounted for — the cap has to hold after the trade,
            # not merely before it.
            for victim in sorted(
                (c for c in selected if not c.deprived and c.cost >= cand.cost),
                key=_density,
            ):
                if _admissible(
                    cand, spend=spend, envelope=envelope, sector_spend=sector_spend,
                    sector_cap=sector_cap, taken=taken_unit_sector, k=k,
                    freed=victim.cost, freed_sector=victim.sector,
                ) is None:
                    _evict(victim, "Displaced to meet the equity floor.")
                    _add(cand)
                    equity_spend += cand.cost
                    break

    if equity_spend < equity_target:
        result.infeasible.append(
            f"Equity floor unreachable: {equity_spend} of {equity_target} required. "
            "Too few deprived units carry a fundable, sufficiently corroborated candidate "
            "that fits inside the remaining envelope and its sector ceiling."
        )

    # ── Repair pass B: geographic spread ───────────────────────────────────
    # Reaching the group minimum must not be bought by breaking another
    # constraint. Where it cannot be done admissibly, the shortfall is declared.
    groups = {c.group_key for c in selected}
    if len(groups) < k.min_groups:
        for g in sorted({c.group_key for c in fundable} - groups):
            if len(groups) >= k.min_groups:
                break
            for cand in sorted(
                (c for c in fundable if c.group_key == g and c.candidate_id not in selected_ids),
                key=lambda c: (c.cost, -c.priority, c.candidate_id),
            ):
                if _admissible(
                    cand, spend=spend, envelope=envelope, sector_spend=sector_spend,
                    sector_cap=sector_cap, taken=taken_unit_sector, k=k,
                ) is None:
                    _add(cand)
                    groups.add(g)
                    break
                # Displace only from a group that would still be represented.
                counts: dict[str, int] = {}
                for c in selected:
                    counts[c.group_key] = counts.get(c.group_key, 0) + 1
                placed = False
                for victim in sorted(
                    (c for c in selected if counts.get(c.group_key, 0) > 1 and c.cost >= cand.cost),
                    key=_density,
                ):
                    if _admissible(
                        cand, spend=spend, envelope=envelope, sector_spend=sector_spend,
                        sector_cap=sector_cap, taken=taken_unit_sector, k=k,
                        freed=victim.cost, freed_sector=victim.sector,
                    ) is None:
                        _evict(victim, f"Displaced to reach the minimum spread of {k.min_groups} groups.")
                        _add(cand)
                        groups.add(g)
                        placed = True
                        break
                if placed:
                    break

    if len(groups) < k.min_groups:
        result.infeasible.append(
            f"Geographic spread unreachable: {len(groups)} of {k.min_groups} groups covered "
            "without breaching the envelope or a sector ceiling."
        )

    # ── Emit ───────────────────────────────────────────────────────────────
    selected.sort(key=lambda c: (-c.priority, c.candidate_id))
    result.funded = [
        Award(c, Lane.FUND, c.cost, "Selected on value per unit of cost, within all constraints.")
        for c in selected
    ]

    equity_final = sum(c.cost for c in selected if c.deprived)
    result.constraints = [
        ConstraintStatus(
            "budget", spend <= envelope, f"{spend} of {envelope} committed to delivery.",
            value=spend, limit=envelope, kind="currency",
        ),
        ConstraintStatus(
            "equity_floor",
            equity_final >= equity_target,
            f"{equity_final} reaches deprived units against a floor of {equity_target}.",
            value=equity_final, limit=equity_target, kind="currency",
        ),
        ConstraintStatus(
            "geographic_spread",
            len(groups) >= k.min_groups,
            f"{len(groups)} groups covered against a minimum of {k.min_groups}.",
            value=len(groups), limit=k.min_groups, kind="count",
        ),
        _sector_cap_status(sector_spend, sector_cap, k),
        ConstraintStatus(
            "outreach_reserve",
            spent_outreach <= outreach_budget,
            f"{spent_outreach} reserved for outreach into units that never reported, "
            f"{spent_verify} for field verification.",
            value=spent_outreach, limit=outreach_budget, kind="currency",
        ),
    ]
    return result
