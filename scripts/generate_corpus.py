"""Phase 2 — the synthetic citizen signal corpus, and the table it lands in.

Two things at once: creates the `signal` table (task 2.1) and fills it with ~3,000
generated citizen reports (task 2.2).

**This layer is synthetic and is labelled as such in the interface itself.** We
have no government data access. What makes it useful rather than decorative is
that it is generated *from the real layer*: districts are sampled using their real
NFHS-5 deprivation, so the complaints cluster where the deprivation actually is.

**The participation bias is the point, not a flaw.** Districts are sampled with a
weight that multiplies real deficit by a synthetic connectivity score, so
well-connected districts are systematically over-represented relative to their
need — exactly the distortion every real grievance channel exhibits, and exactly
what the engine exists to detect and correct. Without the bias there is nothing
for the Silent Need quadrant to find.

**Signals are generated per NEED, not per signal.** A dry borewell is one problem
that forty people report in forty different ways. So the generator produces a
distinct need, then several citizen reports of that same need in different
languages and phrasings. That is what real intake looks like, and it is what makes
the Signals-vs-Needs number in the console mean something instead of being a ratio
of one.

Every generated signal carries `is_synthetic = true` in the warehouse. Nothing
downstream can mistake it for a citizen.

Usage:
    uv run python scripts/generate_corpus.py --target 3000
    uv run python scripts/generate_corpus.py --target 60 --dry-run   # cheap smoke test
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import typer
import yaml
from pydantic import BaseModel, Field
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data"
console = Console()

PROJECT = os.environ.get("CIVOS_PROJECT", "civos-in")
LOCATION = os.environ.get("CIVOS_VERTEX_LOCATION", "asia-south1")
BQ_LOCATION = os.environ.get("CIVOS_BQ_LOCATION", "asia-south1")
DATASET = os.environ.get("CIVOS_BQ_DATASET", "civos")
MODEL = os.environ.get("CIVOS_GEMINI_MODEL", "gemini-2.5-flash")

SEED = 20260815

# Languages the corpus is written in, with the states where each is plausible.
# Kept here rather than in core/ — this is country adapter territory, and the
# lint would fail the build if it drifted into core.
LANGS: dict[str, dict] = {
    "hi": {"name": "Hindi", "states": {"Uttar Pradesh", "Bihar", "Madhya Pradesh", "Rajasthan",
                                       "Haryana", "Jharkhand", "Chhattisgarh", "Uttaranchal", "Delhi"}},
    "mr": {"name": "Marathi", "states": {"Maharashtra"}},
    "bn": {"name": "Bengali", "states": {"West Bengal", "Tripura", "Assam"}},
    "ta": {"name": "Tamil", "states": {"Tamil Nadu", "Puducherry"}},
    "te": {"name": "Telugu", "states": {"Andhra Pradesh"}},
    "kn": {"name": "Kannada", "states": {"Karnataka"}},
    "ml": {"name": "Malayalam", "states": {"Kerala"}},
    "gu": {"name": "Gujarati", "states": {"Gujarat", "Daman and Diu", "Dadra and Nagar Haveli"}},
    "or": {"name": "Odia", "states": {"Orissa"}},
    "pa": {"name": "Punjabi", "states": {"Punjab", "Chandigarh"}},
    "as": {"name": "Assamese", "states": {"Assam"}},
    "en": {"name": "English", "states": set()},  # plausible anywhere
}


# ISO 639-2/3 codes the model sometimes emits instead of the 639-1 code.
_THREE_TO_TWO = {"ory": "or", "asm": "as", "ben": "bn", "eng": "en", "hin": "hi",
                 "mar": "mr", "tam": "ta", "tel": "te", "kan": "kn", "mal": "ml",
                 "guj": "gu", "pan": "pa", "urd": "ur"}


def normalise_lang(tag: str) -> tuple[str, bool]:
    """Canonical base language + whether the report is code-mixed.

    Left to itself the model invents tags: `hi-Latn-code-mixed`, `lang-en`,
    `kn-mix`, `en-hi`. Forty-five distinct "languages" came out of twelve. That
    matters beyond tidiness — SPEC §9 requires each dossier to report how many
    distinct languages its signals arrived in, and an inflated count is a claim
    about reach that is not true.

    Rule: the base language is the first recognised subtag; a second recognised
    language subtag, or an explicit mix/Latn marker on an Indic base, means
    code-mixed. Unrecognisable tags become `und` rather than being guessed at.
    """
    if not tag:
        return "und", False
    parts = [p.lower() for p in str(tag).replace("_", "-").split("-") if p]
    known: list[str] = []
    mixed = False
    for p in parts:
        c = _THREE_TO_TWO.get(p, p)
        if c in LANGS:
            known.append(c)
        elif p in {"mix", "mixed", "latn", "code"}:
            mixed = True
    if not known:
        return "und", mixed
    base = known[0]
    if len(set(known)) > 1:
        mixed = True
    return base, mixed


def langs_for(state: str) -> list[str]:
    opts = [c for c, v in LANGS.items() if state in v["states"]]
    return opts or ["hi", "en"]


# ---------------------------------------------------------------------------
# generation schema
# ---------------------------------------------------------------------------


class Report(BaseModel):
    lang: str = Field(description="BCP-47 code of the language actually used")
    text: str = Field(description="What the citizen said, in their own language")
    english: str = Field(description="Faithful English translation")
    severity: int = Field(ge=1, le=5)
    geo_hint: str = Field(default="", description="Vague place description as a citizen would give it")


class NeedCluster(BaseModel):
    """One distinct problem, reported by several different people."""

    need_summary: str = Field(description="One line, English, describing the single distinct problem")
    asset_type: str = Field(description="The physical asset involved")
    reports: list[Report] = Field(description="Different citizens reporting this same problem")


PROMPT = """Generate realistic citizen infrastructure complaints for a civic platform.

