"""Geo-grounding — resolve a vague citizen description to an administrative unit.

GATE 1. plan.md is blunt about why this matters: everything downstream inherits
this error. Mushy geo-grounding makes DemandIndex noise, which makes the quadrants
noise, which collapses the silence turn. So it is measured before it is trusted.

Design, and the reasoning behind each part:

**One call, with the gazetteer in the prompt.** The model is handed the
authoritative list of districts and asked to return a code from it. This turns an
open-ended extraction problem into a constrained choice, and it means a returned
code is valid by construction — the alternative (free-text district name, then
fuzzy-match) reintroduces exactly the name-matching coin toss that put Sikkim's
"East" in Delhi during Phase 1.

**Ambiguity is resolved in code, not in the prompt.** The model cannot know which
names are ambiguous *in this gazetteer*, so it returns a name and a state; if the
name maps to more than one district and no state disambiguates it, the resolver
abstains. That rule is deterministic and testable, which a prompt instruction is
not.

**Abstaining is a first-class outcome.** A resolver that invents a district for
"in our village" is worse than one that declines, because the invented district
gets a real deprivation score attached to it and nothing downstream ever
questions it. `geo_confidence` records which path produced the answer, so the
honest number can be reported separately from the inferred one (SPEC P0-6).

Usage:
    uv run python scripts/geo_ground.py --eval      # run GATE 1
    uv run python scripts/geo_ground.py --text "borewell band hai, Silchar mein"
"""

from __future__ import annotations

import csv
import json
import os
import re
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml
from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table

REPO = Path(__file__).resolve().parent.parent
console = Console()

PROJECT = os.environ.get("CIVOS_PROJECT", "civos-in")
LOCATION = os.environ.get("CIVOS_VERTEX_LOCATION", "asia-south1")
MODEL = os.environ.get("CIVOS_GEMINI_MODEL", "gemini-2.5-flash")


def norm(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


# ---------------------------------------------------------------------------
# gazetteer
# ---------------------------------------------------------------------------


class Gazetteer:
    def __init__(self, path: Path) -> None:
        self.rows = list(csv.DictReader(path.open(encoding="utf-8")))
        self.by_code = {r["admin_unit_code"]: r for r in self.rows}
        self.by_name: dict[str, list[dict]] = defaultdict(list)
        self.by_state_name: dict[tuple[str, str], dict] = {}
        for r in self.rows:
            self.by_name[norm(r["name"])].append(r)
            self.by_state_name[(norm(r["state"]), norm(r["name"]))] = r

    def catalogue(self) -> str:
        """The district list, grouped by state, as handed to the model."""
        by_state: dict[str, list[str]] = defaultdict(list)
        for r in self.rows:
            by_state[r["state"]].append(r["name"])
        return "\n".join(
            f"{state}: {', '.join(sorted(names))}" for state, names in sorted(by_state.items())
        )

    def resolve(self, district: str | None, state: str | None) -> tuple[str | None, str]:
        """Map a (district, state) pair onto a code. Returns (code, reason)."""
        if not district:
            return None, "no district proposed"
        d = norm(district)

        if state:
            hit = self.by_state_name.get((norm(state), d))
            if hit:
                return hit["admin_unit_code"], "state+district"

        candidates = self.by_name.get(d, [])
        if len(candidates) == 1:
            return candidates[0]["admin_unit_code"], "district unique nationally"
        if len(candidates) > 1:
            # The Phase 1 lesson, enforced: an ambiguous name with no usable state
            # is a coin toss, and a coin toss here silently poisons a score.
            return None, f"ambiguous — {district} exists in {len(candidates)} states"
        return None, f"{district} not in gazetteer"


# ---------------------------------------------------------------------------
# model call
# ---------------------------------------------------------------------------


class GeoProposal(BaseModel):
    """What the model is allowed to say."""

    place_mentions: list[str] = Field(
        default_factory=list, description="Verbatim place names or landmarks found in the text"
    )
    district: str | None = Field(
        default=None, description="District name exactly as spelled in the supplied catalogue"
    )
    state: str | None = Field(default=None, description="State name from the catalogue")
    spans_multiple_districts: bool = Field(
        default=False, description="True if the named place straddles more than one district"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = Field(default="", description="One short sentence")


PROMPT = """You are the geo-grounding component of a civic infrastructure platform.

A citizen has described a problem in their own words, in any Indian language, often
code-mixed, often without naming a district. Your job is to work out which district
of India they are in — or to say that you cannot.

Rules, in order of importance:

1. If the text names a town, block, tehsil, taluka, landmark, lake, forest, river
   barrage or well-known place, use your knowledge of Indian geography to identify
   the DISTRICT that contains it. For example a complaint mentioning Silchar is in
   Cachar district; one mentioning Jagdalpur is in Bastar district.
2. If the named place straddles more than one district, set
   spans_multiple_districts = true and leave district null. Do not pick one.
   Kaziranga spans Golaghat and Nagaon; Chilika spans Puri, Khordha and Ganjam.
3. If the text gives no usable location at all — "our village", "near the temple",
   "the district headquarters", "the north of the state" — leave district null.
4. A district name alone, with no state, is acceptable: return it and leave state
   null if the state is genuinely not stated. Do not invent a state.
5. Spell the district EXACTLY as it appears in the catalogue below. The catalogue
   sometimes uses older or unusual spellings — Dhuburi for Dhubri, Puruliya for
   Purulia, Chamrajnagar for Chamarajanagara, Kachchh for Kutch, Baleshwar for
   Balasore. Map what the citizen wrote onto the catalogue spelling.
6. Never guess to be helpful. An abstention is a correct answer; a wrong district
   silently corrupts a national funding decision.

Districts of India, grouped by state, as this platform knows them:

{catalogue}

Citizen text:
\"\"\"{text}\"\"\"
"""


class Resolver:
    def __init__(self, gaz: Gazetteer) -> None:
        from google import genai

        self.gaz = gaz
        self.client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
        self.catalogue = gaz.catalogue()

    def resolve(self, text: str) -> dict:
        from google.genai import types

        try:
            resp = self.client.models.generate_content(
                model=MODEL,
                contents=PROMPT.format(catalogue=self.catalogue, text=text),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=GeoProposal,
                    temperature=0.0,
                ),
            )
            proposal = GeoProposal.model_validate_json(resp.text or "{}")
        except Exception as exc:  # noqa: BLE001
            return {"code": None, "confidence": 0.0, "reason": f"model error: {exc}"[:180],
                    "geo_confidence": "unknown", "proposal": None}

        if proposal.spans_multiple_districts:
            return {"code": None, "confidence": proposal.confidence,
                    "reason": "spans multiple districts", "geo_confidence": "unknown",
                    "proposal": proposal.model_dump()}

        code, reason = self.gaz.resolve(proposal.district, proposal.state)
        return {
            "code": code,
            "confidence": proposal.confidence,
            "reason": reason,
            "geo_confidence": "inferred" if code else "unknown",
            "proposal": proposal.model_dump(),
        }


# ---------------------------------------------------------------------------
# GATE 1
# ---------------------------------------------------------------------------


def run_eval(resolver: Resolver, cases: list[dict], workers: int) -> list[dict]:
    def one(c: dict) -> dict:
        r = resolver.resolve(c["text"])
        got, want = r["code"], c["expected"]
        return {**c, "got": got, "correct": got == want, "reason": r["reason"],
                "confidence": r["confidence"], "proposal": r["proposal"]}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, cases))


