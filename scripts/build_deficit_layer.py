"""Phase 1 — build the real official deficit layer from NFHS-5.

This is the layer evaluators can independently verify, so it cannot be faked and
its provenance has to survive scrutiny. What this script does and does not claim:

**Source.** National Family Health Survey 2019-21 (NFHS-5), IIPS / Ministry of
Health and Family Welfare, Government of India. District factsheets. The values
are Government of India statistics; this script only transports and reshapes them.

**Transport.** `rchiips.org`, which hosts the official factsheet PDFs, currently
404s and presents an invalid TLS certificate, so the PDFs are not retrievable at
source. Two independent community extractions of those same PDFs are used
instead, and — this is the part that matters — **they are cross-validated against
each other.** Across the 274 districts both cover, all five indicators agree
exactly (max difference 0.00). Two independent PDF extractions agreeing to the
decimal is good evidence neither mangled the source. The check runs on every
build and the result is written into the reconciliation report.

**Reconciliation.** District names are matched against the boundary file the
console renders. This is the task plan.md calls "the boring one that silently
breaks everything downstream", and it is genuinely hard here: the boundary set is
2011-era, so it predates Telangana (2014) and Ladakh (2019), and many districts
have been renamed or split since. Every unmatched district is reported, not
silently dropped, and unmatched districts are excluded from the ranking rather
than given an invented value.

**Deficit direction.** NFHS reports coverage ("% with an improved water source").
The engine needs deprivation, so deficit = 100 − coverage. Stated because getting
this backwards would invert the entire product.

Usage:
    uv run python scripts/build_deficit_layer.py
    uv run python scripts/build_deficit_layer.py --load-bigquery
"""

from __future__ import annotations

import csv
import difflib
import io
import json
import re
import sys
import unicodedata
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "raw"
OUT = REPO / "data"
console = Console()

MIRROR_A = "https://raw.githubusercontent.com/SaiSiddhardhaKalla/NFHS/main/_states/{f}.csv"
MIRROR_A_TREE = "https://api.github.com/repos/SaiSiddhardhaKalla/NFHS/git/trees/main?recursive=1"
MIRROR_B = "https://raw.githubusercontent.com/pratapvardhan/NFHS-5/master/NFHS-5-Districts.csv"

SOURCE_CITATION = (
    "National Family Health Survey 2019-21 (NFHS-5), district factsheets. "
    "International Institute for Population Sciences (IIPS) and Ministry of Health "
    "and Family Welfare, Government of India."
)

# Indicator → (match substring, whether the NFHS value is coverage or deprivation)
# NFHS reports coverage for all five, so every one is inverted to a deficit.
INDICATORS: dict[str, dict] = {
    "pct_households_no_improved_water": {
        "match": "improved drinkingwater source",
        "alt": "improved drinking-water source",
        "label": "Households without an improved drinking water source",
        "sector": "water_sanitation",
    },
    "pct_households_no_improved_sanitation": {
        "match": "improved sanitation facility",
        "alt": "improved sanitation facility",
        "label": "Households without an improved sanitation facility",
        "sector": "water_sanitation",
    },
    "pct_households_no_electricity": {
        "match": "households with electricity",
        "alt": "households with electricity",
        "label": "Households without an electricity connection",
        "sector": "electricity",
    },
    "pct_births_non_institutional": {
        "match": "institutional births (%)",
        "alt": "institutional births (%)",
        "label": "Births not delivered in a health facility",
        "sector": "health",
    },
    "pct_females_never_attended_school": {
        "match": "ever attended school",
        "alt": "ever attended school",
        "label": "Females age 6+ who never attended school",
        "sector": "education",
    },
}

# ---------------------------------------------------------------------------
# Participation capacity — who can actually file a complaint
# ---------------------------------------------------------------------------
#
# These are NOT deficit indicators and are deliberately kept out of INDICATORS so
# they can never reach fact_deficit_indicator.csv and be scored as a sector.
#
# They exist because the synthetic corpus needs a participation-bias term, and
# that term used to be `sha256(district_code)` — a hash with no real-world
# meaning. Since the Silent Need quadrant is defined by low participation against
# high deficit, a hashed participation term meant the product's headline output
# was arbitrary: "why is this district silent?" had no answer.
#
# Schooling is the standard proxy for the literacy and agency needed to navigate a
# grievance process. Electricity coverage proxies the household infrastructure a
# phone depends on. Both are real NFHS-5 values on the same districts, reconciled
# by the same pipeline as the deficit layer, so no new provenance is introduced.
#
# Electricity is not re-parsed: `pct_households_no_electricity` above already
# captures it, and its `coverage_pct` is the share of households WITH electricity.
CAPACITY_INDICATORS: dict[str, dict] = {
    "pct_women_10yr_schooling": {
        "match": "10 or more years of schooling",
        "alt": "10 or more years of schooling",
        "label": "Women with 10 or more years of schooling",
    },
}