District: {district}, {state}, India
Sector: {sector} ({indicator})
Measured deprivation in this district: {deficit:.1f}% of households affected

Produce ONE distinct problem — a single specific broken or missing thing, not a
general grievance — and then {n} DIFFERENT people reporting that same problem.

Requirements:
- Write each report the way an ordinary person actually speaks: short, concrete,
  often annoyed, never in official or departmental vocabulary.
- Use these languages across the reports: {langs}. Write in the native script.
- At least one report must be naturally code-mixed with English, the way real
  Indian speech mixes mid-sentence. Do not make every report code-mixed.
- Vary the phrasing substantially. These are different people, not paraphrases —
  different details, different lengths, different concerns about the same object.
- geo_hint should be vague and human: "near the school", "the hamlet behind the
  temple", "our ward". Do NOT name the district in every report; real citizens
  usually assume you know where they are.
- severity 1-5 reflects how bad the thing is, and should be roughly consistent
  across reports of the same problem, varying by at most 1.
- The problem must be plausible for a district where {deficit:.0f}% of households
  face this deprivation. Do not invent a crisis in a well-served district.

Asset types appropriate to this sector: {assets}
"""


def rnd_from(*parts: str) -> float:
    h = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(h[:8], "big") / float(1 << 64)


# ---------------------------------------------------------------------------


def build_plan(target: int, rng: random.Random) -> list[dict]:
    """Choose which (district, sector) pairs get how many signals.

    The sampling weight IS the participation bias:

        weight = real_deficit × connectivity^1.6

    Real deprivation says where problems are; connectivity says who can report
    them. Multiplying the two reproduces the distortion the product exists to
    correct — the poorest, least connected districts end up under-represented
    relative to their measured need, which is what makes the Silent Need quadrant
    populate with districts that genuinely deserve attention.
    """
    units = {r["admin_unit_code"]: r for r in csv.DictReader((OUT / "dim_admin_unit.csv").open())}
    deficits: dict[tuple[str, str], float] = {}
    for r in csv.DictReader((OUT / "fact_deficit_indicator.csv").open()):
        key = (r["admin_unit_code"], r["sector"])
        deficits.setdefault(key, []).append(float(r["deficit_pct"]))
    sector_deficit = {k: sum(v) / len(v) for k, v in deficits.items()}

    pool: list[tuple[tuple[str, str], float]] = []
    for (code, sector), deficit in sector_deficit.items():
        # Same deterministic connectivity the console fixture uses, so the two
        # views of the same synthetic world agree.
        conn = rnd_from("conn", code)
        weight = deficit * (conn ** 1.6) + 0.05
        pool.append(((code, sector), weight))

    keys = [k for k, _ in pool]
    weights = [w for _, w in pool]

    plan: dict[tuple[str, str], int] = Counter()
    # Each draw is one need cluster of 2-8 reports.
    drawn = 0
    while drawn < target:
        (code, sector) = rng.choices(keys, weights=weights, k=1)[0]
        n = rng.choices([2, 3, 4, 5, 6, 8], weights=[26, 24, 18, 14, 10, 8], k=1)[0]
        plan[(code, sector)] += n
        drawn += n

    return [
        {
            "code": code,
            "sector": sector,
            "n": n,
            "district": units[code]["name"],
            "state": units[code]["state"],
            "deficit": sector_deficit[(code, sector)],
        }
        for (code, sector), n in plan.items()
    ]


def generate(job: dict, sectors_cfg: dict, client, rng: random.Random) -> list[dict]:
    from google.genai import types

    sector = sectors_cfg[job["sector"]]
    langs = langs_for(job["state"])
    chosen = list({rng.choice(langs) for _ in range(3)} | {"en"})

    prompt = PROMPT.format(
        district=job["district"], state=job["state"], sector=sector["label"],
        indicator=sector["indicator"]["label"], deficit=job["deficit"],
        n=min(job["n"], 8), langs=", ".join(LANGS[c]["name"] for c in chosen),
        assets=", ".join(sector["asset_types"]),
    )

    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=NeedCluster,
                temperature=1.0,
            ),
        )
        cluster = NeedCluster.model_validate_json(resp.text or "{}")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]gen failed[/red] {job['district']}/{job['sector']}: {str(exc)[:90]}")
        return []

    need_id = f"N-{uuid.uuid5(uuid.NAMESPACE_URL, job['code'] + job['sector'] + cluster.need_summary).hex[:12]}"
    today = date(2026, 8, 15)
    rows: list[dict] = []
    for i, rep in enumerate(cluster.reports):
        sid = f"S-{uuid.uuid5(uuid.NAMESPACE_URL, need_id + str(i) + rep.text[:40]).hex[:14]}"
        lang, mixed = normalise_lang(rep.lang)
        # Recency spread over the 90-day decay window in SPEC §8.
        age = int(rnd_from("age", sid) * 120)
        # Image attachment tracks connectivity — camera ownership is not evenly
        # distributed, and SPEC §13 wants that skew visible, not hidden.
        conn = rnd_from("conn", job["code"])
        has_image = rnd_from("img", sid) < (0.10 + 0.45 * conn)
        rows.append({
            "signal_id": sid,
            "submission_id": f"SUB-{sid[2:]}",
            "need_cluster_id": need_id,
            "channel": "web" if rnd_from("ch", sid) < 0.55 else "telegram",
            "modality": "voice" if rnd_from("mo", sid) < 0.45 else "text",
            "received_at": (today - timedelta(days=age)).isoformat(),
            "detected_language": lang,
            "is_code_mixed": mixed,
            "raw_text": rep.text,
            "english_normalised": rep.english,
            "sector": job["sector"],
            "severity": max(1, min(5, rep.severity)),
            "admin_unit_code": job["code"],
            "admin_level": "level-2",
            "geo_confidence": "high" if has_image and rnd_from("exif", sid) < 0.45 else "inferred",
            "geo_hint": rep.geo_hint[:200],
            "has_image": has_image,
            "asset_type": cluster.asset_type if has_image else None,
            "condition_flags": None,
            "visual_description": None,
            "image_thumb_uri": None,
            "people_present": False,
            "project_id": None,
            "funded_at": None,
            "is_synthetic": True,
            "need_summary": cluster.need_summary,
        })
    return rows


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS `{p}.{d}.signal` (
  signal_id STRING NOT NULL,
  submission_id STRING,
  need_cluster_id STRING,
  channel STRING,
  modality STRING,
  received_at DATE,
  detected_language STRING,
  is_code_mixed BOOL,
  raw_text STRING,
  english_normalised STRING,
  sector STRING,
  severity INT64,
  admin_unit_code STRING,
  admin_level STRING,
  geo_confidence STRING,
  geo_hint STRING,
  has_image BOOL,
  asset_type STRING,
  condition_flags ARRAY<STRING>,
  visual_description STRING,
  image_thumb_uri STRING,
  people_present BOOL,
  embedding ARRAY<FLOAT64>,
  project_id STRING,
  funded_at DATE,
  is_synthetic BOOL,
  need_summary STRING
)
PARTITION BY received_at
CLUSTER BY admin_unit_code, sector
"""