def write_report(results: list[dict], threshold: float, gaz: Gazetteer) -> tuple[float, str]:
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    acc = correct / total

    by_tier: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_tier[r["tier"]].append(r)

    resolvable = [r for r in results if r["expected"] is not None]
    abstain = [r for r in results if r["expected"] is None]
    res_acc = sum(1 for r in resolvable if r["correct"]) / max(len(resolvable), 1)
    abs_acc = sum(1 for r in abstain if r["correct"]) / max(len(abstain), 1)
    # The dangerous failure: confidently naming the wrong district.
    wrong_confident = [r for r in results if not r["correct"] and r["got"] is not None]

    verdict = "PASS" if acc >= threshold else "FALLBACK_DISTRICT_PICKER"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    md: list[str] = []
    md.append("# GATE 1 — geo-grounding accuracy")
    md.append("")
    md.append(f"**Verdict: `{verdict}` · {correct}/{total} = {acc:.1%}** (threshold {threshold:.0%})")
    md.append("")
    md.append(f"Run {stamp} · model `{MODEL}` · temperature 0 · {LOCATION}")
    md.append("")
    if verdict == "PASS":
        md.append(
            "Proceed as designed. Geo-grounding is accurate enough that the demand signal it "
            "produces is not dominated by placement error."
        )
    else:
        md.append(
            "Below threshold. Take the pre-designed fallback: add a **mandatory district picker** "
            "to the intake UI and reframe as *assisted geo-tagging with human confirmation* — "
            "which is honestly what a real deployment would want anyway. Decide today; do not "
            "carry this into Phase 4."
        )
    md.append("")
    md.append("## Where the errors are")
    md.append("")
    md.append("| Slice | Cases | Correct | Accuracy |")
    md.append("|---|---|---|---|")
    md.append(f"| Resolvable (a district is the right answer) | {len(resolvable)} | "
              f"{sum(1 for r in resolvable if r['correct'])} | {res_acc:.1%} |")
    md.append(f"| Abstain (null is the right answer) | {len(abstain)} | "
              f"{sum(1 for r in abstain if r['correct'])} | {abs_acc:.1%} |")
    md.append("")
    md.append(
        f"**Confidently wrong: {len(wrong_confident)}.** This is the number that matters most — "
        "a named-but-wrong district attaches real deprivation data to the wrong place and nothing "
        "downstream questions it. A miss that abstains is recoverable; a miss that answers is not."
    )
    md.append("")
    md.append("## By difficulty tier")
    md.append("")
    md.append("| Tier | What it tests | Cases | Correct | Accuracy |")
    md.append("|---|---|---|---|---|")
    tier_desc = {
        "T1": "district named outright",
        "T2": "district named, different spelling",
        "T3": "only a town, block or tehsil named",
        "T4": "only a landmark named",
        "T5": "name exists in several states",
        "T6": "genuinely unresolvable",
    }
    for t in sorted(by_tier):
        rs = by_tier[t]
        c = sum(1 for r in rs if r["correct"])
        md.append(f"| {t} | {tier_desc.get(t,'')} | {len(rs)} | {c} | {c/len(rs):.0%} |")
    md.append("")
    md.append("## Every case")
    md.append("")
    md.append("| | id | tier | lang | expected | got | note |")
    md.append("|---|---|---|---|---|---|---|")
    for r in results:
        mark = "✅" if r["correct"] else "❌"
        md.append(
            f"| {mark} | `{r['id']}` | {r['tier']} | {r['lang']} | "
            f"`{r['expected'] or 'null'}` | `{r['got'] or 'null'}` | {r['reason']} |"
        )
    md.append("")
    disputed = [r for r in results if not r["correct"] and r.get("post_hoc_note")]
    if disputed:
        md.append("## Disputed cases")
        md.append("")
        md.append(
            "Cases where, on review, the resolver's answer looks defensible and the answer key "
            "looks wrong. **The keys are left unchanged.** Editing them after seeing the score is "
            "the tuning this test set was written first to prevent."
        )
        md.append("")
        for r in disputed:
            md.append(f"- **`{r['id']}`** — expected `{r['expected']}`, resolver said "
                      f"`{r['got'] or 'null'}`. {' '.join(str(r['post_hoc_note']).split())}")
        md.append("")

    md.append("## Method and its limitation")
    md.append("")
    md.append(
        f"The resolver is a single Gemini call with the full {len(gaz.rows)}-district gazetteer in "
        "the prompt, so a returned district is valid by construction. Ambiguity is then resolved in "
        "code, not by the model: if a district name maps to several states and none is given, the "
        "resolver abstains. That rule is deterministic and testable in a way a prompt instruction "
        "is not."
    )
    md.append("")
    md.append(
        "**This is a self-graded exam.** The test set was authored by the same party that built "
        "the resolver — though it was written and committed first, before any resolver code "
        "existed, which constrains but does not eliminate the bias. Treat this as a build gate, "
        "not an independent benchmark."
    )

    (REPO / "docs" / "GATE1-RESULT.md").write_text("\n".join(md) + "\n")
    (REPO / "docs" / "gate1-result.json").write_text(
        json.dumps(
            {"verdict": verdict, "accuracy": acc, "correct": correct, "total": total,
             "resolvable_accuracy": res_acc, "abstain_accuracy": abs_acc,
             "confidently_wrong": len(wrong_confident), "model": MODEL, "run_at": stamp,
             "results": [{k: r[k] for k in ("id", "tier", "lang", "expected", "got", "correct", "reason")}
                         for r in results]},
            indent=2,
        ) + "\n"
    )
    return acc, verdict