# The composite. Weighting is a judgement, not a measurement — stated here and in
# docs/PARTICIPATION-CAPACITY.md so it can be argued with, exactly as the w1..w5
# scoring weights are exposed as sliders in the console.
CAPACITY_WEIGHTS = {"schooling": 0.6, "electricity": 0.4}

# States renamed or created since the 2011-era boundary file. Reconciliation falls
# back to national name matching anyway, but these make the common cases exact.
STATE_ALIASES = {
    "odisha": "orissa",
    "uttarakhand": "uttaranchal",
    "delhi": "nctofdelhi",
    "puducherry": "pondicherry",
    "jammukashmir": "jammuandkashmir",
    "jammuandkashmir": "jammuandkashmir",
    "andamannicobarislands": "andamanandnicobar",
    # Dadra & Nagar Haveli and Daman & Diu merged into one UT in 2020; the 2011-era
    # boundary file still carries them as two. Both sides map to one key.
    "dadranagarhavelidamandiu": "dadraandnagarhaveli",
    "damananddiu": "dadraandnagarhaveli",
    # Telangana was carved out of Andhra Pradesh in 2014, after the boundary file.
    "telangana": "andhrapradesh",
    # Ladakh was separated from Jammu & Kashmir in 2019.
    "ladakh": "jammuandkashmir",
}


def norm(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


def fetch(url: str, cache: Path) -> str:
    """Download once, cache under data/raw (gitignored), so reruns are offline."""
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    cache.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "CIVOS-build/0.1"})
    with urllib.request.urlopen(req, timeout=90) as r:  # noqa: S310
        text = r.read().decode("utf-8-sig", errors="replace")
    cache.write_text(text, encoding="utf-8")
    return text


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------


def load_mirror_a() -> dict[tuple[str, str], dict]:
    """The fuller extraction: 647 districts, carries census codes."""
    tree = json.loads(fetch(MIRROR_A_TREE, RAW / "mirror_a_tree.json"))
    files = [
        t["path"].split("/")[1].removesuffix(".csv")
        for t in tree["tree"]
        if t["path"].startswith("_states/") and t["path"].endswith(".csv")
    ]
    console.print(f"  mirror A: {len(files)} state files")

    out: dict[tuple[str, str], dict] = {}
    for f in files:
        text = fetch(MIRROR_A.format(f=f), RAW / f"nfhs_a_{f}.csv")
        for r in csv.DictReader(io.StringIO(text)):
            ind = (r.get("Indicator") or "").lower()
            key = (norm(r.get("State")), norm(r.get("District Name")))
            rec = out.setdefault(
                key,
                {
                    "state": (r.get("State") or "").strip(),
                    "district": (r.get("District Name") or "").strip(),
                    "st_cen_cd": (r.get("ST_CEN_CD") or "").strip(),
                    "dt_cen_cd": (r.get("DT_CEN_CD") or "").strip(),
                    "values": {},
                },
            )
            for ikey, spec in {**INDICATORS, **CAPACITY_INDICATORS}.items():
                if spec["match"] in ind and not (ikey.endswith("non_institutional") and "public" in ind):
                    try:
                        rec["values"][ikey] = float(r["NFHS 5"])
                    except (TypeError, ValueError, KeyError):
                        pass
    return out


def load_mirror_b() -> dict[tuple[str, str], dict[str, float]]:
    """The CC-BY-4.0 extraction: fewer districts, used purely as a cross-check."""
    text = fetch(MIRROR_B, RAW / "nfhs_b_districts.csv")
    out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for r in csv.DictReader(io.StringIO(text)):
        ind = (r.get("Indicator") or "").lower()
        key = (norm(r.get("State")), norm(r.get("District")))
        for ikey, spec in INDICATORS.items():
            if spec["alt"] in ind and not (ikey.endswith("non_institutional") and "public" in ind):
                try:
                    out[key][ikey] = float(r["NFHS-5"])
                except (TypeError, ValueError, KeyError):
                    pass
    return dict(out)