def main(
    target: int = typer.Option(3000, "--target", help="Approximate number of signals"),
    workers: int = typer.Option(10, "--workers"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Generate but do not load to BigQuery"),
    from_file: bool = typer.Option(False, "--from-file",
                                   help="Re-normalise and reload data/signals.jsonl without regenerating"),
) -> None:
    from google import genai

    if from_file:
        rows = [json.loads(l) for l in (OUT / "signals.jsonl").open(encoding="utf-8")]
        for r in rows:
            r["detected_language"], r["is_code_mixed"] = normalise_lang(r["detected_language"])
        with (OUT / "signals.jsonl").open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        console.print(f"Re-normalised {len(rows)} signals → "
                      f"{len({r['detected_language'] for r in rows})} distinct languages, "
                      f"{sum(1 for r in rows if r['is_code_mixed'])} code-mixed")
        _load(rows)
        return

    rng = random.Random(SEED)
    console.rule(f"[bold]Phase 2 — signal corpus[/bold] · target {target}")

    sectors_cfg = {
        s["key"]: s for s in yaml.safe_load((REPO / "adapters" / "in" / "sectors.yaml").read_text())["sectors"]
    }
    plan = build_plan(target, rng)
    planned = sum(j["n"] for j in plan)
    console.print(f"  {len(plan)} need clusters across "
                  f"{len({j['code'] for j in plan})} districts → ~{planned} signals")

    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    rows: list[dict] = []
    with Progress(TextColumn("[progress.description]{task.description}"), BarColumn(),
                  TextColumn("{task.completed}/{task.total}"), TimeElapsedColumn(),
                  console=console) as prog:
        t = prog.add_task("generating", total=len(plan))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(generate, j, sectors_cfg, client, random.Random(SEED + i))
                    for i, j in enumerate(plan)]
            for f in as_completed(futs):
                rows.extend(f.result())
                prog.advance(t)

    if not rows:
        console.print("[red]No signals generated.[/red]")
        raise typer.Exit(2)

    # -- report the distribution, because the bias is the deliverable ---------
    by_lang = Counter(r["detected_language"] for r in rows)
    by_sector = Counter(r["sector"] for r in rows)
    needs = len({r["need_cluster_id"] for r in rows})
    districts = len({r["admin_unit_code"] for r in rows})
    with_image = sum(1 for r in rows if r["has_image"])
    exif = sum(1 for r in rows if r["geo_confidence"] == "high")

    out = OUT / "signals.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    t = Table(title="Corpus")
    t.add_column("metric"); t.add_column("value", justify="right")
    t.add_row("signals", str(len(rows)))
    t.add_row("distinct needs", str(needs))
    t.add_row("dedup ratio (signals/needs)", f"{len(rows)/max(needs,1):.1f}×")
    t.add_row("districts covered", f"{districts}/537")
    t.add_row("languages", str(len(by_lang)))
    t.add_row("with photograph", f"{with_image} ({with_image/len(rows):.0%})")
    t.add_row("geo_confidence = high (EXIF)", f"{exif} ({exif/len(rows):.0%})")
    console.print(); console.print(t)
    console.print(f"  languages: {dict(by_lang.most_common())}")
    console.print(f"  sectors:   {dict(by_sector.most_common())}")
    console.print(f"  written to {out.relative_to(REPO)}")

    if dry_run:
        console.print("[yellow]--dry-run: not loading to BigQuery[/yellow]")
        return

    _load(rows)


def _load(rows: list[dict]) -> None:
    from google.cloud import bigquery

    bq = bigquery.Client(project=PROJECT, location=BQ_LOCATION)
    bq.query(f"DROP TABLE IF EXISTS `{PROJECT}.{DATASET}.signal`").result()
    bq.query(SCHEMA_SQL.format(p=PROJECT, d=DATASET)).result()
    console.print(f"  table `{PROJECT}.{DATASET}.signal` ready")

    job = bq.load_table_from_file(
        (OUT / "signals.jsonl").open("rb"),
        f"{PROJECT}.{DATASET}.signal",
        job_config=bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            autodetect=False,
            schema=bq.get_table(f"{PROJECT}.{DATASET}.signal").schema,
        ),
    )
    job.result()
    n = bq.get_table(f"{PROJECT}.{DATASET}.signal").num_rows
    console.print(f"  [green]loaded[/green] {PROJECT}.{DATASET}.signal — {n} rows")


if __name__ == "__main__":
    typer.run(main)
