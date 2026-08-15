"""GATE 0 — empirical probe of BigQuery ML/AI capability in the chosen region.

Why this exists: plan.md Gate 0 forks the whole architecture on whether BigQuery's
AI/ML functions are available and quota-usable in the region we picked. Google's
docs are inconsistent about regional availability and the function surface has
moved (AI.GENERATE_EMBEDDING now sits alongside ML.GENERATE_EMBEDDING), so this
script establishes the answer by execution rather than by reading.

It is deliberately standalone — no import from core/ — so it can be run on a bare
checkout before anything else exists, and so a reviewer can audit it in one file.

Every probe tries several syntax variants and records the exact SQL and the exact
error for each. A failing probe is a *successful gate*: the point is to know today.

Usage:
    uv run python scripts/gate0_probe.py
    uv run python scripts/gate0_probe.py --keep   # don't drop the probe dataset
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import typer
from google.api_core import exceptions as gexc
from google.cloud import bigquery
from rich.console import Console
from rich.table import Table

REPO = Path(__file__).resolve().parent.parent
console = Console()

PROJECT = os.environ.get("CIVOS_PROJECT", "civos-in")
LOCATION = os.environ.get("CIVOS_BQ_LOCATION", "asia-south1")
CONNECTION = os.environ.get("CIVOS_BQ_CONNECTION", "civos_vertex")
PROBE_DS = os.environ.get("CIVOS_PROBE_DATASET", "civos_probe")

# Fully-qualified connection id as BigQuery AI functions expect it.
CONN_ID = f"{PROJECT}.{LOCATION}.{CONNECTION}"

# Retry window for IAM propagation on a freshly-created connection service account.
IAM_RETRY_SECONDS = 120


# ---------------------------------------------------------------------------
# result model
# ---------------------------------------------------------------------------


# Errors that prove the feature EXISTS but a precondition is unmet. Classifying
# these as "unavailable" would mislead anyone reading the gate, so they get their
# own status. Example: CREATE VECTOR INDEX requires 5,000 rows; a 5-row probe
# failing on row count says nothing about regional availability.
SOFT_FAIL_PATTERNS: list[tuple[str, str]] = [
    ("smaller than min allowed", "Feature exists; the probe table is below the minimum row count."),
    ("requires at least", "Feature exists; a size/volume precondition is unmet at probe scale."),
]


def classify(error: str | None) -> tuple[str, str | None]:
    """Return (status, note) for a failed attempt."""
    if error is None:
        return "PASS", None
    low = error.lower()
    for pat, note in SOFT_FAIL_PATTERNS:
        if pat in low:
            return "SUPPORTED_NEEDS_SCALE", note
    return "FAIL", None


@dataclass
class Attempt:
    label: str
    sql: str
    ok: bool
    elapsed_s: float
    error: str | None = None
    sample: str | None = None
    status: str = "PASS"
    note: str | None = None


@dataclass
class Probe:
    name: str
    family: str
    question: str
    fallback: str
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return any(a.ok for a in self.attempts)

    @property
    def needs_scale(self) -> bool:
        """Not exercisable at probe scale, but proven to exist in this region."""
        return not self.ok and any(a.status == "SUPPORTED_NEEDS_SCALE" for a in self.attempts)

    @property
    def winner(self) -> Attempt | None:
        return next((a for a in self.attempts if a.ok), None)

    @property
    def verdict_label(self) -> str:
        if self.ok:
            return "✅ available"
        if self.needs_scale:
            return "⚠️ exists, needs scale"
        return "❌ unavailable"


# ---------------------------------------------------------------------------
# query helper
# ---------------------------------------------------------------------------


def _is_iam_propagation_error(msg: str) -> bool:
    m = msg.lower()
    return "permission" in m and ("denied" in m or "does not have" in m or "aiplatform" in m)


def run_sql(client: bigquery.Client, sql: str, *, retry_iam: bool = True) -> tuple[bool, str | None, str | None]:
    """Execute SQL. Returns (ok, error, first-row-sample).

    Retries transient IAM-propagation failures, because a connection service
    account granted seconds ago is easily mistaken for an unsupported region.
    """
    deadline = time.monotonic() + (IAM_RETRY_SECONDS if retry_iam else 0)
    last_err: str | None = None
    while True:
        try:
            job = client.query(sql, location=LOCATION)
            rows = list(job.result(timeout=300))
            sample = None
            if rows:
                d = dict(rows[0].items())
                sample = json.dumps(d, default=str)[:400]
            return True, None, sample
        except (gexc.GoogleAPICallError, gexc.RetryError, Exception) as exc:  # noqa: BLE001
            last_err = str(exc).split("\n\nLocation:")[0].strip()
            if retry_iam and _is_iam_propagation_error(last_err) and time.monotonic() < deadline:
                console.print("    [dim]IAM not propagated yet, retrying in 15s…[/dim]")
                time.sleep(15)
                continue
            return False, last_err[:1200], None


def probe(client: bigquery.Client, p: Probe, variants: list[tuple[str, str]]) -> Probe:
    console.print(f"[bold]· {p.name}[/bold] — {p.question}")
    for label, sql in variants:
        t0 = time.monotonic()
        ok, err, sample = run_sql(client, sql)
        el = round(time.monotonic() - t0, 1)
        status, note = ("PASS", None) if ok else classify(err)
        p.attempts.append(
            Attempt(label=label, sql=sql.strip(), ok=ok, elapsed_s=el, error=err,
                    sample=sample, status=status, note=note)
        )
        if ok:
            console.print(f"    [green]PASS[/green] {label} ({el}s)")
            break
        colour = "yellow" if status == "SUPPORTED_NEEDS_SCALE" else "red"
        console.print(f"    [{colour}]{status}[/{colour}] {label} ({el}s) — {(err or '')[:150]}")
    return p


# ---------------------------------------------------------------------------
# model discovery on the Vertex side
# ---------------------------------------------------------------------------


def discover_vertex(results: dict) -> None:
    """Confirm the FALLBACK_VERTEX path actually works, and learn live model names.

    Without this, a FALLBACK_VERTEX verdict would be a hope rather than a plan.
    """
    console.print("\n[bold]· vertex_direct[/bold] — does the fallback path work at all?")
    try:
        from google import genai

        client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
        gen_models: list[str] = []
        try:
            for m in client.models.list():
                nm = getattr(m, "name", "") or ""
                gen_models.append(nm.split("/")[-1])
        except Exception as exc:  # noqa: BLE001
            results["vertex_model_list_error"] = str(exc)[:400]

        results["vertex_models_seen"] = sorted(set(gen_models))[:60]

        for candidate in GEMINI_CANDIDATES:
            try:
                r = client.models.generate_content(model=candidate, contents="Reply with the single word OK.")
                results["vertex_generate"] = {"ok": True, "model": candidate, "text": (r.text or "").strip()[:60]}
                console.print(f"    [green]PASS[/green] generate_content via {candidate}")
                break
            except Exception as exc:  # noqa: BLE001
                results.setdefault("vertex_generate_errors", {})[candidate] = str(exc)[:300]
        else:
            results["vertex_generate"] = {"ok": False}
            console.print("    [red]FAIL[/red] generate_content on every candidate model")

        for candidate in EMBED_CANDIDATES:
            try:
                r = client.models.embed_content(model=candidate, contents=["dry handpump in our hamlet"])
                dim = len(r.embeddings[0].values) if r.embeddings else 0
                results["vertex_embed"] = {"ok": True, "model": candidate, "dims": dim}
                console.print(f"    [green]PASS[/green] embed_content via {candidate} ({dim} dims)")
                break
            except Exception as exc:  # noqa: BLE001
                results.setdefault("vertex_embed_errors", {})[candidate] = str(exc)[:300]
        else:
            results["vertex_embed"] = {"ok": False}
            console.print("    [red]FAIL[/red] embed_content on every candidate model")

    except Exception as exc:  # noqa: BLE001
        results["vertex_error"] = str(exc)[:600]
        console.print(f"    [red]FAIL[/red] google-genai client — {exc}")


# Tried in order. Newest first so the probe self-updates as Google ships models.
GEMINI_CANDIDATES = [
    "gemini-3-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
]
EMBED_CANDIDATES = [
    "gemini-embedding-001",
    "text-embedding-005",
    "text-multilingual-embedding-002",
]


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

FIXTURES = [
    (
        "probe_text",
        f"""
        CREATE OR REPLACE TABLE `{PROJECT}.{PROBE_DS}.probe_text` AS
        SELECT * FROM UNNEST([
          STRUCT('s1' AS id, 'The handpump in our hamlet has been dry for five months.' AS content),
          ('s2', 'Borewell band pada hai, gaon mein paani nahi aa raha.'),
          ('s3', 'The street light outside the school has been broken for weeks.')
        ])
        """,
    ),
    (
        "probe_vec",
        f"""
        CREATE OR REPLACE TABLE `{PROJECT}.{PROBE_DS}.probe_vec` AS
        SELECT * FROM UNNEST([
          STRUCT('a' AS id, [1.0, 0.0, 0.0, 0.0] AS emb),
          ('b', [0.9, 0.1, 0.0, 0.0]),
          ('c', [0.0, 0.0, 1.0, 0.0]),
          ('d', [0.0, 0.0, 0.9, 0.1]),
          ('e', [0.5, 0.5, 0.0, 0.0])
        ])
        """,
    ),
    (
        "probe_series",
        f"""
        CREATE OR REPLACE TABLE `{PROJECT}.{PROBE_DS}.probe_series` AS
        SELECT
          DATE_ADD(DATE '2026-01-01', INTERVAL n DAY) AS ts,
          10.0 + MOD(n, 7) + n * 0.3 AS value
        FROM UNNEST(GENERATE_ARRAY(0, 59)) AS n
        """,
    ),
]


# ---------------------------------------------------------------------------
# probe definitions
# ---------------------------------------------------------------------------


def build_probes() -> list[tuple[Probe, list[tuple[str, str]]]]:
    t_text = f"`{PROJECT}.{PROBE_DS}.probe_text`"
    t_vec = f"`{PROJECT}.{PROBE_DS}.probe_vec`"
    t_series = f"`{PROJECT}.{PROBE_DS}.probe_series`"
    global_ep = "projects/{p}/locations/global/publishers/google/models/{m}"

    out: list[tuple[Probe, list[tuple[str, str]]]] = []

    # -- 1. GIS ------------------------------------------------------------
    out.append(
        (
            Probe(
                name="st_functions",
                family="gis",
                question="EXIF geo path (P0-6) and district reconciliation",
                fallback="None needed — GIS is core BigQuery",
            ),
            [
                (
                    "ST_CONTAINS / ST_GEOGPOINT / ST_DWITHIN",
                    """
                    SELECT
                      ST_CONTAINS(
                        ST_GEOGFROMTEXT('POLYGON((72.7 18.8, 73.2 18.8, 73.2 19.3, 72.7 19.3, 72.7 18.8))'),
                        ST_GEOGPOINT(72.87, 19.07)) AS inside,
                      ST_DWITHIN(ST_GEOGPOINT(72.87, 19.07), ST_GEOGPOINT(72.88, 19.08), 5000) AS near,
                      ST_AREA(ST_GEOGFROMTEXT('POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))')) AS area_m2
                    """,
                )
            ],
        )
    )

    # -- 2. embeddings -----------------------------------------------------
    # Inline-connection form (no CREATE MODEL) — the newer surface.
    embed_variants: list[tuple[str, str]] = []
    for m in EMBED_CANDIDATES:
        embed_variants.append(
            (
                f"AI.GENERATE_EMBEDDING connection_id · endpoint={m}",
                f"""
                SELECT ARRAY_LENGTH(embedding) AS dims
                FROM AI.GENERATE_EMBEDDING(
                  TABLE {t_text},
                  connection_id => '{CONN_ID}',
                  endpoint => '{m}'
                )
                LIMIT 1
                """,
            )
        )
    out.append(
        (
            Probe(
                name="embedding_inline",
                family="embedding",
                question="Is there an inline (no CREATE MODEL) embedding surface in this region?",
                fallback="Vertex AI embed_content via google-genai; store ARRAY<FLOAT64> in BigQuery",
            ),
            embed_variants,
        )
    )

    # Remote-model form, the one SPEC.md P0-7 assumes.
    remote_embed: list[tuple[str, str]] = []
    for m in EMBED_CANDIDATES:
        safe = m.replace("-", "_")
        remote_embed.append(
            (
                f"CREATE MODEL REMOTE + ML.GENERATE_EMBEDDING · endpoint={m}",
                f"""
                CREATE OR REPLACE MODEL `{PROJECT}.{PROBE_DS}.emb_{safe}`
                  REMOTE WITH CONNECTION `{CONN_ID}`
                  OPTIONS (ENDPOINT = '{m}');
                SELECT ARRAY_LENGTH(ml_generate_embedding_result) AS dims
                FROM ML.GENERATE_EMBEDDING(
                  MODEL `{PROJECT}.{PROBE_DS}.emb_{safe}`,
                  (SELECT content FROM {t_text})
                )
                LIMIT 1
                """,
            )
        )
    out.append(
        (
            Probe(
                name="embedding_remote_model",
                family="embedding",
                question="ML.GENERATE_EMBEDDING via a REMOTE model (SPEC P0-7 assumption)",
                fallback="Vertex AI embed_content via google-genai",
            ),
            remote_embed,
        )
    )

    # -- 3. text generation ------------------------------------------------
    gen_variants: list[tuple[str, str]] = []
    for m in GEMINI_CANDIDATES:
        gen_variants.append(
            (
                f"AI.GENERATE inline · endpoint={m}",
                f"""
                SELECT AI.GENERATE(
                  'Reply with the single word OK.',
                  connection_id => '{CONN_ID}',
                  endpoint => '{m}'
                ).result AS out
                """,
            )
        )
    for m in GEMINI_CANDIDATES:
        gen_variants.append(
            (
                f"AI.GENERATE global endpoint · {m}",
                f"""
                SELECT AI.GENERATE(
                  'Reply with the single word OK.',
                  connection_id => '{CONN_ID}',
                  endpoint => '{global_ep.format(p=PROJECT, m=m)}'
                ).result AS out
                """,
            )
        )
    out.append(
        (
            Probe(
                name="ai_generate",
                family="generation",
                question="Can grounded dossier text (SPEC §9) be generated inside SQL?",
                fallback="Call Gemini from the FastAPI layer — the dossier is one call, so this is cheap",
            ),
            gen_variants,
        )
    )

    gen_remote: list[tuple[str, str]] = []
    for m in GEMINI_CANDIDATES:
        safe = m.replace("-", "_").replace(".", "_")
        gen_remote.append(
            (
                f"CREATE MODEL REMOTE + ML.GENERATE_TEXT · endpoint={m}",
                f"""
                CREATE OR REPLACE MODEL `{PROJECT}.{PROBE_DS}.gen_{safe}`
                  REMOTE WITH CONNECTION `{CONN_ID}`
                  OPTIONS (ENDPOINT = '{m}');
                SELECT ml_generate_text_llm_result AS out
                FROM ML.GENERATE_TEXT(
                  MODEL `{PROJECT}.{PROBE_DS}.gen_{safe}`,
                  (SELECT 'Reply with the single word OK.' AS prompt),
                  STRUCT(TRUE AS flatten_json_output)
                )
                """,
            )
        )
    out.append(
        (
            Probe(
                name="ml_generate_text",
                family="generation",
                question="ML.GENERATE_TEXT via a REMOTE model",
                fallback="Call Gemini from the FastAPI layer",
            ),
            gen_remote,
        )
    )

    # -- 4. vector search --------------------------------------------------
    out.append(
        (
            Probe(
                name="vector_search",
                family="vector",
                question="Dedup → distinct needs (P0-7): the Signals-vs-Needs number",
                fallback="scikit-learn agglomerative clustering on embeddings pulled client-side",
            ),
            [
                (
                    "VECTOR_SEARCH brute force, COSINE",
                    f"""
                    SELECT base.id AS match_id, distance
                    FROM VECTOR_SEARCH(
                      TABLE {t_vec}, 'emb',
                      (SELECT [1.0, 0.0, 0.0, 0.0] AS emb),
                      top_k => 2,
                      distance_type => 'COSINE')
                    ORDER BY distance
                    """,
                ),
                (
                    "VECTOR_SEARCH with query_column_to_search",
                    f"""
                    SELECT base.id AS match_id, distance
                    FROM VECTOR_SEARCH(
                      TABLE {t_vec}, 'emb',
                      (SELECT [1.0, 0.0, 0.0, 0.0] AS qemb),
                      query_column_to_search => 'qemb',
                      top_k => 2)
                    ORDER BY distance
                    """,
                ),
            ],
        )
    )

    out.append(
        (
            Probe(
                name="vector_index_ddl",
                family="vector",
                question="Will a vector index be available at 3,000-signal scale?",
                fallback="Brute-force VECTOR_SEARCH is fine at our corpus size; index is an optimisation",
            ),
            [
                (
                    "CREATE VECTOR INDEX IVF/COSINE",
                    f"""
                    CREATE OR REPLACE VECTOR INDEX probe_idx
                    ON {t_vec}(emb)
                    OPTIONS (index_type = 'IVF', distance_type = 'COSINE')
                    """,
                )
            ],
        )
    )

    # -- 5. forecast -------------------------------------------------------
    out.append(
        (
            Probe(
                name="arima_plus",
                family="forecast",
                question="90-day demand forecast (P1-1) in ~10 lines of SQL",
                fallback="statsmodels ARIMA in the API layer",
            ),
            [
                (
                    "CREATE MODEL ARIMA_PLUS + ML.FORECAST",
                    f"""
                    CREATE OR REPLACE MODEL `{PROJECT}.{PROBE_DS}.probe_arima`
                      OPTIONS (
                        model_type = 'ARIMA_PLUS',
                        time_series_timestamp_col = 'ts',
                        time_series_data_col = 'value',
                        horizon = 30,
                        auto_arima = TRUE
                      ) AS
                    SELECT ts, value FROM {t_series};
                    SELECT forecast_timestamp, forecast_value
                    FROM ML.FORECAST(MODEL `{PROJECT}.{PROBE_DS}.probe_arima`,
                                     STRUCT(30 AS horizon, 0.8 AS confidence_level))
                    LIMIT 1
                    """,
                )
            ],
        )
    )

    return out


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

BLOCKING_FAMILIES = {"embedding", "generation", "vector", "forecast", "gis"}


def verdict_for(probes: list[Probe]) -> tuple[str, list[str]]:
    by_family: dict[str, bool] = {}
    for p in probes:
        by_family[p.family] = by_family.get(p.family, False) or p.ok
    missing = sorted(f for f in BLOCKING_FAMILIES if not by_family.get(f, False))
    return ("PROCEED_BQML" if not missing else "FALLBACK_VERTEX"), missing


def write_report(probes: list[Probe], vertex: dict, out_md: Path, out_json: Path) -> str:
    verdict, missing = verdict_for(probes)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []
    lines.append("# GATE 0 — BigQuery ML/AI capability probe")
    lines.append("")
    lines.append(f"**Verdict: `{verdict}`**")
    lines.append("")
    lines.append(f"| | |\n|---|---|")
    lines.append(f"| Run at | {stamp} |")
    lines.append(f"| Project | `{PROJECT}` |")
    lines.append(f"| BigQuery location | `{LOCATION}` |")
    lines.append(f"| Connection | `{CONN_ID}` |")
    lines.append("")
    if verdict == "PROCEED_BQML":
        lines.append(
            "Every capability the architecture depends on is available in this region. "
            "Proceed as specified in SPEC.md — BigQuery is the analytical spine."
        )
    else:
        lines.append(
            "One or more required capabilities are unavailable in this region: "
            + ", ".join(f"`{m}`" for m in missing)
            + ". **BigQuery remains the warehouse in this region** — data residency is unchanged. "
            "Only the failing functions move to the fallback listed against each probe below."
        )
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Probe | Family | Result | Working form | Fallback if unavailable |")
    lines.append("|---|---|---|---|---|")
    for p in probes:
        form = f"`{p.winner.label}`" if p.winner else "—"
        lines.append(f"| `{p.name}` | {p.family} | {p.verdict_label} | {form} | {p.fallback} |")
    lines.append("")

    scale_notes = [(p, a) for p in probes if p.needs_scale
                   for a in p.attempts if a.status == "SUPPORTED_NEEDS_SCALE"]
    if scale_notes:
        lines.append(
            "**⚠️ exists, needs scale is not a failure.** The feature is present in this region; "
            "the probe table is simply too small to exercise it. Read the error before treating "
            "one of these as a blocker:"
        )
        lines.append("")
        for p, a in scale_notes:
            lines.append(f"- `{p.name}` — {a.note} Mitigation: {p.fallback}")
        lines.append("")

    lines.append("## Fallback path viability (Vertex AI direct)")
    lines.append("")
    lines.append(
        "Probed regardless of the verdict, because a `FALLBACK_VERTEX` result is only a plan "
        "if the fallback is known to work."
    )
    lines.append("")
    vg = vertex.get("vertex_generate", {})
    ve = vertex.get("vertex_embed", {})
    lines.append("| Path | Result | Detail |")
    lines.append("|---|---|---|")
    lines.append(
        f"| Gemini generate via `google-genai` | {'✅' if vg.get('ok') else '❌'} | "
        f"{vg.get('model', '—')} → `{vg.get('text', '')}` |"
    )
    lines.append(
        f"| Embeddings via `google-genai` | {'✅' if ve.get('ok') else '❌'} | "
        f"{ve.get('model', '—')}, {ve.get('dims', 0)} dims |"
    )
    lines.append("")
    seen = vertex.get("vertex_models_seen") or []
    if seen:
        lines.append(f"Models visible to this project ({len(seen)} listed): "
                     + ", ".join(f"`{m}`" for m in seen[:30]))
        lines.append("")

    lines.append("## Evidence — every attempt, with the exact error")
    lines.append("")
    for p in probes:
        lines.append(f"### `{p.name}` — {p.question}")
        lines.append("")
        for a in p.attempts:
            lines.append(f"**{a.status}** · {a.label} · {a.elapsed_s}s")
            lines.append("")
            if a.note:
                lines.append(f"> {a.note}")
                lines.append("")
            lines.append("```sql")
            lines.append(a.sql)
            lines.append("```")
            lines.append("")
            if a.sample:
                lines.append(f"Result: `{a.sample}`")
                lines.append("")
            if a.error:
                lines.append("```")
                lines.append(a.error)
                lines.append("```")
                lines.append("")

    out_md.write_text("\n".join(lines) + "\n")
    out_json.write_text(
        json.dumps(
            {
                "verdict": verdict,
                "missing_families": missing,
                "run_at": stamp,
                "project": PROJECT,
                "location": LOCATION,
                "connection": CONN_ID,
                "vertex": vertex,
                "probes": [
                    {
                        "name": p.name,
                        "family": p.family,
                        "ok": p.ok,
                        "needs_scale": p.needs_scale,
                        "winner": p.winner.label if p.winner else None,
                        "attempts": [
                            {"label": a.label, "status": a.status, "ok": a.ok,
                             "elapsed_s": a.elapsed_s, "error": a.error, "note": a.note}
                            for a in p.attempts
                        ],
                    }
                    for p in probes
                ],
            },
            indent=2,
        )
        + "\n"
    )
    return verdict


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(keep: bool = typer.Option(False, "--keep", help="Keep the probe dataset for inspection")) -> None:
    console.rule(f"[bold]GATE 0[/bold] · {PROJECT} · {LOCATION}")
    client = bigquery.Client(project=PROJECT, location=LOCATION)

    console.print("\n[bold]Fixtures[/bold]")
    for name, sql in FIXTURES:
        ok, err, _ = run_sql(client, sql, retry_iam=False)
        console.print(f"  {'[green]ok[/green]' if ok else '[red]fail[/red]'} {name}"
                      + (f" — {err[:150]}" if err else ""))
        if not ok:
            raise typer.Exit(code=2)

    console.print("\n[bold]Probes[/bold]")
    probes: list[Probe] = []
    for p, variants in build_probes():
        probes.append(probe(client, p, variants))

    vertex: dict = {}
    discover_vertex(vertex)

    docs = REPO / "docs"
    docs.mkdir(exist_ok=True)
    verdict = write_report(probes, vertex, docs / "GATE0-RESULT.md", docs / "gate0-result.json")

    table = Table(title="GATE 0 result", show_lines=False)
    table.add_column("probe")
    table.add_column("family")
    table.add_column("result")
    table.add_column("working form", overflow="fold")
    for p in probes:
        if p.ok:
            cell = "[green]available[/green]"
        elif p.needs_scale:
            cell = "[yellow]exists, needs scale[/yellow]"
        else:
            cell = "[red]unavailable[/red]"
        table.add_row(p.name, p.family, cell, p.winner.label if p.winner else "—")
    console.print()
    console.print(table)
    console.rule(f"[bold]VERDICT: {verdict}[/bold]")
    console.print(f"Written to docs/GATE0-RESULT.md and docs/gate0-result.json")

    if not keep:
        run_sql(client, f"DROP SCHEMA IF EXISTS `{PROJECT}.{PROBE_DS}` CASCADE", retry_iam=False)
        console.print(f"[dim]Dropped probe dataset {PROBE_DS}.[/dim]")


if __name__ == "__main__":
    typer.run(main)
