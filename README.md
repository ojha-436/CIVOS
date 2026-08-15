# CIVOS — the civic operating system

**Citizen-signal-driven infrastructure prioritisation for BRICS governments.**

Any citizen can report what their area needs — by **speaking, typing, or
photographing** it, in their own language, with no app install and no literacy
requirement. CIVOS merges duplicate reports into distinct needs, checks them
against official deprivation data, corrects for the fact that the poorest
districts complain the least, and emits a **budget-ready project dossier** tied
to a real, named government funding scheme.

The country is a config directory (`adapters/<iso>/`), not code. India's instance
is `CIVOS-IN`; South Africa's would be `CIVOS-ZA`.

> Built for **Build with AI: Code for Communities — Second Edition**
> (Google Cloud × Hack2skill), problem statement PS-01 — AI for Digital Public
> Infrastructure & Governance.

New here? Read **[EXPLAINER.md](EXPLAINER.md)** first — five minutes, no jargon.

---

## The idea in one paragraph

A map of complaints is a map of who owns a phone and knows how to complain. It is
not a map of need. Rank districts by request volume and you systematically defund
the poorest — the exact inversion of the mission. So CIVOS treats **silence as the
most important signal in the data**: it measures how much each district *speaks*
against how much each district *lacks*, and surfaces a **Silent Need** quadrant —
severe measured deficit, no citizen voice. Those districts trigger **outreach**,
never automatic funding. It is a bias correction, not an override of citizen input.

## Status

**Phase 0 complete. Console built ahead of schedule against a frozen data
contract.** See [plan.md](plan.md) for the day-by-day build plan and
[memory.md](memory.md) for the decision log.

The console was built before the data layer on purpose: it is the phase most
likely to overrun and the thing evaluators actually click, so it now runs against
a fixture generated to match `Warehouse.aggregate_scores()` exactly. When Phase 4
lands, one fetch URL changes and nothing else does.

```bash
cd console && npm install && npm run dev     # http://localhost:3000
```

| | |
|---|---|
| `/` | Policymaker console — 594 real districts, choropleth, quadrants, weight sliders, drilldown dossier |
| `/report` | Citizen intake — microphone, camera and text, mobile-first |

![Console, equity-adjusted](docs/screenshots/console-adjusted.png)

| Gate | Result |
|---|---|
| **Gate 0** — BigQuery ML/AI availability in `asia-south1` | ✅ `PROCEED_BQML` — [evidence](docs/GATE0-RESULT.md) |
| Gate 1 — geo-grounding accuracy ≥ 85% | pending (Phase 2) |
| Gate 2 — vision sector accuracy ≥ 80% | pending (Phase 4) |

## Repository layout

```
core/          country-agnostic. Interfaces, models, extraction, scoring.
               Contains zero country literals — enforced in CI.
adapters/in/   the CIVOS-IN country adapter: languages, sectors, schemes, admin units
api/           FastAPI service (Cloud Run)
console/       Next.js + MapLibre policymaker console
scripts/       capability probes, loaders, corpus generation, the country lint
config/        generated configuration, committed so results are reviewable
docs/          gate results, language coverage, DPG compliance, image attribution
sql/           the intelligence layer
```

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) and the `gcloud` CLI.

```bash
uv sync
gcloud auth application-default login
export CIVOS_PROJECT=civos-in        # your project
export CIVOS_BQ_LOCATION=asia-south1
```

## The probes — run these first

Each writes its findings to `docs/`, and each is designed to be re-run rather than
trusted from a previous day's output.

```bash
# Gate 0 — is the analytical spine actually available in your region?
uv run python scripts/gate0_probe.py

# Language coverage — measured against live APIs, never hardcoded
uv run python scripts/probe_language_capability.py --check-list adapters/in/languages.yaml

# Cross-border claim — fails the build if a country literal reaches core/
uv run python scripts/lint_country_literals.py
```

## What is real and what is not

This distinction is stated here, in the interface, and in every dossier, because
a labelled substitution is worth more than mystery data.

| Layer | Status |
|---|---|
| Official deficit indicators, administrative boundaries, funding schemes | **Real.** Public government datasets, cited with source and year. |
| Evidence photographs | **Real.** Openly licensed, individually attributed. Never generated — vision accuracy demonstrated on synthetic images would prove nothing. |
| Citizen signals (text and voice) | **Synthetic.** We have no government data access. Generated from real geography and real deficits, with deliberately biased participation rates — the bias is what the product detects. Labelled as synthetic in the UI. |

The generator ships as part of the public good: a reference dataset and pilot
simulator so a ministry can trial CIVOS *before* it has data.

## Privacy

- Audio is transcribed and **deleted immediately**.
- Photographs are analysed and the **original deleted**. A thumbnail survives only
  when no people are detected; if people are present, nothing visual is kept.
- EXIF GPS resolves the administrative unit and is then **discarded**. Storing a
  citizen's precise coordinates is a surveillance risk with no product benefit.
- Identifiers are salted-hashed. Admin unit only — never a point location.
- k-anonymity suppression below 5 signals per district-sector, applied inside the
  warehouse so no caller can route around it.

Full mapping against all nine DPGA indicators: [SPEC.md §11](SPEC.md).

## Licence

Apache-2.0 for code; CC-BY-4.0 for documentation, schema and data.
See [LICENSE](LICENSE) and [OWNERSHIP.md](OWNERSHIP.md).

## Documents

| File | What it holds |
|---|---|
| [EXPLAINER.md](EXPLAINER.md) | Plain-language version. Start here. |
| [SPEC.md](SPEC.md) | Full specification — personas, loops, formulas, requirements, DPGA mapping |
| [plan.md](plan.md) | Day-by-day build plan, gates, cut list, risk register |
| [memory.md](memory.md) | Decision log — every decision and why |
| [docs/GATE0-RESULT.md](docs/GATE0-RESULT.md) | Measured BigQuery AI/ML capability, with the exact SQL and errors |
| [docs/LANGUAGE-COVERAGE.md](docs/LANGUAGE-COVERAGE.md) | Measured language coverage, with provenance per tier |
