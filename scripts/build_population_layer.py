"""Census 2011 district population — replaces the hashed placeholder.

Why this exists
---------------
`scripts/generate_console_fixtures.py` set

    population = 180_000 + sha256(district_code) * 3_400_000

and every dossier's "population affected (est.)" derived from it. The interface
labelled it a placeholder and the dossier prompt now forces the model to say so,
but a labelled fake number in a scored output is still a fake number — and
`SPEC.md §12` counts population-affected estimates toward Impact Potential.

Source, and why this one
------------------------
**Wikidata** (`P1082` population, on entities that are instances of *district of
India*), licensed **CC0**. Values there are sourced from the 2011 Census of India.

data.gov.in hosts the Census tables directly and would be the better primary, but
every relevant resource there is behind an API key, which cannot be committed to a
public repository and would make this script unrunnable for anyone cloning it. A
CC0 source that needs no credential is worth more to a Digital Public Good than a
marginally more authoritative one nobody else can fetch.

The trade-off is stated rather than hidden: Wikidata is community-maintained, so
each value is a transcription of the census rather than the census itself. Every
figure written by this script therefore carries `source = "Census 2011 via
Wikidata (CC0)"` so a reader can see the chain, and districts that do not match are
left without a population rather than being given an estimate.

Two measured limitations of this source, recorded because they shape the join:

1. **`P5140` (2011 census code) is empty** on these entities — 0 of 754 rows carry
   it — so the exact code join that made the deficit layer reliable is not
   available here. Matching is by name, which is weaker.
2. **`P131` often returns a division, not a state** ("Bangalore division" for
   Tumkur), so state-qualified matching only works for part of the set and
   name-uniqueness does most of the work.

Because of (1) and (2), a name is accepted only when it is unique on BOTH sides.
Coverage therefore stops around 82%, and the rest are left empty on purpose.

Caching
-------
The Wikidata Query Service was rate-limited to 1 request/minute during an active
outage when this was written, so the raw response is cached under
`data/raw/wikidata_population.json` and reruns are offline — the same pattern
`build_deficit_layer.py` uses. The derived CSV is committed, so the pipeline does
not depend on WDQS being healthy.

Usage
-----
    uv run python scripts/build_population_layer.py
    uv run python scripts/build_population_layer.py --refresh   # re-query WDQS
"""

from __future__ import annotations

import csv
import difflib
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import typer
from rich.console import Console

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "raw" / "wikidata_population.json"
OUT = REPO / "data" / "fact_population.csv"

ENDPOINT = "https://query.wikidata.org/sparql"

