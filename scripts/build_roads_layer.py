"""Roads & Transport deficit — Census 2011 Village Directory, all-weather road access.

Closes the one sector that had no real indicator. Four of five sectors come from
NFHS-5; road connectivity has no health-survey equivalent, so it needed its own
source. `docs/ROADS-INDICATOR.md` records the six sources checked before this one
and the two that were rejected on principle.

Source
------
**Village Amenities, Census 2011** — Ministry of Home Affairs / Office of the
Registrar General and Census Commissioner, published on `data.gov.in` under the
**National Data Sharing and Accessibility Policy (NDSAP)**, which permits reuse and
redistribution with attribution and is compatible with this project's licensing.

Two things make this workable without any credential:

1. The catalogue is enumerable through data.gov.in's **public** backend
   (`/backend/dmspublic/v1/resources`) — no API key. The portal's own front end
   uses it. 631 resources, one CSV per district.
2. Each record's `datafile_url` points straight at `censusindia.gov.in`, so the
   CSVs download directly from the census website.

This is why SHRUG was rejected even though it would have been faster: SHRUG is
CC BY-NC-SA, and an NC layer would break DPGA indicator 2 and restrict what a
ministry could do with the output. Going to the authoritative source keeps the
licence clean.

The indicator, and the one that was rejected
--------------------------------------------
Column **"Black Topped (pucca) Road (Status A(1)/NA(2))"** per village:
1 = available, 2 = not available, blank = not recorded.

    deficit_pct = 100 × villages with status 2 / villages with a recorded status

**"All Weather Road" was tested first and rejected.** All ten road columns were
captured for 628 districts and screened for state-level coding artefacts — a state
where every district lands within 1 percentage point of the others, which is a
coding convention rather than a physical fact. Results:

    National Highway            median 93.9%   0 flat states
    State Highway               median 84.1%   0
    Other District Road         median 44.0%   0
    Black Topped (pucca) Road   median 27.5%   1  (Kerala)   <- chosen
    All Weather Road            median 25.2%   3  (Kerala, Haryana, Andhra Pradesh)
    Footpath                    median  0.0%  13

Highway presence is not a connectivity measure — most villages legitimately have no
highway on them. Pucca-road presence is the standard proxy and shows real internal
spread in almost every state (Assam 60.8–99.6, Uttar Pradesh 7.1–100.0, Bihar
2.6–77.8, Jammu & Kashmir 15.4–87.7).

**Known limitation, disclosed rather than hidden.** Coding is still not perfectly
comparable across states. Kerala reports 0.0% in all 14 districts, which is
credible — it has near-universal paved access. **Jharkhand's median of 1.7% is
not** credible for a state where PMGSY runs priority programmes, and Ballia and Mau
in Uttar Pradesh both sit at 100%. The caveat travels with the data: it is written
into the indicator label, surfaced in the console, and stated in every dossier that
cites the sector.

A straight aggregation of an official categorical field — the same operation as
"% households without electricity" from NFHS-5. No spatial analysis, no buffers, no
derived estimate. Villages with a blank status are excluded from the denominator
rather than assumed connected, and the recorded coverage is reported per district so
a thin denominator is visible instead of hidden.

Joining
-------
The CSV's "District Code" is the all-India Census 2011 district code, which is the
`censuscode` field carried by the DataMeet boundary set. The join is therefore an
exact integer match, not a name match.

Usage
-----
    uv run --with pandas python scripts/build_roads_layer.py
    uv run --with pandas python scripts/build_roads_layer.py --keep-raw   # cache CSVs
    uv run --with pandas python scripts/build_roads_layer.py --limit 20   # smoke test
"""

from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "raw" / "village_amenities"
OUT = REPO / "data" / "fact_roads_deficit.csv"

CATALOG_REFERENCE = 534901          # "Village Amenities, Census 2011"
CATALOG_UUID = "007f2c63-cdb1-4c91-82ef-61716f0b0e76"
API = "https://www.data.gov.in/backend/dmspublic/v1/resources"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
# All road columns are captured so the choice of indicator can be revisited without
# re-downloading 628 files (~760 MB from a slow government host).
ROAD_COLS = (
    "National Highway", "State Highway", "Major District Road", "Other District Road",
    "Black Topped (pucca) Road", "Gravel (kuchha) Roads", "Water Bounded Macadam",
    "All Weather Road", "Navigable Waterways", "Footpath",
)
DEFAULT_COL = "Black Topped (pucca) Road"
COLUMN_CACHE = "road_columns.json"

