"""Turn scored rows into fundable candidates — the country-aware half.

`core/allocation/` knows about costs and constraints and has never heard of a
place. This module is where a water deficit in a particular district meets the
particular named scheme that can pay for it, at a published unit cost. That split
is what keeps the cross-border claim true: a second country needs a new
`adapters/<iso>/schemes.yaml`, not a new optimiser.

It lives under `api/` rather than `scripts/` because `/allocate` needs it at
request time. A runtime endpoint importing from a build-time script would work
today (the image copies the whole tree) and break the first time somebody
tightened .dockerignore, which is the kind of failure that only shows up in
production.

Where the trust inputs come from
--------------------------------
`core.allocation.trust` wants six numbers per need. Four are already in the
fixture and two are deliberately left at zero rather than invented:

  * `total_reports`       <- `signals`. Real field.
  * `distinct_submitters` <- `needs`, the post-dedup cluster count. A genuine
    **lower bound**: embedding dedup collapses repeats, so the cluster count is at
    most the number of distinct people who raised something. It also makes
    `independence` equal the dedup ratio, which is already exactly the quantity
    "how much of this volume is one thing said twice".
  * `image_backed`        <- `images`. Real field.
  * `deficit_pct`         <- `deficit`. **Real survey data.**
  * `reused_images`       <- 0. Perceptual-hash reuse detection is implemented in
    the model, but the synthetic corpus contains no recycled photographs, so the
    honest reading is zero rather than a number chosen to make the feature look
    busy. The live path populates it.
  * `burst_share`         <- 0.0. Needs per-report timestamps, which the
    aggregated fixture does not carry. Absent, not fabricated.

Both zeros travel in the output provenance so nobody reads a clean trust score as
a verified one.

Counting beneficiaries
----------------------
A project is credited with `units x beneficiaries_per_unit`, **capped** at the
population the official indicator says is actually deprived. Both halves matter.
Without the first, forty-seven tap connections were credited with the whole
district and cost-per-beneficiary came out roughly ten times too good. Without the
cap, a large scheme in a small district could claim to serve more people than live
there. The per-unit figures and their published norms are in the country adapter.

Scheme eligibility
------------------
A scheme is proposed only where its published scope overlaps the population the
sector's indicator is computed over. Without this the allocator matched on sector
alone and proposed **AMRUT 2.0** — a statutory-town programme — for Karbi Anglong,
Dima Hasao and Dhemaji, rural hill districts. The eligibility clause had been
sitting in `schemes.yaml` as prose nothing could read; it is now `applies_to`,
checked against the sector's `measures`.

The consequence is deliberate and worth stating plainly: the roads indicator is the
Census Village Directory, which counts **villages and has no urban universe at
all**. So no urban roads scheme can be justified anywhere in the country from the
data this build carries, and AMRUT therefore proposes zero projects. That is the
correct answer to the question being asked rather than a gap, and it travels in the
output provenance instead of being left for a reader to notice.

Deprivation flag
----------------
The equity floor needs to know which units are deprived. This takes the **upper
tercile of the real deficit distribution within each sector**, so "deprived" means
measurably worse off than two thirds of the country on the indicator that sector
is scored by, and the cut moves with the data instead of being a magic constant.
"""

from __future__ import annotations

from core.allocation import Candidate, assess
from core.allocation.trust import TrustSignals

# SPEC §8 defaults, mirroring console/lib/scoring.ts DEFAULT_WEIGHTS. Kept in step
# by tests/test_allocation_fixture.py so the console and the allocator can never
# silently disagree about what a priority score is.
DEFAULT_WEIGHTS = {"w1": 0.3, "w2": 0.3, "w3": 0.25, "w4": 0.05, "w5": 0.1}

# Mirrors costBand() in console/lib/scoring.ts. Not every reported need becomes a
# funded unit — some are duplicates of the same asset, some are already in another
# programme — so the buildable share is below one and stated rather than implied.
BUILDABLE_SHARE = 0.6