# Instances of "district of India" (Q1149652) that carry a population value.
# P131 = located in the administrative territorial entity, used to get the state.
QUERY = """
SELECT ?districtLabel ?stateLabel ?pop ?censuscode WHERE {
  ?district wdt:P31 wd:Q1149652 ;
            wdt:P1082 ?pop .
  OPTIONAL { ?district wdt:P131 ?state . }
  OPTIONAL { ?district wdt:P5140 ?censuscode . }   # 2011 Census of India code
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""

console = Console()
app = typer.Typer(add_completion=False)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"\bdistrict\b", "", s, flags=re.I)
    return re.sub(r"[^a-z]", "", s.lower())


def fetch(refresh: bool) -> dict:
    if RAW.exists() and not refresh:
        console.print(f"  using cached {RAW.relative_to(REPO)}")
        return json.loads(RAW.read_text())

    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": QUERY, "format": "json"})
    req = urllib.request.Request(
        url,
        headers={
            # WDQS requires a descriptive UA and blocks generic ones.
            "User-Agent": "CIVOS-build/0.1 (https://github.com/ojha-436/CIVOS) python-urllib",
            "Accept": "application/sparql-results+json",
        },
    )
    console.print("  querying Wikidata Query Service…")
    with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310
        payload = json.load(r)
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps(payload))
    console.print(f"  cached → {RAW.relative_to(REPO)}")
    return payload


@app.command()
def main(refresh: bool = typer.Option(False, "--refresh", help="Re-query WDQS")) -> None:
    console.rule("[bold]Census 2011 district population (via Wikidata, CC0)[/bold]")

    try:
        payload = fetch(refresh)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            f"Wikidata fetch failed: {type(exc).__name__}: {str(exc)[:200]}\n"
            "WDQS was rate-limited to 1 request/minute during an outage when this was "
            "written. Wait a minute and retry, or keep the committed data/fact_population.csv."
        ) from None

    rows = payload["results"]["bindings"]
    console.print(f"  Wikidata districts with a population value: [bold]{len(rows)}[/bold]")

    # Highest population per (state, district) name — Wikidata sometimes carries
    # several census years on one entity, and 2011 is the largest for almost every
    # Indian district. Documented as the heuristic it is.
    wd: dict[tuple[str, str], int] = {}
    wd_by_name: dict[str, list[tuple[str, int]]] = {}
    # Census-code index. Our boundary set carries dt_cen_cd since the DataMeet
    # swap, so where Wikidata also has P5140 the join is an exact integer match
    # rather than a transliteration guess — no more Ahmadnagar/Ahmednagar,
    # Baleshwar/Balasore, or Allahabad/Prayagraj renames to reconcile by hand.
    wd_by_census: dict[int, int] = {}
    for b in rows:
        d = b.get("districtLabel", {}).get("value", "")
        st = b.get("stateLabel", {}).get("value", "")
        try:
            pop = int(float(b["pop"]["value"]))
        except (KeyError, ValueError):
            continue
        if pop < 10_000 or pop > 20_000_000:
            continue  # not a district-scale figure
        key = (norm(st), norm(d))
        wd[key] = max(wd.get(key, 0), pop)
        wd_by_name.setdefault(norm(d), []).append((norm(st), pop))
        cc = b.get("censuscode", {}).get("value")
        if cc:
            try:
                wd_by_census[int(float(cc))] = max(wd_by_census.get(int(float(cc)), 0), pop)
            except ValueError:
                pass

    # -- join onto our districts -------------------------------------------
    units = list(csv.DictReader((REPO / "data" / "dim_admin_unit.csv").open()))
    matched: dict[str, tuple[int, str]] = {}
    unmatched: list[str] = []

    # How many of OUR districts share each normalised name. Needed for the
    # unique-nationally rule below: a name that is unique in Wikidata but
    # duplicated here would hand the same population to two different districts,
    # and one of them would be silently wrong.
    ours_by_name: dict[str, int] = {}
    for u in units:
        ours_by_name[norm(u["name"])] = ours_by_name.get(norm(u["name"]), 0) + 1

    for u in units:
        code, name, state = u["admin_unit_code"], u["name"], u["state"]
        if name.lower() == "data not available":
            continue
        n, s = norm(name), norm(state)

        # Census code first — exact, and immune to spelling and renames.
        cc = u.get("census_district_code")
        try:
            cci = int(float(cc)) if cc else None
        except ValueError:
            cci = None
        if cci is not None and cci in wd_by_census:
            matched[code] = (wd_by_census[cci], "census_code")
            continue

        if (s, n) in wd:
            matched[code] = (wd[(s, n)], "exact_state_district")
            continue
        # Unique nationally is safe ONLY if the name is unique on BOTH sides.
        # Measured: `bijapur` and `raigarh` are single entries in Wikidata but two
        # districts each here, so a one-sided uniqueness test would give two
        # different districts the same population and one would be wrong. Two
        # missing figures beat two invented ones — the same rule the deficit layer
        # learned the hard way when "East" matched Sikkim to Delhi.
        cands = wd_by_name.get(n, [])
        if len(cands) == 1 and ours_by_name.get(n, 0) == 1:
            matched[code] = (cands[0][1], "district_unique_nationally")
            continue
        near = difflib.get_close_matches(n, [k[1] for k in wd if k[0] == s], n=1, cutoff=0.88)
        if near:
            matched[code] = (wd[(s, near[0])], "fuzzy_within_state")
            continue
        unmatched.append(f"{name} ({state})")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["admin_unit_code", "population", "source", "match_method"])
        for code, (pop, how) in sorted(matched.items()):
            w.writerow([code, pop, "Census 2011 via Wikidata (CC0)", how])

    pct = 100 * len(matched) / max(len(units), 1)
    console.print(f"  matched [bold]{len(matched)}/{len(units)}[/bold] districts ({pct:.1f}%)")
    methods: dict[str, int] = {}
    for _, how in matched.values():
        methods[how] = methods.get(how, 0) + 1
    for m, c in sorted(methods.items(), key=lambda x: -x[1]):
        console.print(f"    {m:28} {c}")
    console.print(f"  [yellow]no population found: {len(unmatched)}[/yellow]")
    if unmatched:
        console.print("    " + ", ".join(unmatched[:12]) + (" …" if len(unmatched) > 12 else ""))
    console.print(f"\n  wrote {OUT.relative_to(REPO)} ({len(matched)} rows)")
    console.print(
        "\n[bold]Next:[/bold] uv run python scripts/generate_console_fixtures.py "
        "--geojson console/public/data/districts.geojson"
    )

    if pct < 50:
        raise SystemExit(
            f"only {pct:.1f}% of districts got a population — too low to replace the "
            "placeholder. Keep the placeholder rather than shipping a half-populated column."
        )


if __name__ == "__main__":
    app()