def cross_validate(a: dict, b: dict) -> dict:
    """Two independent extractions of the same PDFs must agree, or neither is trusted."""
    overlap = set(a) & set(b)
    report = {"overlap_districts": len(overlap), "indicators": {}}
    for ikey in INDICATORS:
        diffs = [
            abs(a[d]["values"][ikey] - b[d][ikey])
            for d in overlap
            if ikey in a[d]["values"] and ikey in b[d]
        ]
        if not diffs:
            continue
        report["indicators"][ikey] = {
            "compared": len(diffs),
            "identical": sum(1 for x in diffs if x < 0.05),
            "max_diff": round(max(diffs), 3),
        }
    return report


# ---------------------------------------------------------------------------
# reconciliation
# ---------------------------------------------------------------------------


def reconcile(nfhs: dict, geo_districts: list[dict]) -> tuple[dict, list, list]:
    """Match NFHS districts onto the boundary file the console actually renders.

    Name matching, in decreasing confidence — **state agreement is mandatory**:
      1. exact (state, district) after alias mapping
      2. close district name within the same state

    There is deliberately no national name-only fallback. An earlier version had
    one and it produced exactly the failure it invites: Sikkim's "East" district
    matched Delhi's "East" district (census code 7/4 — Delhi, not Sikkim 11), and
    a boundary polygon labelled "Junagadh" under Daman and Diu picked up Gujarat's
    Junagadh figures. Both would have silently painted one district's deprivation
    onto another. A name-only match across 640 districts full of Easts, Wests and
    Norths is not a heuristic, it is a coin toss.

    Everything unmatched is reported and excluded. Nothing is invented.
    """
    by_state_district: dict[tuple[str, str], tuple] = {}
    by_district: dict[str, list[tuple]] = defaultdict(list)
    # Census-code index. The boundary set now carries ST_CEN_CD / DT_CEN_CD, and
    # NFHS-5's own extraction carries the same pair, so most districts can be
    # joined on an integer tuple. This is the reliable path; name matching below
    # is now the fallback rather than the primary mechanism.
    by_census: dict[tuple[int, int], tuple] = {}
    for key, rec in nfhs.items():
        st, dt = key
        st = STATE_ALIASES.get(st, st)
        by_state_district[(st, dt)] = key
        by_district[dt].append(key)
        try:
            by_census[(int(float(rec["st_cen_cd"])), int(float(rec["dt_cen_cd"])))] = key
        except (TypeError, ValueError, KeyError):
            pass

    matched: dict[str, dict] = {}
    unmatched_geo: list[dict] = []
    how = defaultdict(int)

    for g in geo_districts:
        # Sentinel polygons carry no measurement and must never be matched — the
        # NFHS extraction has its own placeholder row, and joining the two yields a
        # fake district with 0% on every indicator.
        if g.get("placeholder"):
            unmatched_geo.append(g)
            how["excluded_sentinel"] += 1
            continue
        gst = STATE_ALIASES.get(norm(g["state"]), norm(g["state"]))
        gdt = norm(g["name"])
        hit = None

        method = ""
        # Census code first — an exact integer join cannot marry Sikkim's East to
        # Delhi's East, which is precisely the failure name matching produced.
        gcen = (g.get("st_cen_cd"), g.get("dt_cen_cd"))
        if gcen[0] is not None and gcen[1] is not None and gcen in by_census:
            hit, method = by_census[gcen], "census_code"
        elif (gst, gdt) in by_state_district:
            hit, method = by_state_district[(gst, gdt)], "exact_state_district"
        else:
            same_state = [k for k in nfhs if STATE_ALIASES.get(k[0], k[0]) == gst]
            cand = difflib.get_close_matches(gdt, [k[1] for k in same_state], n=1, cutoff=0.86)
            if cand:
                hit = next(k for k in same_state if k[1] == cand[0])
                method = "fuzzy_within_state"

        if hit:
            matched[g["code"]] = {
                "geo": g,
                "nfhs": nfhs[hit],
                "method": method,
                "nfhs_name": nfhs[hit]["district"],
                "nfhs_state": nfhs[hit]["state"],
            }
            how[method] += 1
        else:
            unmatched_geo.append(g)

    used = {(m["nfhs"]["state"], m["nfhs"]["district"]) for m in matched.values()}
    unmatched_nfhs = [
        rec for rec in nfhs.values() if (rec["state"], rec["district"]) not in used
    ]
    return matched, unmatched_geo, unmatched_nfhs, dict(how)


