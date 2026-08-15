<div align="center">

# CIVOS

**The civic operating system — citizen-signal-driven infrastructure prioritisation for BRICS governments**

Speak it, type it, or photograph it. In any language. CIVOS turns citizen requests
into a costed, evidence-cited project dossier tied to a real government funding scheme —
and finds the districts that never speak up at all.

[![Licence: Apache-2.0](https://img.shields.io/badge/code-Apache--2.0-blue.svg)](LICENSE)
[![Docs: CC-BY-4.0](https://img.shields.io/badge/docs%20%26%20data-CC--BY--4.0-lightgrey.svg)](OWNERSHIP.md)
[![Gate 0](https://img.shields.io/badge/Gate%200-PROCEED__BQML-success.svg)](docs/GATE0-RESULT.md)
[![Languages](https://img.shields.io/badge/languages-196%20measured-f3c14b.svg)](docs/LANGUAGE-COVERAGE.md)

Built for **Build with AI: Code for Communities — Second Edition** (Google Cloud × Hack2skill)
· problem statement **PS-01**, AI for Digital Public Infrastructure & Governance.

</div>

![CIVOS console, equity-adjusted view](docs/screenshots/console-adjusted.png)

---

## The problem, and the part everyone misses

Governments across BRICS nations are not short of citizen feedback. They are
drowning in it — grievance portals, ward meetings, helplines, social media, all in
mutually unintelligible systems. What they lack is a way to turn any of it into a
funding decision that survives an audit.

There is a second failure that is easier to miss, and it is the one CIVOS is built
around:

> **A map of complaints is a map of who owns a phone and knows how to complain.
> It is not a map of need.**

Every voice-based or app-based feedback channel over-samples the loud, connected,
literate, urban citizen. Rank districts by request volume and you systematically
defund the poorest and least-connected — the exact inversion of the mission.
Silence gets read as satisfaction when it is usually the absence of access.

So CIVOS measures how much each district **speaks** against how much each district
**lacks**:

|  | Official data says conditions are OK | Official data says conditions are bad |
|---|---|---|
| **Many complaints** | **Expectation Gap** — your dataset may be stale, or the service exists but is bad | **Act Now** — corroborated need. Fund it. |
| **Few complaints** | **Stable** — no action | **Silent Need** — severe deficit, no voice. **Go and listen.** |

That bottom-right cell is the product. And CIVOS never auto-funds silence — that
would replace one guess with another. It dispatches **outreach**. It is a
bias-correction mechanism, not an override of citizen input, and the interface
says so on the card itself.

---

## Try it

Requires [Node 20+](https://nodejs.org). No cloud credentials needed — the console
runs against a committed fixture.

```bash
git clone https://github.com/ojha-436/CIVOS.git
cd CIVOS/console
npm install
npm run dev          # http://localhost:3000
```

| Route | What it is |
|---|---|
| **`/`** | **Policymaker console** — 594 real districts, quadrant choropleth, live weight sliders, drilldown dossier |
| **`/report`** | **Citizen intake** — microphone, camera and text in one widget, mobile-first |

<table>
<tr>
<td width="50%"><img src="docs/screenshots/console-dossier.png" alt="District dossier"><br><em>The dossier — every claim resolves to a signal cluster, an image, or a dataset row</em></td>
<td width="50%"><img src="docs/screenshots/intake-mobile.png" alt="Citizen intake"><br><em>Citizen intake — no form, no app, no language selector</em></td>
</tr>
</table>

---

## The three loops

```
LOOP 1 · LISTEN
  web widget (mic · camera · text)  ┐
  Telegram bot (voice · text · photo)├─► ONE Gemini multimodal call ─► NormalisedSignal
  bulk CSV importer (legacy systems)┘   language auto-detect · sector · severity
                                        visual asset · condition · geo hint
                                        EXIF GPS ─► ST_CONTAINS ─► exact district

LOOP 2 · DECIDE  (BigQuery, asia-south1)
  ML.GENERATE_EMBEDDING + VECTOR_SEARCH ─► distinct needs, duplicate-photo check
  official deficit data                 ─► DeficitIndex
  participation correction              ─► VoiceCorrection, AdjustedDemand
  ARIMA_PLUS                            ─► 90-day forecast
  quadrant assignment + scheme match    ─► Act Now / Silent Need / …
  AI.GENERATE from a retrieved bundle   ─► grounded project dossier

LOOP 3 · VERIFY
  post-funding signal decay · before/after image pair on the same asset,
  matched by image embedding + admin unit — did the thing actually get fixed?
```

**One call, three modalities.** Gemini accepts audio, text and image parts in the
same request, so there is a single extraction function with a single output
schema — not three pipelines. Each modality buys something distinct:

| | What it buys |
|---|---|
| 🎙 **Voice** | **Access.** No literacy, no form, no departmental vocabulary. The only channel that reaches the citizens the system is most at risk of missing. |
| ⌨️ **Text** | **Scale.** Messaging apps, and bulk import of the millions of complaints already sitting in legacy systems. This is how you defragment instead of becoming fragment #5. |
| 📷 **Image** | **Evidence.** A voice note is a claim; a photo is corroboration. It is also the highest-confidence geo path (EXIF), the only modality that can verify a fix — and it needs no language at all. |

---

## Cross-border is a schema problem, not a translation problem

Two languages in a demo is translation. The real question is whether Brazil's
ministry can run this next month — which is only yes if the country layer is a
**configuration directory**, not code.

```
adapters/in/     languages.yaml · sectors.yaml · schemes.yaml   ← CIVOS-IN
adapters/za/     the same four files                            ← CIVOS-ZA
core/            contains ZERO country literals
```

Enforced, not asserted. `scripts/lint_country_literals.py` fails the build if a
country name, ISO code, scheme, dataset or language reaches `core/`. It parses
rather than greps — `IN` is a SQL keyword and `in` is an English preposition, so
the obvious regex matches nearly every line of Python ever written.

```bash
uv run python scripts/lint_country_literals.py
```

---

## What is real, and what is not

Stated here, in the interface, and in every dossier. A labelled substitution is
worth more than mystery data.

| Layer | Status |
|---|---|
| District boundaries, names, administrative codes | **Real** — 594 districts, public boundary data simplified for web rendering |
| Sector deficit indicators | **Real** — NFHS-5 2019-21 (IIPS / MoHFW), 537 of 594 districts, 4 of 5 sectors. Cross-validated against a second independent extraction: 100% identical. See [provenance](docs/DATA-RECONCILIATION.md) |
| Funding schemes and unit costs | **Real** — ten named central schemes with published unit costs |
| Evidence photographs | **Real** — openly licensed, individually attributed. *Never generated:* vision accuracy demonstrated on synthetic images would prove nothing |
| Citizen signals (voice and text) | **Synthetic** — no government data access. Generated from real geography and real deficits with a **deliberate participation bias**, because that bias is what the product detects |
| Roads & Transport deficit · district population | **Not loaded.** Road connectivity has no health-survey equivalent and no census population is loaded. Both are shown as gaps in the interface rather than filled with a proxy |

The generator ships as part of the public good: a reference dataset and pilot
simulator, so a ministry can trial CIVOS *before* it has data.

---

## Measured, not claimed

Two numbers in this README were produced by probing live APIs, and both are
re-runnable. Neither is hardcoded.

**Gate 0 — is the analytical spine actually available?** → [`docs/GATE0-RESULT.md`](docs/GATE0-RESULT.md)

```bash
uv run python scripts/gate0_probe.py
```

Verdict `PROCEED_BQML` in `asia-south1`. Every attempt is recorded with its exact
SQL and its exact error, including the ones that failed.

**Language coverage** → [`docs/LANGUAGE-COVERAGE.md`](docs/LANGUAGE-COVERAGE.md)

```bash
uv run python scripts/probe_language_capability.py --check-list adapters/in/languages.yaml
```

| Tier | Capability | Measured |
|---|---|---|
| **A** | Full voice round-trip — speak in, spoken confirmation back | **56 locales** |
| **B** | Voice in, text confirmation out | **3 further locales** |
| **C** | Text in, full pipeline | **196 languages** |
| **D** | **Image only — no language required at all** | universal |

Two disclosures the probe forces, rather than letting them age quietly:

- Tier C covers **19 of the 22 Scheduled Languages of India**, not all 22 — there
  is no Translation pair for Santali, Kashmiri or Bodo. Konkani and Manipuri *are*
  covered, as `gom` and `mni-Mtei`. The claim is re-verified on every run.
- Tiers A and B are a **probed lower bound**. Speech-to-Text publishes no
  list-locales API and rejects bare language codes, so support is established by
  attempting a real recognition per candidate locale. A measured lower bound is
  worth more than a larger number copied from documentation.

**Tier D is the one worth saying out loud:** a citizen whose language nothing
supports can still photograph a broken handpump and be heard.

---

## Repository layout

```
core/            country-agnostic. Interfaces, models, extraction, scoring.
  interfaces/      LanguageModel · ChannelAdapter · Warehouse
  models/          Part · RawSubmission · NormalisedSignal · ExtractionResult
adapters/in/     the CIVOS-IN country adapter
api/             FastAPI service (Cloud Run)
console/         Next.js + MapLibre policymaker console and citizen intake
scripts/         capability probes, fixture generation, the country lint
config/          generated configuration, committed so results are reviewable
docs/            gate results, language coverage, screenshots
sql/             the intelligence layer
```

`LanguageModel.extract()` takes a **`parts[]` list** — not named `audio=`, `text=`,
`image=` arguments. That single decision is what makes one multimodal call
possible instead of three pipelines, and what makes adding video later a
non-event. Every interface docstring names a non-Google reference implementation
path, because platform independence is a DPGA requirement and Google AI is the
reference implementation, not a dependency of the design.

---

## Privacy

- Audio is transcribed and **deleted immediately**.
- Photographs are analysed and the **original deleted**. A thumbnail survives only
  when no people are detected; if people are present, nothing visual is kept.
- EXIF GPS resolves the administrative unit and is then **discarded**. Storing a
  citizen's precise coordinates is a surveillance risk with no product benefit.
- Identifiers are salted-hashed. Administrative unit only — never a point location.
- k-anonymity suppression below 5 signals per district-sector, applied **inside the
  warehouse** so no caller can route around it.

Mapped against all nine [DPGA indicators](SPEC.md) — because "designed as a Digital
Public Good" is a specification, not a licence choice.

---

## Status

| Phase | State |
|---|---|
| 0 — Foundations, interfaces, Gate 0 | ✅ complete |
| 5 — Console and citizen intake | ✅ built early, against a frozen data contract |
| 1 — Real deficit data layer | ✅ complete — NFHS-5 loaded, 4/5 sectors real |
| 2–4 — Corpus, multimodal intake, intelligence | next |
| 6–7 — Second country adapter, submission | pending |

The console was built ahead of the data layer deliberately: it is the phase most
likely to overrun and the artefact evaluators actually click, so it runs against a
fixture generated to match `Warehouse.aggregate_scores()` field for field. When the
intelligence layer lands, one fetch URL changes and nothing else does.

| Gate | Result |
|---|---|
| **Gate 0** — BigQuery ML/AI availability in `asia-south1` | ✅ `PROCEED_BQML` |
| Gate 1 — geo-grounding accuracy ≥ 85% | pending |
| Gate 2 — vision sector accuracy ≥ 80% | pending |

---

## Documents

| File | What it holds |
|---|---|
| [EXPLAINER.md](EXPLAINER.md) | Plain-language version and the 30-second pitch. **Start here.** |
| [SPEC.md](SPEC.md) | Full specification — personas, loops, formulas, requirements, DPGA mapping |
| [plan.md](plan.md) | Day-by-day build plan, gates, cut list, risk register |
| [memory.md](memory.md) | Decision log — every decision and, more importantly, why |
| [docs/GATE0-RESULT.md](docs/GATE0-RESULT.md) | Measured BigQuery capability, with the exact SQL and errors |
| [docs/LANGUAGE-COVERAGE.md](docs/LANGUAGE-COVERAGE.md) | Measured language coverage, with provenance per tier |

---

## Licence

Apache-2.0 for code; CC-BY-4.0 for documentation, schema and data.
See [LICENSE](LICENSE) and [OWNERSHIP.md](OWNERSHIP.md).

© 2026 Prince Kumar Ojha
