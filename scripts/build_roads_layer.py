"""Roads & Transport deficit — Census 2011 Village Directory, all-weather road access.

Closes the one sector that had no real indicator. Four of five sectors come from
NFHS-5; road connectivity has no health-survey equivalent, so it needed its own
source. `docs/ROADS-SECTOR-GAP.md` records the six sources checked before this one
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

The indicator
-------------
Column **"All Weather Road (Status A(1)/NA(2))"** per village: 1 = available,
2 = not available, blank = not recorded.

    deficit_pct = 100 × villages with status 2 / villages with a recorded status

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
ROAD_COL = "All Weather Road"        # matched by prefix; full name carries a suffix

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
    keep_raw: bool = typer.Option(False, "--keep-raw", help="Cache the CSVs (~760 MB)"),
    limit: int = typer.Option(0, "--limit", help="Only process N districts (smoke test)"),
) -> None:
    console.rule("[bold]Roads & Transport — Census 2011 Village Directory[/bold]")

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
    console.print(f"  resources: [bold]{len(resources)}[/bold] · CSV: {len(csvs)}")

    RAW.mkdir(parents=True, exist_ok=True)
    per_district: dict[int, dict] = {}
    failures: list[str] = []

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(), TextColumn("{task.completed}/{task.total}"), TimeElapsedColumn(),
        console=console,
    ) as prog:
        t = prog.add_task("districts", total=len(csvs))
        for res in csvs:
            url = res["url"]
            name = url.rsplit("/", 1)[-1]
            cached = RAW / name
            try:
                if cached.exists():
                    blob = cached.read_bytes()
                else:
                    blob = _get_census(url)
                    if keep_raw:
                        cached.write_bytes(blob)

                df = pd.read_csv(io.BytesIO(blob), low_memory=False)
                road_cols = [c for c in df.columns if c.startswith(ROAD_COL)]
                if not road_cols:
                    failures.append(f"{name}: no '{ROAD_COL}' column")
                    prog.advance(t)
                    continue
                col = road_cols[0]

                # "'327" → 327. The leading apostrophe is Excel text-guarding.
                codes = (
                    df["District Code"].astype(str).str.replace("'", "", regex=False).str.strip()
                )
                vals = pd.to_numeric(df[col], errors="coerce")

                for code, grp in vals.groupby(codes):
                    try:
                        ci = int(code)
                    except ValueError:
                        continue
                    recorded = int(grp.isin([1, 2]).sum())
                    unconnected = int((grp == 2).sum())
                    d = per_district.setdefault(
                        ci, {"villages": 0, "recorded": 0, "unconnected": 0}
                    )
                    d["villages"] += int(len(grp))
                    d["recorded"] += recorded
                    d["unconnected"] += unconnected
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{name}: {type(exc).__name__} {str(exc)[:80]}")
            prog.advance(t)

    console.print(f"  district codes aggregated: [bold]{len(per_district)}[/bold]")
    if failures:
        console.print(f"  [yellow]failures: {len(failures)}[/yellow]")
        for f in failures[:8]:
            console.print(f"    {f}")

    # -- join onto our districts by all-India census code -------------------
    gj = json.loads((REPO / "console" / "public" / "data" / "districts.geojson").read_text())
    by_census: dict[int, dict] = {}
    for f in gj["features"]:
        p = f["properties"]
        if p.get("censuscode") is not None and not p.get("placeholder"):
            by_census[int(p["censuscode"])] = p

    OUT.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([
            "admin_unit_code", "censuscode", "villages_total", "villages_recorded",
            "villages_without_all_weather_road", "deficit_pct", "recorded_pct",
            "indicator_key", "indicator_label", "source", "year",
        ])
        for ci, d in sorted(per_district.items()):
            prop = by_census.get(ci)
            if not prop or d["recorded"] == 0:
                continue
            deficit = 100.0 * d["unconnected"] / d["recorded"]
            recorded_pct = 100.0 * d["recorded"] / max(d["villages"], 1)
            w.writerow([
                prop["code"], ci, d["villages"], d["recorded"], d["unconnected"],
                round(deficit, 1), round(recorded_pct, 1),
                "pct_villages_no_all_weather_road",
                "Villages without all-weather road access",
                "Census 2011 Village Directory", 2011,
            ])
            written += 1

    unmatched = [c for c in per_district if c not in by_census]
    console.print(f"\n  wrote {OUT.relative_to(REPO)} ([bold]{written}[/bold] districts)")
    console.print(f"  census codes with no boundary match: {len(unmatched)}")
    if written:
        vals = []
        for row in csv.DictReader(OUT.open()):
            vals.append(float(row["deficit_pct"]))
        vals.sort()
        console.print(
            f"  deficit range {vals[0]:.1f}% – {vals[-1]:.1f}% · median {vals[len(vals)//2]:.1f}%"
        )
    console.print(
        "\n[bold]Next:[/bold] uv run python scripts/build_deficit_layer.py  then  "
        "uv run python scripts/generate_console_fixtures.py "
        "--geojson console/public/data/districts.geojson"
    )


if __name__ == "__main__":
    app()