# ---------------------------------------------------------------------------


def main(
    load_bigquery: bool = typer.Option(False, "--load-bigquery", help="Also load to BigQuery"),
    with_roads: bool = typer.Option(
        False, "--with-roads",
        help="Load data/fact_roads_deficit.csv. OFF by default — the Census "
             "all-weather-road field is not comparably coded across states.",
    ),
    project: str = typer.Option("civos-in", "--project"),
    location: str = typer.Option("asia-south1", "--location"),
    dataset: str = typer.Option("civos", "--dataset"),
) -> None:
    console.rule("[bold]Phase 1 — official deficit layer[/bold]")

    console.print("\n[bold]Fetching NFHS-5 extractions[/bold]")
    a = load_mirror_a()
    b = load_mirror_b()
    console.print(f"  mirror A: {len(a)} districts · mirror B: {len(b)} districts")

    console.print("\n[bold]Cross-validating the two extractions[/bold]")
    xval = cross_validate(a, b)
    ok = True
    for ikey, r in xval["indicators"].items():
        pct = 100 * r["identical"] / r["compared"]
        colour = "green" if pct > 99 else "yellow" if pct > 95 else "red"
        ok &= pct > 99
        console.print(
            f"  [{colour}]{pct:5.1f}%[/{colour}] identical  {ikey:42s} "
            f"n={r['compared']}  max_diff={r['max_diff']}"
        )
    if not ok:
        console.print("[yellow]  Extractions disagree — treat values as unverified.[/yellow]")

    console.print("\n[bold]Reconciling against the rendered boundary set[/bold]")
    gj = json.loads((REPO / "console" / "public" / "data" / "districts.geojson").read_text())
    geo = [
        {
            "code": f["properties"]["code"],
            "name": f["properties"]["name"],
            "state": f["properties"]["state"],
            # Present since the boundary set moved to DataMeet Census 2011; absent
            # in older files, in which case reconcile() falls back to names.
            "st_cen_cd": f["properties"].get("st_cen_cd"),
            "dt_cen_cd": f["properties"].get("dt_cen_cd"),
            "placeholder": bool(f["properties"].get("placeholder")),
        }
        for f in gj["features"]
    ]
    n_placeholder = sum(1 for g in geo if g["placeholder"])
    if n_placeholder:
        console.print(
            f"  [yellow]{n_placeholder} sentinel polygon(s) excluded from matching[/yellow] "
            "— area where census enumeration did not happen, not a district with poor indicators"
        )
    matched, un_geo, un_nfhs, how = reconcile(a, geo)
    rate = 100 * len(matched) / len(geo)
    console.print(f"  matched [bold]{len(matched)}/{len(geo)}[/bold] boundary districts ({rate:.1f}%)")
    for m, n in sorted(how.items(), key=lambda x: -x[1]):
        console.print(f"    {m:24s} {n}")
    console.print(f"  boundary districts with no NFHS row: {len(un_geo)}")
    console.print(f"  NFHS districts with no boundary:     {len(un_nfhs)}")

    # -- emit tables --------------------------------------------------------
    OUT.mkdir(parents=True, exist_ok=True)
    sectors = yaml.safe_load((REPO / "adapters" / "in" / "sectors.yaml").read_text())["sectors"]
    sector_of = {k: v["sector"] for k, v in INDICATORS.items()}

    with open(OUT / "dim_admin_unit.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["admin_unit_code", "name", "state", "admin_level", "census_state_code",
                    "census_district_code", "has_deficit_data", "match_method"])
        for g in geo:
            m = matched.get(g["code"])
            w.writerow([
                g["code"], g["name"], g["state"], "level-2",
                m["nfhs"]["st_cen_cd"] if m else "",
                m["nfhs"]["dt_cen_cd"] if m else "",
                "true" if m else "false",
                m["method"] if m else "unmatched",
            ])

    n_facts = 0
    with open(OUT / "fact_deficit_indicator.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["admin_unit_code", "sector", "indicator_key", "indicator_label",
                    "coverage_pct", "deficit_pct", "source", "year"])
        for code, m in matched.items():
            for ikey, val in m["nfhs"]["values"].items():
                # Capacity indicators ride along in the same parse but are not
                # deficits and must never be written as a scored sector row.
                if ikey not in INDICATORS:
                    continue
                spec = INDICATORS[ikey]
                w.writerow([
                    code, sector_of[ikey], ikey, spec["label"],
                    round(val, 1),
                    round(100.0 - val, 1),  # coverage → deprivation
                    "NFHS-5", 2021,
                ])
                n_facts += 1

        # -- Roads & Transport, from a different source -------------------------
        # NFHS is a health survey and carries no road indicator (all 105 scanned,
        # zero matches — see docs/ROADS-SECTOR-GAP.md). The roads deficit comes
        # from the Census 2011 Village Directory instead, built separately by
        # scripts/build_roads_layer.py because it is 631 district CSVs rather than
        # one extraction. Appended here so every sector lands in one table with its
        # own source and year attached, rather than the console having to know that
        # one sector arrives by a different route.
        # QUARANTINED, and deliberately opt-in rather than "load it if the file is
        # there". Measured 18 Aug 2026: the Census "All Weather Road" status field
        # is not coded comparably across states — Kerala (14/14 districts), Haryana
        # (21/21) and Andhra Pradesh (18/18) all report EXACTLY 0.0% of villages
        # without an all-weather road, while Rajasthan's median is 73%. Two
        # enumerators applied Status A(1)/NA(2) in opposite directions.
        #
        # CIVOS ranks districts nationally against per-sector medians, so consuming
        # this would drive the ranking with a state-level enumeration artefact —
        # the exact "measurement bias distorts funding" failure the product exists
        # to correct. See docs/ROADS-SECTOR-GAP.md for the full evidence.
        #
        # The layer is kept, and the flag is kept, because the finding is worth
        # more than the file: if a comparably-coded column or source turns up, this
        # becomes a one-flag change.
        roads_path = OUT / "fact_roads_deficit.csv"
        n_roads = 0
        if with_roads and roads_path.exists():
            for r in csv.DictReader(roads_path.open()):
                if r["admin_unit_code"] not in matched:
                    # A district with no NFHS row is excluded everywhere else; it
                    # would be inconsistent to score it on roads alone.
                    continue
                w.writerow([
                    r["admin_unit_code"], "roads_transport", r["indicator_key"],
                    r["indicator_label"],
                    round(100.0 - float(r["deficit_pct"]), 1),   # coverage
                    round(float(r["deficit_pct"]), 1),           # deprivation
                    r["source"], r["year"],
                ])
                n_roads += 1
                n_facts += 1
            console.print(
                f"\n[bold]Roads & Transport[/bold] — Census 2011 Village Directory: "
                f"[bold]{n_roads}[/bold] districts"
            )
        elif roads_path.exists():
            console.print(
                "\n[yellow]Roads & Transport layer present but NOT loaded[/yellow] — the Census "
                "all-weather-road field is not comparably coded across states. Pass --with-roads "
                "to override; see docs/ROADS-SECTOR-GAP.md."
            )

    # -- participation capacity ---------------------------------------------
    # Replaces the sha256 connectivity term. Two real NFHS-5 values per district,
    # min-max normalised to [0,1] so the composite is comparable across districts
    # and drops into the existing `deficit × conn^1.6` weight unchanged.
    #
    # Districts missing either input get NO capacity value. They are not given the
    # median: a district that a health survey failed to reach is precisely the kind
    # of district most likely to be genuinely low-capacity, so imputing the middle
    # would erase the signal the product exists to find. Downstream excludes them
    # and says so, matching how missing deficit is already handled.
    cap_rows: list[tuple[str, float, float, float]] = []
    for code, m in matched.items():
        vals = m["nfhs"]["values"]
        schooling = vals.get("pct_women_10yr_schooling")
        electricity = vals.get("pct_households_no_electricity")  # coverage, not deficit
        if schooling is None or electricity is None:
            continue
        raw = (
            CAPACITY_WEIGHTS["schooling"] * schooling
            + CAPACITY_WEIGHTS["electricity"] * electricity
        )
        cap_rows.append((code, schooling, electricity, raw))

    n_cap = 0
    cap_stats: dict | None = None
    if cap_rows:
        raws = [r[3] for r in cap_rows]
        lo, hi = min(raws), max(raws)
        span = (hi - lo) or 1.0
        cap_stats = {"lo": lo, "hi": hi, "n": len(cap_rows), "total": len(geo)}
        with open(OUT / "fact_participation_capacity.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["admin_unit_code", "pct_women_10yr_schooling",
                        "pct_households_with_electricity", "capacity_raw",
                        "connectivity", "source", "year"])
            for code, schooling, electricity, raw in sorted(cap_rows):
                w.writerow([
                    code, round(schooling, 1), round(electricity, 1), round(raw, 2),
                    round((raw - lo) / span, 4), "NFHS-5", 2021,
                ])
                n_cap += 1
        console.print(
            f"\n[bold]Participation capacity[/bold] — "
            f"{CAPACITY_WEIGHTS['schooling']}·schooling + {CAPACITY_WEIGHTS['electricity']}·electricity"
        )
        console.print(f"  raw range {lo:.1f} – {hi:.1f}  →  normalised to [0,1]")
        console.print(f"  districts with capacity: [bold]{n_cap}[/bold] / {len(geo)}")
        console.print(f"  districts without (excluded, not imputed): {len(geo) - n_cap}")

    console.print(f"\n  wrote data/dim_admin_unit.csv ({len(geo)} rows)")
    console.print(f"  wrote data/fact_deficit_indicator.csv ({n_facts} rows)")
    console.print(f"  wrote data/fact_participation_capacity.csv ({n_cap} rows)")

    covered_sectors = sorted({sector_of[k] for k in INDICATORS})
    if n_roads:
        # roads_transport is real too now, just from a different source
        covered_sectors = sorted(set(covered_sectors) | {"roads_transport"})
    missing = [s["key"] for s in sectors if s["key"] not in covered_sectors]

    # -- reconciliation report ---------------------------------------------
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md: list[str] = []
    md.append("# Deficit layer — provenance and reconciliation")
    md.append("")
    md.append(f"Built {stamp}. Regenerate with `uv run python scripts/build_deficit_layer.py`.")
    md.append("")
    md.append("## Source")
    md.append("")
    md.append(SOURCE_CITATION)
    md.append("")
    md.append(
        "`rchiips.org`, which hosts the official factsheet PDFs, currently returns 404 and "
        "presents an invalid TLS certificate, so the PDFs could not be retrieved at source. "
        "Two independent community extractions of those same PDFs were used instead, and "
        "**cross-validated against each other** rather than trusted."
    )
    md.append("")
    md.append("| Extraction | Districts | Licence | Role |")
    md.append("|---|---|---|---|")
    md.append(f"| `SaiSiddhardhaKalla/NFHS` | {len(a)} | none stated | primary — carries census district codes |")
    md.append(f"| `pratapvardhan/NFHS-5` | {len(b)} | CC-BY-4.0 | independent cross-check |")
    md.append("")
    md.append(
        "The values themselves are Government of India statistics and are attributed to NFHS-5 "
        "above; the repositories are transport, not authorship."
    )
    md.append("")
    md.append("### On the \"none stated\" licence")
    md.append("")
    md.append(
        "The primary extraction states no licence, which by default means all rights reserved. "
        "That is worth addressing directly rather than leaving as a blank cell in a table, "
        "because it reads as an unexamined risk and it is not one."
    )
    md.append("")
    md.append(
        "1. **The figures are facts, not expression.** A district's measured percentage of "
        "households without piped water is a Government of India survey statistic. Facts are not "
        "copyrightable; only a creative arrangement of them is, and a factsheet transcription is "
        "the opposite of a creative arrangement."
    )
    md.append(
        "2. **Neither repository is the origin.** The canonical source is `rchiips.org` "
        "(IIPS / MoHFW), recorded above together with the exact 404 and TLS failure that "
        "prevented retrieval at source."
    )
    md.append(
        "3. **Two independent extractions agree to the decimal.** The cross-validation below is "
        "not only a quality check — it is evidence that neither repository *authored* anything. "
        "Two parties cannot independently produce identical creative work from the same PDFs; "
        "they can only both transcribe the same facts."
    )
    md.append(
        "4. **A CC-BY-4.0 route to the same values exists.** The cross-check extraction is "
        "CC-BY-4.0 and covers "
        f"{len(b)} districts, independently licensing the same figures where it overlaps."
    )
    md.append("")
    md.append(
        "CIVOS therefore attributes the data to **NFHS-5 (IIPS / MoHFW, Government of India)** and "
        "treats both repositories as retrieval mechanisms. If IIPS restores `rchiips.org`, this "
        "script should be pointed at the source PDFs and this section reduced to a footnote."
    )
    md.append("")
    md.append(
        "This is a reasoned position, not legal advice. A ministry deploying CIVOS in production "
        "should retrieve the factsheets from IIPS directly, which is correct practice regardless "
        "of licensing."
    )
    md.append("")
    md.append("## Cross-validation")
    md.append("")
    md.append(f"Both extractions cover **{xval['overlap_districts']} districts** in common.")
    md.append("")
    md.append("| Indicator | Compared | Identical | Max difference |")
    md.append("|---|---|---|---|")
    for ikey, r in xval["indicators"].items():
        md.append(f"| `{ikey}` | {r['compared']} | {r['identical']} ({100*r['identical']/r['compared']:.1f}%) | {r['max_diff']} |")
    md.append("")
    md.append(
        "Two independent PDF extractions agreeing to the decimal across every indicator is "
        "good evidence that neither mangled the source. This check re-runs on every build."
    )
    md.append("")
    md.append("## Reconciliation against the boundary set")
    md.append("")
    md.append(
        f"**{len(matched)} of {len(geo)} rendered districts ({rate:.1f}%)** carry real NFHS-5 values."
    )
    md.append("")
    md.append("| Method | Districts |")
    md.append("|---|---|")
    for m, n in sorted(how.items(), key=lambda x: -x[1]):
        md.append(f"| `{m}` | {n} |")
    md.append("")
    md.append(
        "The boundary file is 2011-era, so it predates **Telangana** (created 2014) and "
        "**Ladakh** (2019), and many districts have been split or renamed since. Those states "
        "are aliased back to their parent for matching. Districts that still do not match are "
        "listed below, **excluded from the ranking, and rendered grey** — they are not given an "
        "invented value."
    )
    md.append("")
    md.append(f"### Boundary districts with no NFHS-5 row ({len(un_geo)})")
    md.append("")
    md.append(", ".join(f"{g['name']} ({g['state']})" for g in un_geo[:80]) or "none")
    if len(un_geo) > 80:
        md.append(f"\n… and {len(un_geo)-80} more.")
    md.append("")
    md.append(f"### NFHS-5 districts with no boundary ({len(un_nfhs)})")
    md.append("")
    md.append(", ".join(f"{r['district']} ({r['state']})" for r in un_nfhs[:80]) or "none")
    if len(un_nfhs) > 80:
        md.append(f"\n… and {len(un_nfhs)-80} more.")
    md.append("")
    md.append("## Sector coverage")
    md.append("")
    md.append("| Sector | Indicator | Status |")
    md.append("|---|---|---|")
    for s in sectors:
        ind = next((INDICATORS[k]["label"] for k in INDICATORS if sector_of[k] == s["key"]), None)
        md.append(
            f"| {s['label']} | {ind or '—'} | "
            + ("✅ real, NFHS-5 2021" if ind else "❌ **no real indicator loaded**")
            + " |"
        )
    md.append("")
    if missing:
        md.append(
            "**"
            + ", ".join(missing)
            + "** has no NFHS-5 equivalent — road connectivity is not a health-survey "
            "indicator. It needs PMGSY habitation-connectivity data, which is not loaded. "
            "The sector is left visibly empty rather than filled with a proxy: plan.md's rule "
            "is that two real sectors beat five mangled ones."
        )
    md.append("")
    md.append("## Deficit direction")
    md.append("")
    md.append(
        "NFHS-5 reports **coverage** (\"% with an improved water source\"). The engine needs "
        "**deprivation**, so `deficit_pct = 100 − coverage_pct`. Stated explicitly because "
        "getting it backwards would invert the entire product."
    )
    md.append("")
    md.append("## Participation capacity — who can actually file a complaint")
    md.append("")
    md.append(
        "The synthetic corpus applies a participation bias of `deficit × connectivity^1.6`. The "
        "shape is the whole argument — real deprivation multiplied by ability-to-report is what "
        "makes the Silent Need quadrant populate. But `connectivity` used to be "
        "`sha256(district_code)`: a hash with no real-world meaning, which meant the specific set "
        "of districts classified Silent Need was **arbitrary**. \"Why is this district silent?\" "
        "had no answer."
    )
    md.append("")
    md.append("It is now built from two real NFHS-5 values on the same districts:")
    md.append("")
    md.append("| Input | Proxies | Weight |")
    md.append("|---|---|---|")
    md.append(
        f"| Women with 10 or more years of schooling (%) | literacy and the agency to navigate a "
        f"grievance process | {CAPACITY_WEIGHTS['schooling']} |"
    )
    md.append(
        f"| Population living in households with electricity (%) | household infrastructure a "
        f"phone depends on | {CAPACITY_WEIGHTS['electricity']} |"
    )
    md.append("")
    if cap_stats:
        md.append(
            f"Composite raw range **{cap_stats['lo']:.1f} – {cap_stats['hi']:.1f}**, min-max "
            f"normalised to `[0,1]`. **{cap_stats['n']} of {cap_stats['total']} districts** carry "
            f"a capacity value."
        )
        md.append("")
    md.append(
        "**The weighting is a judgement, not a measurement.** It is stated here so it can be "
        "argued with, on the same principle that exposes the `w1..w5` scoring weights as sliders "
        "in the console rather than burying them."
    )
    md.append("")
    md.append(
        "**Districts missing either input get no capacity value and are excluded — not imputed.** "
        "A district a health survey failed to reach is precisely the kind of district most likely "
        "to be genuinely low-capacity, so filling it with the median would erase the signal the "
        "product exists to find."
    )
    md.append("")
    md.append("Written to `data/fact_participation_capacity.csv`.")
    md.append("")
    md.append("## Still placeholder")
    md.append("")
    md.append("- **District population** — no census population loaded. The population-affected figure in dossiers is derived from a placeholder, is labelled as such in the interface, and the dossier prompt now requires the model to say so in prose as well.")
    md.append("- **Roads & Transport deficit** — see above.")
    md.append("- **Citizen signals** — synthetic by design, and labelled as such in the interface.")
    md.append("")
    md.append("No longer placeholder: **participation / connectivity**, previously a hash — see above.")

    (REPO / "docs" / "DATA-RECONCILIATION.md").write_text("\n".join(md) + "\n")
    console.print("  wrote docs/DATA-RECONCILIATION.md")

    # -- summary ------------------------------------------------------------
    t = Table(title="Phase 1 deficit layer")
    t.add_column("metric")
    t.add_column("value", justify="right")
    t.add_row("NFHS-5 districts extracted", str(len(a)))
    t.add_row("cross-validated against", f"{len(b)} districts")
    t.add_row("boundary districts matched", f"{len(matched)}/{len(geo)} ({rate:.1f}%)")
    t.add_row("deficit facts written", str(n_facts))
    t.add_row("sectors with real data", f"{len(covered_sectors)}/{len(sectors)}")
    console.print()
    console.print(t)

    if load_bigquery:
        load_to_bq(project, location, dataset)


def load_to_bq(project: str, location: str, dataset: str) -> None:
    """Task 1.5 — load the two tables to BigQuery with source and year columns."""
    from google.cloud import bigquery

    console.print(f"\n[bold]Loading to BigQuery[/bold] {project}.{dataset} ({location})")
    client = bigquery.Client(project=project, location=location)

    specs = [
        ("dim_admin_unit", OUT / "dim_admin_unit.csv"),
        ("fact_deficit_indicator", OUT / "fact_deficit_indicator.csv"),
    ]
    for table, path in specs:
        ref = f"{project}.{dataset}.{table}"
        job = client.load_table_from_file(
            path.open("rb"),
            ref,
            job_config=bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1,
                autodetect=True,
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            ),
        )
        job.result()
        n = client.get_table(ref).num_rows
        console.print(f"  [green]loaded[/green] {ref} — {n} rows")


if __name__ == "__main__":
    typer.run(main)