def priority(row: dict, w: dict[str, float]) -> float:
    """SPEC §8, adjusted mode. Identical to the browser implementation."""
    return (
        w["w1"] * row["adjusted_demand"]
        + w["w2"] * row["deficit"]
        + w["w3"] * max(row["silence_gap"], 0.0)
        + w["w4"] * max(row["forecast"], 0.0)
        + w["w5"] * row["evidence"]
    )


def trust_for(row: dict) -> object:
    severities = [a["severity"] for a in row.get("assets", [])]
    return assess(
        TrustSignals(
            total_reports=row["signals"],
            distinct_submitters=row["needs"],
            image_backed=row["images"],
            geo_verified=0,
            reused_images=0,
            burst_share=0.0,
            deficit_pct=row["deficit"] if row["has_deficit"] else None,
            mean_severity=sum(severities) / len(severities) if severities else 3.0,
        )
    )


def eligible(scheme: dict, sector: dict) -> bool:
    """May this scheme pay for a need measured by this sector's indicator?

    Overlap, not equality: a rural scheme against an indicator covering both
    settlements is fine, because the rural half of that measurement is real need
    the scheme can serve. An urban scheme against a rural-only indicator is not,
    because nothing in the measurement evidences an urban problem.

    A missing field is treated as unrestricted rather than as an error, so an
    adapter for a country that does not draw this distinction keeps working.
    """
    scope = scheme.get("applies_to", "both")
    measured = sector.get("measures", "both")
    if scope == "both" or measured == "both":
        return True
    return scope == measured


def build_candidates(data: dict, weights: dict[str, float]) -> list[Candidate]:
    districts = {d["code"]: d for d in data["districts"]}
    sectors = {s["key"]: s for s in data["sectors"]}

    # Upper-tercile deficit cut, per sector, over rows carrying a real value.
    cuts: dict[str, float] = {}
    for key in sectors:
        vals = sorted(r["deficit"] for r in data["rows"] if r["sector"] == key and r["has_deficit"])
        cuts[key] = vals[int(len(vals) * 2 / 3)] if vals else 0.0

    out: list[Candidate] = []
    for row in data["rows"]:
        sector = sectors.get(row["sector"])
        district = districts.get(row["code"])
        if sector is None or district is None:
            continue

        t = trust_for(row)
        pri = round(priority(row, weights), 2)
        pop = district.get("population")
        # The population the indicator says is actually deprived — the ceiling on
        # what any project here could possibly serve.
        affected = int(pop * row["deficit"] / 100.0) if pop else None
        units = max(1, round(row["needs"] * BUILDABLE_SHARE))
        deprived = row["has_deficit"] and row["deficit"] >= cuts[row["sector"]]

        for scheme in sector["schemes"]:
            if not eligible(scheme, sector):
                continue
            cost = units * int(scheme["unit_cost_inr"])
            # Beneficiaries are what the funded units reach, capped by the
            # deprived population. Crediting a project with the whole district
            # was the bug that made cost-per-beneficiary look ten times better
            # than it is; the cap is what keeps the headline number defensible.
            reach = units * int(scheme["beneficiaries_per_unit"])
            benef = min(reach, affected) if affected is not None else None
            out.append(
                Candidate(
                    candidate_id=f"{row['code']}|{row['sector']}|{scheme['name']}",
                    unit_code=row["code"],
                    group_key=district["state"],
                    sector=row["sector"],
                    scheme_key=scheme["name"],
                    units=units,
                    unit_cost=int(scheme["unit_cost_inr"]),
                    cost=cost,
                    priority=pri,
                    quadrant=row["quadrant"],
                    confidence=t.confidence,
                    beneficiaries=benef,
                    deprived=deprived,
                    suppressed=row["suppressed"],
                    has_official_data=row["has_deficit"],
                )
            )
    return out