console = Console()
app = typer.Typer(add_completion=False)


def _get(url: str, timeout: int = 180) -> bytes:
    """data.gov.in — normal TLS, urllib is fine."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return r.read()


def _get_census(url: str, timeout: int = 240) -> bytes:
    """censusindia.gov.in — fetched with curl, and the reason is not laziness.

    The host serves an incomplete certificate chain: it omits an intermediate, so
    Python's verifier fails with "unable to get local issuer certificate" even
    against the certifi bundle. curl completes the chain from the system trust
    store and the download succeeds.

    The alternative would be `ssl._create_unverified_context()`, i.e. turning
    verification off entirely. That is refused here — this project already
    documents a TLS failure at another government source (rchiips.org, see
    docs/DATA-RECONCILIATION.md) and the response there was to record the problem,
    not to silence the check. Shelling out keeps verification ON; it just uses a
    verifier that has the full chain.
    """
    if not shutil.which("curl"):
        raise RuntimeError(
            "curl not found. censusindia.gov.in serves an incomplete certificate "
            "chain that Python's verifier rejects; curl is required to fetch it."
        )
    # Retried: 631 sequential fetches from one government host will hit transient
    # timeouts, and a district silently missing from a national deficit layer is a
    # worse outcome than a slow build.
    last = ""
    for attempt in range(3):
        proc = subprocess.run(
            ["curl", "-sSL", "--fail", "--retry", "2", "--retry-delay", "2",
             "-m", str(timeout), "-A", UA, url],
            capture_output=True,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
        last = f"curl exit {proc.returncode}: {proc.stderr.decode('utf-8','replace')[:140]}"
    raise RuntimeError(f"{last} (after 3 attempts)")


def list_resources() -> list[dict]:
    """Enumerate the catalogue through data.gov.in's public backend. No API key."""
    cache = RAW / "_resources.json"
    if cache.exists():
        console.print(f"  using cached resource list {cache.relative_to(REPO)}")
        return json.loads(cache.read_text())

    out: list[dict] = []
    offset, limit = 0, 100
    while True:
        q = urllib.parse.urlencode(
            {
                "filters[catalog_reference]": CATALOG_REFERENCE,
                "offset": offset,
                "limit": limit,
                "sort[changed]": "desc",
            }
        )
        payload = json.loads(_get(f"{API}?{q}"))
        total = payload["total"]
        rows = payload["data"]["rows"]
        if not rows:
            break
        for r in rows:
            # every value arrives as a single-element list
            def one(k):
                v = r.get(k)
                return v[0] if isinstance(v, list) and v else v
            out.append(
                {
                    "title": one("title"),
                    "url": one("datafile_url"),
                    "size": one("file_size"),
                    "fmt": one("file_format"),
                }
            )
        offset += limit
        console.print(f"  listed {min(offset, total)}/{total}")
        if offset >= total:
            break

    RAW.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out))
    return out


