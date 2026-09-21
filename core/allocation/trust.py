"""How much a reported need can be relied on — and what that may never be used for.

The question this module answers is the first one any official asks: *how do you
know these complaints are genuine?* The honest answer is that you cannot know, so
this does not return a verdict. It returns a **confidence** with named components,
each of which a reader can inspect and argue with.

Two rules govern the design, and both exist to stop a verification layer from
quietly becoming a gatekeeping layer.

1. **Absence of evidence is not evidence of absence.** A district where nobody
   owns a camera must not be punished twice — once by having no photographs, and
   again by scoring badly for having none. This is the same reasoning that pinned
   `w5` (evidence strength) to the smallest weight in SPEC §8. So the evidence
   component here is *additive upside*, never a multiplier that can zero a score,
   and `CONFIDENCE_WEIGHTS` keeps it small. A text-only report corroborated by
   nine neighbours in a measurably deprived unit reaches a usable confidence with
   no photograph at all, and there is a test that pins exactly that.

2. **Confidence changes the lane, never the record.** Nothing here can stop a
   citizen being heard. A low-confidence need is still stored, still counted, and
   still surfaced — it is routed to `VERIFY_FIRST` so somebody goes and looks,
   rather than being deleted or hidden. A system that silently drops the reports
   it distrusts would reproduce, in software, exactly the bias the product exists
   to correct.

What is actually detectable
---------------------------
Fraud in citizen reporting is mostly not elaborate. It is four things:

  * **One person filing many times** — inflates volume with no new information.
    Caught by `independence`: distinct submitters over total reports.
  * **A coordinated burst** — an organised push that looks like demand. Caught by
    `timing`, which reads the share of reports landing in the tightest window, and
    by log-capping corroboration so the hundredth report adds almost nothing.
  * **A recycled photograph** — the same pothole image attached to fifty reports,
    often from different places. Caught by `integrity`, fed by perceptual-hash
    collisions computed upstream.
  * **A claim the measured world contradicts** — reports of total absence in a
    unit whose official deficit is near zero. Caught by `plausibility`.

The fourth deserves care. A mismatch between what citizens say and what the
official data records is *not* presumed to be a lie. It is exactly the
`expectation_gap` quadrant, where the likeliest explanation is that the official
dataset is stale. So plausibility is deliberately gentle and asymmetric: it never
falls below `PLAUSIBILITY_FLOOR`, because the alternative is a product that tells
a government its own out-of-date spreadsheet outranks its citizens.

What this cannot do
-------------------
It cannot detect a careful, distributed, patient fabrication by several people
with real cameras in a genuinely deprived place. Nothing short of a field visit
can, which is precisely why `VERIFY_FIRST` exists as a destination rather than a
failure state. Stated here, and stated on screen, because a limit disclosed is
worth more than a limit discovered by an evaluator.

No country literals: this module knows about counts, ratios and time. It has
never heard of a place.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

# ── Tunables, all in one place so a reviewer can see the whole policy ───────
#
# Corroboration saturates: the difference between one report and six is large,
# between sixty and six hundred is nearly nothing. Log-capping is what stops a
# brigade out-shouting a village.
CORROBORATION_CAP = 25

# Below this share of distinct submitters, volume is one voice repeating itself.
INDEPENDENCE_FLOOR = 0.25

# A burst this concentrated is a campaign, not a coincidence.
BURST_CEILING = 0.80

# Plausibility never bottoms out — see the module note on expectation_gap.
PLAUSIBILITY_FLOOR = 0.35

# Component weights. Evidence is deliberately the smallest positive term, for the
# same reason w5 is smallest in SPEC §8. Corroboration and independence carry the
# most because they are the hardest to fake cheaply.
CONFIDENCE_WEIGHTS: dict[str, float] = {
    "corroboration": 0.30,
    "independence": 0.25,
    "plausibility": 0.20,
    "timing": 0.15,
    "evidence": 0.10,
}

# Needs scoring below this are routed to verification rather than funding.
DEFAULT_CONFIDENCE_FLOOR = 55.0


class TrustFlag(StrEnum):
    """A specific, nameable reason to look closer. Never a reason to delete."""

    SINGLE_SUBMITTER = "single_submitter"
    """Volume is one person reporting repeatedly."""

    COORDINATED_BURST = "coordinated_burst"
    """Reports concentrated into a window too tight to be independent."""

    RECYCLED_IMAGERY = "recycled_imagery"
    """Every photograph matched one already seen elsewhere."""

    CONTRADICTS_MEASURED = "contradicts_measured"
    """Severe claims where the official indicator records almost no deficit."""

    UNVERIFIED_LOCATION = "unverified_location"
    """No report in the cluster had its coordinates containment-tested."""


@dataclass(frozen=True)
class TrustSignals:
    """The inputs the model reads. Counts and ratios only — never identities.

    Everything here is derivable from `NormalisedSignal` rows already persisted.
    `distinct_submitters` comes from the salted `submitter_hash`, which is why the
    hash exists at all: it permits counting people without knowing any of them.
    """

    total_reports: int
    distinct_submitters: int
    image_backed: int = 0
    geo_verified: int = 0
    reused_images: int = 0
    burst_share: float = 0.0
    """Share of reports arriving inside the tightest 24-hour window, 0-1."""
    deficit_pct: float | None = None
    """Official measured deficit for this unit and sector. None where unreconciled."""
    mean_severity: float = 3.0
    """Mean citizen-assigned severity, 1-5."""


@dataclass(frozen=True)
class TrustAssessment:
    """A confidence with its working shown. Every field appears in the dossier."""

    confidence: float
    components: dict[str, float]
    flags: list[TrustFlag] = field(default_factory=list)
    review_required: bool = False
    note: str = ""

    @property
    def is_confident(self) -> bool:
        return not self.review_required


def _corroboration(s: TrustSignals) -> float:
    """Log-capped distinct-submitter count.

    Distinct submitters, not reports: ten people saying it once is stronger
    evidence than one person saying it ten times, and the arithmetic should say so.
    """
    if s.distinct_submitters <= 0:
        return 0.0
    return min(1.0, math.log1p(s.distinct_submitters) / math.log1p(CORROBORATION_CAP))


def _independence(s: TrustSignals) -> float:
    """Distinct submitters over total reports.

    A cluster of 50 reports from 2 people scores 0.04 here. A cluster of 6 reports
    from 6 people scores 1.0. This is the single cheapest defence against the most
    common form of inflation.
    """
    if s.total_reports <= 0:
        return 0.0
    return min(1.0, s.distinct_submitters / s.total_reports)


def _evidence(s: TrustSignals) -> float:
    """Photographic backing, with verified coordinates counting for more.

    Additive upside only. Its weight is small by design, and the tests pin the
    case where a camera-less district still clears the floor on corroboration.
    """
    if s.total_reports <= 0:
        return 0.0
    usable = max(0, s.image_backed - s.reused_images)
    photo = usable / s.total_reports
    located = s.geo_verified / s.total_reports
    return min(1.0, 0.6 * photo + 0.4 * located)


def _integrity(s: TrustSignals) -> float:
    """Share of submitted photographs that were not already seen elsewhere.

    Returns 1.0 when there are no photographs at all — having submitted nothing is
    not the same as having submitted something fake, and conflating the two is how
    a verification layer starts penalising poverty.
    """
    if s.image_backed <= 0:
        return 1.0
    return max(0.0, 1.0 - s.reused_images / s.image_backed)


def _timing(s: TrustSignals) -> float:
    """Inverse of burst concentration.

    Genuine need accumulates. A campaign arrives. Below the ceiling this returns
    1.0, because ordinary clustering after a monsoon or a breakdown is expected
    and must not be treated as suspicious.
    """
    if s.burst_share <= BURST_CEILING:
        return 1.0
    over = (s.burst_share - BURST_CEILING) / max(1e-9, 1.0 - BURST_CEILING)
    return max(0.0, 1.0 - over)


def _plausibility(s: TrustSignals) -> float:
    """Consistency of the claim with the official indicator, held gently.

    Returns a neutral 0.75 where no official value reconciled — absent data is not
    a mark against the citizen. Never falls below PLAUSIBILITY_FLOOR, because a
    citizen contradicting a stale dataset is a documented product finding
    (`expectation_gap`), not a suspected lie.
    """
    if s.deficit_pct is None:
        return 0.75
    # Severity 1-5 mapped to the deficit share a claim implies, then compared.
    claimed = (max(1.0, min(5.0, s.mean_severity)) - 1.0) / 4.0
    measured = max(0.0, min(1.0, s.deficit_pct / 100.0))
    gap = claimed - measured
    if gap <= 0:
        # Citizens claim less than the data records. Never suspicious.
        return 1.0
    return max(PLAUSIBILITY_FLOOR, 1.0 - gap)


def assess(
    signals: TrustSignals, *, confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR
) -> TrustAssessment:
    """Score one clustered need, and say plainly what would need checking."""
    components = {
        "corroboration": _corroboration(signals),
        "independence": _independence(signals),
        "evidence": _evidence(signals),
        "plausibility": _plausibility(signals),
        "timing": _timing(signals),
    }

    # Integrity multiplies rather than adds, because recycled imagery is the one
    # input that actively misleads. Everything else is merely absent.
    base = sum(CONFIDENCE_WEIGHTS[k] * v for k, v in components.items() if k in CONFIDENCE_WEIGHTS)
    integrity = _integrity(signals)
    components["integrity"] = integrity
    confidence = round(100.0 * base * integrity, 1)

    flags: list[TrustFlag] = []
    if components["independence"] < INDEPENDENCE_FLOOR and signals.total_reports >= 3:
        flags.append(TrustFlag.SINGLE_SUBMITTER)
    if signals.burst_share > BURST_CEILING and signals.total_reports >= 5:
        flags.append(TrustFlag.COORDINATED_BURST)
    if signals.image_backed > 0 and signals.reused_images >= signals.image_backed:
        flags.append(TrustFlag.RECYCLED_IMAGERY)
    if components["plausibility"] <= PLAUSIBILITY_FLOOR:
        flags.append(TrustFlag.CONTRADICTS_MEASURED)
    if signals.geo_verified == 0 and signals.total_reports > 0:
        flags.append(TrustFlag.UNVERIFIED_LOCATION)

    # UNVERIFIED_LOCATION alone never forces review. Most citizens submit by voice
    # from a feature phone and will never have EXIF coordinates; treating that as
    # grounds for suspicion would route the entire population this product was
    # built to reach into a verification queue.
    hard = [f for f in flags if f is not TrustFlag.UNVERIFIED_LOCATION]
    review_required = confidence < confidence_floor or bool(hard)

    note = (
        "Confidence reflects corroboration, independence and consistency with official data. "
        "It is not proof. Needs below the floor are routed for field verification, never discarded."
    )
    return TrustAssessment(
        confidence=confidence,
        components={k: round(v, 3) for k, v in components.items()},
        flags=flags,
        review_required=review_required,
        note=note,
    )
