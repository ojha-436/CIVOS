# CIVOS — submission copy

Ready to paste. Every number here is checked against the repo; see the
"accuracy notes" at the bottom for the two claims I deliberately did **not** make.

---

## One line (for a title / tagline field)

> CIVOS lets any citizen report what their area needs by speaking, typing or
> photographing it — then finds the districts that need help most *and* the
> districts that never speak up at all, and writes the funding proposal.

---

## Short — ~90 words

**CIVOS (Civic Operating System)** turns citizen reports into funded
infrastructure decisions. Citizens report a local problem by voice, text or
photograph, in their own language, on the web or over Telegram. A single Gemini
multimodal call structures all three into one schema. In BigQuery, duplicates
collapse into distinct needs, real government deprivation data joins in, and a
participation correction exposes **Silent Need** — districts with severe measured
deficit and almost no citizen voice, which a complaint map would show as fine.
The output is not a dashboard but a sourced project dossier tied to a real
central funding scheme.

---

## Main — ~270 words

**The problem.** Governments have no reliable way to know which infrastructure a
district actually needs. The obvious fix — collect complaints and map them — is
quietly wrong: *a map of complaints is a map of who owns a phone and knows how to
file one.* Fund the reddest dots and you fund the districts that shout loudest,
while the poorest and least connected stay invisible and unfunded.

**What CIVOS does.** Citizens report a need by **speaking, typing or
photographing** it, in their own language, via a web page or a Telegram bot.
Voice buys access (no literacy, no form, no departmental vocabulary); text buys
scale and bulk-imports complaints already sitting in legacy systems; a photograph
buys evidence, carries EXIF GPS for exact district resolution, and needs no
language at all. One Gemini 2.5 Flash call handles all three modalities in a
single request against a single output schema.

Everything lands in BigQuery, where `ML.GENERATE_EMBEDDING` + `VECTOR_SEARCH`
collapse 800 reports about one dry borewell into **one distinct need** (and catch
resubmitted photographs), real NFHS-5 deprivation data joins in, `ARIMA_PLUS`
forecasts 90-day demand, and a **participation correction** — built from real
deprivation × real participation capacity — sorts every district-sector into four
verdicts: Act Now, Expectation Gap, Stable, and **Silent Need**.

Silent Need is the point. CIVOS does **not** auto-fund it — that would replace one
guess with another. It dispatches outreach: *go and ask these people.* It fixes a
measurement problem rather than overruling citizens.

**The output is a document, not a chart**, because nobody can attach a heatmap to
a funding request. Each dossier carries the distinct needs behind it, citizens'
own words with translations, the government statistic confirming it, the
population affected, an indicative cost, and **the central scheme it can be
funded under**. Every claim resolves to a signal cluster, an image ID or a
dataset row — the model writes only from a retrieved evidence bundle.

**Portability.** The country is a configuration directory, not code.
`adapters/in/` holds India's sectors, schemes and languages; `core/` contains zero
country literals, checked by `scripts/lint_country_literals.py`. Adding
`adapters/za/` runs the same engine on South African data.

---

## Tech stack

**AI / ML**
- **Gemini 2.5 Flash** (`google-genai`) — one multimodal call for audio + text +
  image, structured output, language auto-detect, visual asset & condition
- **BigQuery ML** — `ML.GENERATE_EMBEDDING` and `VECTOR_SEARCH` (deduplication
  into distinct needs, duplicate-photo detection), `ARIMA_PLUS` (90-day forecast),
  `AI.GENERATE` (grounded dossier prose from a retrieved bundle)
- **Google Cloud Translation v3 / Speech-to-Text / Text-to-Speech** — used to
  *measure* language coverage rather than assert it

**Data & backend**
- **BigQuery** (`asia-south1`) — warehouse, scoring views, geospatial
  `ST_CONTAINS` for EXIF-GPS district resolution
- **Python 3.12**, **FastAPI**, **Uvicorn**, **Pydantic v2**, **Typer**, **uv**
- **Telegram Bot API** (`python-telegram-bot`) — second intake channel

**Frontend**
- **Next.js 16**, **React 19**, **TypeScript**, **MapLibre GL JS 5** — 641-district
  quadrant choropleth, live weight sliders (w1–w5), drilldown dossier
- **Firebase Auth** (email/password + Google SSO) and **Firestore** with rules

**Infrastructure**
- **Cloud Run** (`civos-api`, `civos-console`, `asia-south1`), **Docker**
- **GitHub Actions** — build and deploy on push to `main`
- **Playwright** + **pytest** — UI smoke tests and API tests

**Open data (all attributed, licences in `OWNERSHIP.md`)**
- NFHS-5 2019–21 (IIPS / MoHFW) — deficit indicators, 639 of 641 districts
- DataMeet Census-2011 district boundaries (CC-BY 4.0) — 641 districts
- Census 2011 Village Directory — pucca-road access, 617 districts
- Census 2011 population via Wikidata (CC0) — 526 of 641 districts
- Ten named central schemes with published unit costs

---

## Numbers that are safe to quote

- **641** districts · **5** sectors · **10** central funding schemes
- **196** languages for typed input; **56** locales for a full voice round-trip;
  **19 of 22** Scheduled Languages of India covered by Translation — all three
  measured by a re-runnable probe, not claimed
- Image channel needs **no language at all**
- NFHS-5 deficit values cross-validated against a second independent extraction:
  **100% identical**

---

## Accuracy notes — read before editing this copy

Two things are stated carefully on purpose:

1. **The country lint is genuinely enforced, so "enforced" is safe to say.**
   `scripts/lint_country_literals.py` runs as the `Country lint (SPEC P0-14)` job
   in `.github/workflows/deploy.yml`, and the deploy job declares `needs: lint`,
   so a country literal in `core/` blocks the release. The job also runs the
   linter against a deliberate violation first and fails if that *passes* — a
   detail worth mentioning if anyone asks how you know the check works. This
   closes the last item of `plan.md` §6.1.

2. **Citizen signals are synthetic and this should be said out loud, not hidden.**
   Boundaries, deficit indicators, population, schemes and evidence photographs
   are real and attributed. Citizen voice/text signals are generated — there is no
   government complaint-data access — from real geography and real deficits with a
   *deliberate participation bias*, because that bias is exactly what the product
   detects. The console labels this in its own masthead and the launch film repeats
   it on screen. Volunteering it reads as rigour; being caught reads as the
   opposite.