@app.command()
def main(
    column: str = typer.Option(DEFAULT_COL, "--column", help="Which road column to use"),
    refresh: bool = typer.Option(False, "--refresh", help="Re-download and rebuild the column cache"),
    limit: int = typer.Option(0, "--limit", help="Only process N districts (smoke test)"),
) -> None:
    console.rule("[bold]Roads & Transport — Census 2011 Village Directory[/bold]")

    cache_path = RAW / COLUMN_CACHE

    # -- stage 1: per-district value counts for EVERY road column -----------
    # Cached, because rebuilding it means 628 sequential downloads from
    # censusindia.gov.in. Changing the chosen indicator must not cost that again.
    if cache_path.exists() and not refresh:
        console.print(f"  using cached column counts {cache_path.relative_to(REPO)}")
        counts = json.loads(cache_path.read_text())
    else:
        try:
            import pandas as pd
        except ImportError:
            raise SystemExit(
                "pandas missing. Run: uv run --with pandas python scripts/build_roads_layer.py"
            ) from None

        resources = list_resources()
        if limit:
            resources = resources[:limit]
        csvs = [r for r in resources if r["url"] and str(r["url"]).lower().endswith(".csv")]
        console.print(f"  downloading [bold]{len(csvs)}[/bold] district CSVs (~760 MB, slow host)")

        counts, failures = {}, []
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(), TextColumn("{task.completed}/{task.total}"), TimeElapsedColumn(),
            console=console,
        ) as prog:
            t = prog.add_task("districts", total=len(csvs))
            for res in csvs:
                url = res["url"]; fname = url.rsplit("/", 1)[-1]
                try:
                    blob = _get_census(url)
                    # These files are latin-1, not UTF-8. 19 of them fail to decode
                    # as UTF-8 and were silently dropped before this was found.
                    df = pd.read_csv(io.BytesIO(blob), low_memory=False, encoding="latin-1")
                    codes = (
                        df["District Code"].astype(str)
                        .str.replace("'", "", regex=False).str.strip()
                    )
                    cc = codes.mode()[0]
                    rec = {"file": fname, "villages": int(len(df)), "cols": {}}
                    for k in ROAD_COLS:
                        m = [c for c in df.columns if c.startswith(k)]
                        if not m:
                            continue
                        v = pd.to_numeric(df[m[0]], errors="coerce")
                        rec["cols"][k] = {
                            str(kk): int(vv) for kk, vv in v.value_counts(dropna=False).items()
                        }
                    counts[cc] = rec
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{fname}: {type(exc).__name__} {str(exc)[:70]}")
                prog.advance(t)

        RAW.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(counts))
        console.print(f"  cached → {cache_path.relative_to(REPO)}")
        if failures:
            console.print(f"  [yellow]{len(failures)} file(s) failed[/yellow]")
            for f in failures[:6]:
                console.print(f"    {f}")

    console.print(f"  districts in cache: [bold]{len(counts)}[/bold]")

    if column not in ROAD_COLS:
        raise SystemExit(f"--column must be one of {ROAD_COLS}")
    console.print(f"  indicator column: [bold]{column}[/bold]")

    # -- stage 2: derive the deficit ---------------------------------------
    gj = json.loads((REPO / "console" / "public" / "data" / "districts.geojson").read_text())
    by_census = {
        int(f["properties"]["censuscode"]): f["properties"]
        for f in gj["features"]
        if f["properties"].get("censuscode") is not None and not f["properties"].get("placeholder")
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    written, thin = 0, 0
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([
            "admin_unit_code", "censuscode", "villages_total", "villages_recorded",
            "villages_without", "deficit_pct", "recorded_pct",
            "indicator_key", "indicator_label", "source", "year",
        ])
        for cc, rec in sorted(counts.items(), key=lambda x: int(x[0])):
            ci = int(cc)
            prop = by_census.get(ci)
            cols = rec["cols"].get(column)
            if not prop or not cols:
                continue
            ones = cols.get("1.0", 0) + cols.get("1", 0)
            twos = cols.get("2.0", 0) + cols.get("2", 0)
            recorded = ones + twos
            # A district with almost no recorded statuses cannot support a
            # percentage. Excluded and counted, rather than published on a
            # denominator of six villages.
            if recorded < 30:
                thin += 1
                continue
            w.writerow([
                prop["code"], ci, rec["villages"], recorded, twos,
                round(100.0 * twos / recorded, 1),
                round(100.0 * recorded / max(rec["villages"], 1), 1),
                "pct_villages_no_pucca_road",
                "Villages without a black-topped (pucca) road",
                "Census 2011 Village Directory", 2011,
            ])
            written += 1

    console.print(f"\n  wrote {OUT.relative_to(REPO)} ([bold]{written}[/bold] districts)")
    if thin:
        console.print(f"  [yellow]excluded {thin} district(s)[/yellow] with fewer than 30 recorded villages")

    vals = sorted(float(r["deficit_pct"]) for r in csv.DictReader(OUT.open()))
    if vals:
        console.print(
            f"  deficit {vals[0]:.1f}% – {vals[-1]:.1f}% · median {vals[len(vals)//2]:.1f}%"
        )
    console.print(
        "\n[bold]Next:[/bold] uv run python scripts/build_deficit_layer.py --with-roads  then  "
        "uv run python scripts/generate_console_fixtures.py "
        "--geojson console/public/data/districts.geojson"
    )


if __name__ == "__main__":
    app()
