"""Build the district boundary set from DataMeet's Census-2011 shapefile.

Why this script exists
----------------------
The previous boundary file was produced by hand from a 33 MB "public GeoJSON" whose
identity was never recorded, and which the code strongly indicates was **GADM**
(it read `NAME_1`/`NAME_2`, and `build_deficit_layer.py` aliased state names back
to GADM 2.x-era spellings like `orissa` and `uttaranchal`).

Two problems with that:

1. **Licensing.** GADM permits academic and non-commercial use but prohibits
   redistribution without prior permission. CIVOS commits a derived, simplified
   copy of the geometry to a public repository under Apache-2.0 / CC-BY-4.0. That
   is redistribution, and for a project whose licence posture is part of its
   Digital Public Good argument it was the one finding that could be turned
   against it.
2. **Reproducibility.** Nobody but the original author could rebuild the file.

DataMeet's Census-2011 district shapefile fixes both, and turns out to be a better
dataset besides:

| | GADM (previous) | DataMeet (this) |
|---|---|---|
| Licence | redistribution prohibited | **CC-BY 4.0** |
| Districts | 594 | **641** |
| Census codes | absent | **ST_CEN_CD + DT_CEN_CD carried** |
| NFHS reconciliation | 90.4%, fuzzy name matching | **98.0% exact code match** |
| State naming | 2011-era (`Orissa`, `Uttaranchal`) | modern |

Carrying the census codes is the important part. NFHS-5's own extraction carries
the same codes, so districts can be joined on an integer pair instead of on
fuzzy-matched English names. That removes an entire class of silent error — the
matcher previously married Sikkim's "East" district to Delhi's "East", which would
have painted one district's deprivation onto another with nothing on screen to
show for it (see memory.md).

Attribution
-----------
District boundaries by the DataMeet India community, CC-BY 4.0.
https://github.com/datameet/maps — Districts/Census_2011

Usage
-----
    uv run --with pyshp python scripts/build_boundaries.py

    # keep more detail (larger file)
    uv run --with pyshp python scripts/build_boundaries.py --simplify 8%

Requires `npx` for mapshaper simplification. Downloads are cached under data/raw/
so reruns are offline.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parent))
from india_admin import district_code  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "raw" / "datameet"
OUT = REPO / "console" / "public" / "data"

BASE = "https://raw.githubusercontent.com/datameet/maps/master/Districts/Census_2011/2011_Dist"
PARTS = ("shp", "dbf", "shx", "prj")

SOURCE_URL = "https://github.com/datameet/maps/tree/master/Districts/Census_2011"
SOURCE_NAME = "DataMeet India community — Census 2011 district boundaries"
SOURCE_LICENCE = "CC-BY 4.0"

console = Console()
app = typer.Typer(add_completion=False)


def fetch_parts() -> Path:
    """Download the shapefile's four sidecar files once. Cached, so reruns work offline."""
    RAW.mkdir(parents=True, exist_ok=True)
    for ext in PARTS:
        dest = RAW / f"2011_Dist.{ext}"
        if dest.exists():
            continue
        url = f"{BASE}.{ext}"
        console.print(f"  fetching {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "CIVOS-build/0.1"})
        with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310
            dest.write_bytes(r.read())
    return RAW / "2011_Dist"


@app.command()
def main(
    simplify: str = typer.Option(
        "4%", "--simplify",
        help="mapshaper simplification retained-vertex percentage",
    ),
) -> None:
    console.rule("[bold]District boundaries — DataMeet Census 2011[/bold]")

    try:
        import shapefile  # pyshp
    except ImportError:
        raise SystemExit(
            "pyshp missing. Run: uv run --with pyshp python scripts/build_boundaries.py"
        ) from None

    stem = fetch_parts()
    r = shapefile.Reader(str(stem))
    fields = [f[0] for f in r.fields[1:]]
    for required in ("DISTRICT", "ST_NM", "ST_CEN_CD", "DT_CEN_CD"):
        if required not in fields:
            raise SystemExit(f"upstream shapefile is missing field {required!r}; fields={fields}")

    idx = {f: fields.index(f) for f in fields}
    seen: set[str] = set()
    features: list[dict] = []
    placeholders: list[str] = []

    for shp, rec in zip(r.shapes(), r.records()):
        state = str(rec[idx["ST_NM"]]).strip()
        name = str(rec[idx["DISTRICT"]]).strip()
        st_cd = int(rec[idx["ST_CEN_CD"]])
        dt_cd = int(rec[idx["DT_CEN_CD"]])

        # The upstream shapefile carries a SENTINEL polygon for the area where
        # census enumeration did not happen: DISTRICT = "Data Not Available" with
        # census codes 99/99. NFHS-5's extraction carries a matching placeholder
        # row, so a naive join marries one placeholder to the other and produces a
        # district with 0% schooling and 0% electricity.
        #
        # That is not a district with terrible indicators — it is the absence of a
        # measurement, and treating it as data poisoned the min-max normalisation
        # of participation capacity, dragging the floor from 39.0 to 0.0 and
        # compressing every real district's connectivity upward.
        #
        # The polygon is KEPT so the map stays geographically complete, but it is
        # flagged. Downstream excludes it from reconciliation, from capacity and
        # from the ranking, and renders it as no-official-data. The land exists;
        # the data does not.
        placeholder = name.lower() == "data not available" or (st_cd == 99 and dt_cd == 99)
        code = district_code(state, name, seen)
        if placeholder:
            placeholders.append(code)
        features.append(
            {
                "type": "Feature",
                # Census codes are carried, NOT discarded. The previous pipeline
                # stripped properties down to {code,name,state}, which is why the
                # source became unidentifiable and why reconciliation had to fall
                # back to fuzzy name matching.
                "properties": {
                    "code": code,
                    "name": name,
                    "state": state,
                    "st_cen_cd": st_cd,
                    "dt_cen_cd": dt_cd,
                    **({"placeholder": True} if placeholder else {}),
                },
                "geometry": shp.__geo_interface__,
            }
        )

    console.print(f"  districts read: [bold]{len(features)}[/bold]")
    if placeholders:
        console.print(
            f"  [yellow]sentinel polygons flagged (kept on the map, excluded from data):[/yellow] "
            f"{', '.join(placeholders)}"
        )

    raw_path = RAW / "districts_full.geojson"
    raw_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    console.print(f"  unsimplified: {raw_path.stat().st_size / 1e6:.1f} MB")

    # -- simplify -----------------------------------------------------------
    # Topology-preserving, so neighbouring districts keep shared edges and the
    # choropleth has no white seams between them.
    OUT.mkdir(parents=True, exist_ok=True)
    final = OUT / "districts.geojson"
    cmd = [
        "npx", "-y", "mapshaper", str(raw_path),
        "-simplify", simplify, "keep-shapes",
        "-o", "format=geojson", "precision=0.0001", str(final),
    ]
    console.print(f"  simplifying with mapshaper ({simplify}, topology preserved)…")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            "mapshaper failed — is npx available?\n"
            f"{proc.stdout[-800:]}\n{proc.stderr[-800:]}"
        )

    gj = json.loads(final.read_text())
    # mapshaper can reorder; re-serialise compactly and confirm nothing was dropped.
    if len(gj["features"]) != len(features):
        raise SystemExit(
            f"simplification changed the feature count: {len(features)} → {len(gj['features'])}"
        )
    final.write_text(json.dumps(gj, separators=(",", ":")))
    console.print(f"  wrote {final.relative_to(REPO)} ({final.stat().st_size / 1e3:.0f} KB)")

    # -- state → district index used by the citizen intake dropdowns --------
    by_state: dict[str, list[dict]] = {}
    for f in gj["features"]:
        p = f["properties"]
        by_state.setdefault(p["state"], []).append({"code": p["code"], "name": p["name"]})
    for v in by_state.values():
        v.sort(key=lambda d: d["name"])
    idx_path = OUT / "india-districts.json"
    idx_path.write_text(json.dumps(dict(sorted(by_state.items())), separators=(",", ":")))
    console.print(f"  wrote {idx_path.relative_to(REPO)} ({len(by_state)} states)")

    # -- attribution --------------------------------------------------------
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    doc = f"""# District boundary attribution

Built {stamp}. Regenerate with `uv run --with pyshp python scripts/build_boundaries.py`.

## Source

**{SOURCE_NAME}**, licensed **{SOURCE_LICENCE}**.

<{SOURCE_URL}>

> District boundaries by the [DataMeet India community](http://datameet.org/)
> ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)).

The upstream file is a shapefile (`2011_Dist.shp`, ~10 MB, already in WGS 84).
`scripts/build_boundaries.py` converts it to GeoJSON, simplifies it for web
rendering, and writes `console/public/data/districts.geojson`.

| | Value |
|---|---|
| Districts | {len(gj['features'])} |
| Simplification | `{simplify}` retained vertices, topology preserved |
| Rendered size | {final.stat().st_size / 1e3:.0f} KB |
| Coordinate precision | 4 decimal places (~11 m) |

## Why this source, and what it replaced

The previous boundary file came from an unrecorded 33 MB "public GeoJSON" that the
code strongly indicates was **GADM** — `scripts/generate_console_fixtures.py` read
`NAME_1`/`NAME_2`, GADM's property convention, and the deficit builder aliased
state names back to GADM 2.x spellings (`orissa`, `uttaranchal`, `nctofdelhi`).

**GADM prohibits redistribution without prior permission.** CIVOS publishes a
derived copy of the geometry in a public repository, so that was a licensing
conflict as well as an unattributed layer — and it undercut the Digital Public Good
argument the project makes about itself.

The replacement is better on the merits, not only on licensing:

| | GADM (previous) | DataMeet (current) |
|---|---|---|
| Licence | redistribution prohibited | **CC-BY 4.0** |
| Districts | 594 | **{len(gj['features'])}** |
| Census codes in properties | absent | **`st_cen_cd` + `dt_cen_cd`** |
| NFHS-5 reconciliation | 90.4%, fuzzy name matching | **exact census-code join** |
| State naming | 2011-era | modern |

Carrying the census codes is the substantive gain. NFHS-5's own extraction carries
the same `ST_CEN_CD` / `DT_CEN_CD` pair, so districts join on integers rather than
on fuzzy-matched English names. That removes a class of silent error the project
had already been bitten by once: the earlier name matcher married Sikkim's **East**
district to Delhi's **East**, which would have painted one district's deprivation
onto another with nothing on screen to indicate it (see `memory.md`).

## Properties carried

```json
{{"code": "IN-OR-dhenkanal", "name": "Dhenkanal", "state": "Odisha",
 "st_cen_cd": 21, "dt_cen_cd": 15}}
```

Codes stay in the human-readable `IN-<ISO 3166-2 subdivision>-<slug>` form, because
that string is shown in the console drilldown and in dossiers where it tells a
reader something. Census codes travel alongside rather than replacing it. Spelling
variants across sources (`Odisha`/`Orissa`, `&`/`and`, the upstream `Arunanchal`
typo) are aliased to the same subdivision code in `scripts/india_admin.py`, so a
change of boundary source does not silently renumber districts.
"""
    (REPO / "docs" / "BOUNDARY-ATTRIBUTION.md").write_text(doc)
    console.print("  wrote docs/BOUNDARY-ATTRIBUTION.md")

    console.print(
        "\n[bold]Next:[/bold] re-run the deficit layer and the console fixture — "
        "district codes change with the boundary set.\n"
        "  uv run python scripts/build_deficit_layer.py\n"
        "  uv run python scripts/generate_console_fixtures.py "
        "--geojson console/public/data/districts.geojson"
    )


if __name__ == "__main__":
    app()