def main(
    evaluate: bool = typer.Option(False, "--eval", help="Run the GATE 1 test set"),
    text: str = typer.Option("", "--text", help="Resolve a single string"),
    workers: int = typer.Option(8, "--workers"),
) -> None:
    gaz = Gazetteer(REPO / "data" / "dim_admin_unit.csv")
    resolver = Resolver(gaz)

    if text:
        r = resolver.resolve(text)
        console.print_json(json.dumps(r, ensure_ascii=False))
        return

    if not evaluate:
        console.print("Nothing to do. Pass --eval or --text.")
        raise typer.Exit(1)

    ts = yaml.safe_load((REPO / "tests" / "geo_grounding_testset.yaml").read_text())
    cases, threshold = ts["cases"], float(ts["meta"]["gate_threshold"])
    console.rule(f"[bold]GATE 1[/bold] · {len(cases)} cases · {MODEL}")

    results = run_eval(resolver, cases, workers)
    acc, verdict = write_report(results, threshold, gaz)

    t = Table(title="GATE 1")
    t.add_column("tier"); t.add_column("cases", justify="right"); t.add_column("correct", justify="right")
    by_tier: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_tier[r["tier"]].append(r)
    for tier in sorted(by_tier):
        rs = by_tier[tier]
        c = sum(1 for r in rs if r["correct"])
        t.add_row(tier, str(len(rs)), f"{c} ({c/len(rs):.0%})")
    console.print(); console.print(t)

    for r in results:
        if not r["correct"]:
            colour = "red" if r["got"] else "yellow"
            console.print(f"  [{colour}]miss[/{colour}] {r['id']:8s} want={r['expected'] or 'null':24s} "
                          f"got={r['got'] or 'null':24s} {r['reason'][:60]}")

    console.rule(f"[bold]{verdict} — {acc:.1%}[/bold]")
    console.print("Written to docs/GATE1-RESULT.md")


if __name__ == "__main__":
    typer.run(main)
