"""Build the allocation candidate set and solve it from the command line.

The logic lives in `api/candidates.py` so the `/allocate` endpoint and this script
cannot drift. This file is the operator-facing wrapper: it prints the three lanes,
reports which constraints bound, and writes `allocation.json` for the console.

Usage:
    uv run python scripts/build_allocation_candidates.py
    uv run python scripts/build_allocation_candidates.py --budget 1200000000
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

# `package = false` in pyproject means the repo is never installed, so a script
# run directly cannot import `api` or `core` without this. pytest gets the same
# effect from `pythonpath = ["."]`; a bare `uv run python scripts/...` does not.
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from api.candidates import BUILDABLE_SHARE, DEFAULT_WEIGHTS, build_candidates  # noqa: E402
from core.allocation import Constraints, allocate  # noqa: E402

DATA = REPO / "console" / "public" / "data"
console = Console()

def main(
    budget: int = typer.Option(4_000_000_000, help="Delivery envelope, in the adapter's currency"),
    sector_cap: float = typer.Option(0.40),
    equity_floor: float = typer.Option(0.30),
    min_groups: int = typer.Option(8),
    outreach_reserve: float = typer.Option(0.05),
    write: bool = typer.Option(True, help="Write the candidate set for the console"),
):
    data = json.loads((DATA / "scores.json").read_text())
    cands = build_candidates(data, DEFAULT_WEIGHTS)
    console.rule("[bold]Allocation candidates[/bold]")
    console.print(f"Built [bold]{len(cands)}[/bold] candidates from {len(data['rows'])} scored rows")

    k = Constraints(
        budget=budget,
        sector_cap_share=sector_cap,
        equity_floor_share=equity_floor,
        min_groups=min_groups,
        outreach_reserve_share=outreach_reserve,
    )
    result = allocate(cands, k)

    t = Table(show_header=True, header_style="bold")
    for col in ("Lane", "Count", "Cost"):
        t.add_column(col)
    t.add_row("Fund", str(len(result.funded)), f"{result.funded_cost:,}")
    t.add_row("Verify first", str(len(result.verify)), f"{result.verify_cost:,}")
    t.add_row("Outreach", str(len(result.outreach)), f"{result.outreach_cost:,}")
    t.add_row("Dropped", str(len(result.dropped)), "—")
    console.print(t)
    console.print(f"Beneficiaries: [bold]{result.beneficiaries:,}[/bold]")
    cpb = result.cost_per_beneficiary
    console.print(f"Cost per beneficiary: [bold]{cpb}[/bold]" if cpb else "Cost per beneficiary: n/a")
    for c in result.constraints:
        mark = "[green]ok[/green]" if c.satisfied else "[red]BINDING[/red]"
        console.print(f"  {mark} {c.name}: {c.detail}")
    for m in result.infeasible:
        console.print(f"  [yellow]infeasible[/yellow] {m}")

    if write:
        payload = {
            "meta": {
                "budget": budget,
                "weights": DEFAULT_WEIGHTS,
                "buildable_share": BUILDABLE_SHARE,
                "provenance": {
                    "unit_costs": "REAL — published central scheme norms, adapters/in/schemes.yaml",
                    "scheme_eligibility": "A scheme is proposed only where its published settlement scope overlaps what the sector indicator measures. The roads indicator counts villages only, so no urban roads scheme is proposed anywhere in this build.",
                    "beneficiaries_per_unit": "Published norms (IPHS catchment, RTE class size, Census household size), capped at the deprived population",
                    "deficit": data["meta"]["provenance"]["deficit_indicators"],
                    "population": data["meta"]["provenance"]["population"],
                    "distinct_submitters": "LOWER BOUND — post-dedup cluster count, not a counted headcount",
                    "reused_images": "NOT MEASURED in the synthetic corpus — reported as zero, never estimated",
                    "burst_share": "NOT MEASURED — the aggregated fixture carries no per-report timestamps",
                },
            },
            "summary": result.summary(),
            "constraints": [
                {"name": c.name, "satisfied": c.satisfied, "detail": c.detail} for c in result.constraints
            ],
            "funded": [
                {
                    "id": a.candidate.candidate_id,
                    "code": a.candidate.unit_code,
                    "state": a.candidate.group_key,
                    "sector": a.candidate.sector,
                    "scheme": a.candidate.scheme_key,
                    "units": a.candidate.units,
                    "cost": a.cost,
                    "priority": a.candidate.priority,
                    "confidence": a.candidate.confidence,
                    "beneficiaries": a.candidate.beneficiaries,
                    "deprived": a.candidate.deprived,
                }
                for a in result.funded
            ],
            "outreach": [
                {
                    "id": a.candidate.candidate_id,
                    "code": a.candidate.unit_code,
                    "state": a.candidate.group_key,
                    "sector": a.candidate.sector,
                    "cost": a.cost,
                    "priority": a.candidate.priority,
                    "rationale": a.rationale,
                }
                for a in result.outreach
            ],
            "verify": [
                {
                    "id": a.candidate.candidate_id,
                    "code": a.candidate.unit_code,
                    "sector": a.candidate.sector,
                    "cost": a.cost,
                    "confidence": a.candidate.confidence,
                    "rationale": a.rationale,
                }
                for a in result.verify
            ],
        }
        path = DATA / "allocation.json"
        path.write_text(json.dumps(payload, separators=(",", ":")))
        console.print(f"Wrote {path.name}: {path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    typer.run(main)
