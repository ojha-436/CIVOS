# CIVOS — Product Specification

**The civic operating system — citizen-signal-driven infrastructure prioritisation for BRICS governments**

| | |
|---|---|
| **Platform** | CIVOS · instances named `CIVOS-IN`, `CIVOS-ZA`, … mirroring `adapters/<iso>/` |
| **Hackathon** | Build with AI: Code for Communities — Second Edition (Google Cloud × Hack2skill) |
| **Problem statement** | PS-01 — AI for Digital Public Infrastructure & Governance (BRICS theme: Innovation) |
| **Team** | 1 (solo) |
| **Build window** | 14 Aug 2026 → 22 Aug 2026 (target submit) · hard deadline 24 Aug 2026 |
| **Effective capacity** | ~44 hours (8 days × 5.5 h) — of which ~34 h code, ~10 h submission assets |
| **Spec version** | 1.1 — adds image modality, renames platform to CIVOS |

---

## 1. Problem Statement

Governments across BRICS nations receive enormous volumes of citizen development requests — through grievance portals, ward meetings, elected-representative letters, helplines and social media — but these live in mutually unintelligible systems. As a result, three things are true at once: public spending is misaligned with actual need, entire districts with severe infrastructure deficits are never heard from at all, and there is no mechanism to prove whether a funded project changed anything.

The failure is not a shortage of citizen feedback. It is that **feedback never becomes a fundable, auditable, prioritised project proposal.** A district officer cannot move a budget line on the strength of a heatmap. They need an evidence trail that survives an audit, a legislature question and a journalist.

And there is a second, less visible failure. Every voice-based or app-based feedback channel over-samples the loud, connected, urban, literate, smartphone-owning citizen. Rank districts by request volume and you systematically defund the poorest and least-connected — the exact inversion of the mission. **Silence is read as satisfaction when it is usually the absence of access.**

---

## 2. Goals

| # | Goal | How we know it succeeded |
|---|---|---|
| G1 | Any citizen can register a development request **by speaking, typing, or photographing** — in their own language, with no app install and no literacy requirement | End-to-end input → structured, geo-located, sector-classified need object in < 15 s, verified across ≥ 10 languages and all three modalities |
| G2 | Collapse raw request volume into **distinct needs**, so policymakers see the number that matters | Dedup ratio reported per district; raw signals resolve to a defensible count of distinct needs |
| G3 | Rank districts by need in a way that is **corrected for participation bias**, and explicitly surface high-deficit / zero-voice districts | "Silent Need" quadrant is populated and every district in it is traceable to real official deficit data |
| G4 | Every recommendation is emitted as a **budget-ready dossier** — evidence-cited, photographically corroborated where available, costed, and matched to a real named funding scheme | 100% of dossier claims link to a citizen signal cluster, an image, or a named official dataset row |
| G5 | A second country can be onboarded by **adding a config directory**, not by writing code | Second-country adapter loads and renders with zero changes to core modules |

---

## 3. Non-Goals

| Non-goal | Why |
|---|---|
| **User accounts, authentication, RBAC** | Scores zero on the rubric. Role is a URL parameter in v1. Real deployments would use the host nation's existing identity layer, which is a ministry decision, not ours. |
| **WhatsApp Business API integration** | Requires Meta business verification — days of latency, unavailable to an individual. Telegram provides identical proof of the "messaging app" requirement in 5 minutes. Ships as a documented `WhatsAppAdapter` stub behind the same interface. |
| **Video input** | 10× the payload for marginal additional signal over a photo. Interface is designed to accept it later (P2-5). |
| **Custom model training (Vertex AutoML)** | Days of work for a marginal accuracy gain. `BigQuery ML ARIMA_PLUS` satisfies the predictive-modelling requirement in ~10 lines of SQL. |
| **Real-time streaming / websockets** | Nothing in the rubric rewards it. Batch + polling is indistinguishable in a demo. |
| **Live impact measurement** | The verification loop requires months of real elapsed time. v1 ships a **precomputed, clearly-labelled** before/after for one district — using the image-pair mechanism, so the method is real even though the timeline is compressed. |
| **PDF/DOCX export of dossiers** | Browser print is free. On-screen dossier is sufficient for evaluation. |
| **Storing original photos long-term** | Privacy liability with no product benefit. Originals are deleted after extraction; a thumbnail and the extracted attributes persist. |
| **Claiming real citizen data** | We have no government access. The citizen layer is synthetic, generated from real geography and real deficits, and **labelled as synthetic in the UI itself**. The official layer is 100% real. Evidence photos are real, openly-licensed images. |

---

## 4. Users & Jobs to be Done

### Persona 1 — Asha, citizen (primary volume)
Speaks Marathi. Owns a feature phone. Has never used a grievance portal. The borewell in her hamlet has been dry for five months.

> **When** something in my village is broken and I have no idea who to tell, **I want to** just say what's wrong in my own language — or show it — and be told it was heard, **so that** I don't have to travel to a taluka office or fill a form in a language I can't read.

### Persona 2 — Imran, informal civic volunteer (evidence contributor)
Walks the ward. Photographs broken things. Cannot describe them in the sector vocabulary a government form expects.

> **When** I see a collapsed culvert or a dark stretch of street, **I want to** take one photo and send it, **so that** I don't have to know which department owns it or what it's officially called.

### Persona 3 — Rajesh, district collector / municipal commissioner (primary decision-maker)
Has a discretionary and scheme-tied budget. Receives thousands of complaints a year and hundreds of political requests. Is audited.

> **When** I have to decide which of forty possible projects to fund this quarter, **I want** a ranked list where each entry comes with the evidence, the cost band and the scheme it draws from, **so that** I can defend the decision to an auditor, my minister and the press.

### Persona 4 — Dr. Nandini, ministry / NITI-level policy analyst (cross-district)
Allocates across 700 districts. Needs to detect systemic gaps, not individual complaints.

> **When** I'm allocating a national scheme's budget across districts, **I want** to know which districts have high measured deficit but zero citizen demand signal, **so that** I fund need rather than funding whoever shouted loudest.

### Persona 5 — Foreign ministry evaluator (cross-border / DPG adopter)
Wants to know if this runs on their country's data.

> **When** I evaluate a digital public good built in another country, **I want** to see it running on my nation's administrative units and languages, **so that** I know adoption is a configuration exercise and not a rebuild.

---

## 5. System Overview

Three loops. The third is the one nobody else will build.

```
┌─ LOOP 1 · LISTEN ────────────────────────────────────────────────────────┐
│                                                                          │
│  Web widget          ┐   VOICE  ─┐                                       │
│   · mic              │   TEXT   ─┼─► ONE Gemini multimodal call           │
│   · camera / upload  ├── IMAGE  ─┘   · language auto-detect               │
│   · text box         │                · sector classification             │
│  Telegram bot        │                · severity 1–5                      │
│   · voice / text /   │                · visual asset identification       │
│     photo            │                · geo hint extraction               │
│  Bulk CSV importer   ┘                                                    │
│   (legacy grievance                   EXIF GPS ──► ST_CONTAINS ──┐        │
│    system adapter)                    (high-confidence geo path) │        │
│                                                                  ▼        │
│                                                        NormalisedSignal   │
│                                              { …, has_image, asset_type } │
└──────────────────────────────────────────────────────────────────────────┘
                                     │
┌─ LOOP 2 · DECIDE ───────────────────▼────────────────────────────────────┐
│  BigQuery                                                                 │
│   ML.GENERATE_EMBEDDING (text + image) → distinct needs, duplicate photos │
│   VECTOR_SEARCH                → clustering + submission-fraud check      │
│   ST_*                         → admin unit reconciliation               │
│   Official deficit data        → DeficitIndex per sector                  │
│   Participation correction     → VoiceCorrection                          │
│   Image-backed share           → EvidenceStrength                         │
│   ARIMA_PLUS                   → 90-day demand forecast                   │
│   Quadrant assignment          → Act Now / Silent Need / …                │
│   Scheme catalogue match       → FundingRoute                             │
│                                                                           │
│  Gemini (grounded generation)  → Project Dossier + citations + photos     │
└──────────────────────────────────────────────────────────────────────────┘
                                     │
┌─ LOOP 3 · VERIFY ───────────────────▼────────────────────────────────────┐
│  Post-funding signal decay · sentiment shift · re-poll via same channel   │
│  **Before/after image pair** on the same asset, matched by image          │
│  embedding + admin unit → did the thing actually get fixed?               │
│  (v1: precomputed demonstration on one district, labelled)                │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Multimodal & Multilingual Specification

### 6.1 The three modalities do different jobs

This is not "three inputs because three is better than one." Each buys something the others cannot.

| Modality | What it buys | Who it serves |
|---|---|---|
| **Voice** | **Access.** No literacy requirement, no form, no vocabulary. The only channel that reaches the citizens the system is most at risk of missing. | Asha — the reason the participation correction exists at all |
| **Text** | **Scale.** Messaging apps, web forms, and — critically — bulk import of existing grievance records from legacy systems. Text is how you defragment rather than add a fragment. | Volume, and the legacy-data path |
| **Image** | **Evidence.** A voice note is a claim; a photo is corroboration. Also the highest-confidence geo path (EXIF), and the only modality that can verify a fix. | Imran, the auditor, and Loop 3 |

**One call, three modalities.** Gemini accepts audio, text and image parts in the same request. There is a single extraction function with a single output schema — not three pipelines. This is the primary architectural reason for choosing Gemini multimodal over a chain of Speech-to-Text + Translation + Vision APIs.

### 6.2 What vision extracts from a citizen photo

| Output | Notes |
|---|---|
| `sector` | Broken road, dry handpump, dark street, collapsed school wall → one of the five sectors |
| `asset_type` | handpump · borewell · culvert · transformer · street light · school building · toilet block · PHC building · road surface |
| `severity` (1–5) | Graded from visible state — a hairline crack is not a washed-out culvert |
| `visual_description` | Short factual caption, stored as the image's text representation for embedding |
| `condition_flags` | `structurally_unsafe`, `standing_water`, `unusable`, `partially_functional` |
| `people_present` | **Safety gate** — triggers the PII path in §11 |
| `relevance` | Rejects images unrelated to civic infrastructure, with a polite retry prompt |

### 6.3 Language coverage — probed, not hardcoded

The language list is **never hardcoded**. A capability-probe script queries the live Google APIs at build time and generates `config/languages.generated.yaml`. The number quoted in the pitch is therefore the number the platform actually supports on demo day, and it grows for free as Google expands coverage.

```
scripts/probe_language_capability.py
  → Cloud Speech-to-Text v2 : supported recognition locales
  → Cloud Translation v3     : supported source/target languages
  → Cloud Text-to-Speech     : available voices per locale
  → emits tiered config + a coverage report for the deck
```

| Tier | Capability | Coverage — **measured 14 Aug 2026**, see [docs/LANGUAGE-COVERAGE.md](docs/LANGUAGE-COVERAGE.md) |
|---|---|---|
| **A — Full voice round-trip** | Speak in, structured extraction, spoken confirmation back in the same language | **56 locales**, of which 9 are Indian (`bn ` `gu` `hi` `kn` `ml` `mr` `ta` `te` + `en-IN`) |
| **B — Voice in, text out** | Speech recognised, confirmation delivered as text | **3 further locales** confirmed. Lower bound — see caveat below |
| **C — Text only** | Typed or messaged input, full pipeline | **196 languages** via Translation API, including **19 of the 22 Scheduled Languages of India** |
| **D — Image-only fallback** | **No language required at all.** Photograph the problem; vision does the classification; confirmation via icon + district name | Universal — this tier has no language dependency, which makes it the true accessibility floor |

**Two corrections that measurement forced, recorded rather than quietly dropped:**

1. **Tier C is 19 of 22 Scheduled Languages, not all 22.** Translation v3 has no
   pair for **Santali**, **Kashmiri** or **Bodo**. Konkani and Manipuri *are*
   covered, under `gom` and `mni-Mtei` — checking the obvious codes `kok`/`mni`
   would have under-reported them. The claim is now verified on every probe run by
   `--check-list adapters/in/languages.yaml`, so it fails loudly rather than
   ageing badly. Those three languages still reach citizens through Tier D and
   through code-mixed speech.
2. **Tiers A and B are a probed lower bound.** Speech-to-Text publishes no
   list-locales API and rejects bare language codes, so support is established by
   attempting a real recognition per candidate locale. The candidate set is seeded
   from locales that have synthesis voices, so Speech-to-Text locales without a
   TTS voice are undercounted. A measured lower bound is worth more than a larger
   number copied from documentation, and the report says so.

Tier D is worth stating explicitly in the pitch: **the image channel is the only one that works for a citizen whose language nothing supports.**

### 6.4 Requirements
- **Language auto-detection**, not language selection. Asha does not pick "Marathi" from a dropdown; she speaks and the system figures it out.
- **Code-mixing must survive.** Real Indian speech is Hindi-English-Marathi in one sentence. Gemini handles this natively; a rigid STT-then-translate chain does not.
- **Original input is never discarded conceptually.** Every signal stores `raw_text`, `detected_language`, `english_normalised`, and for images the `visual_description` + thumbnail. Dossier quotes display original language and English side by side. Auditability requires the citizen's own words.
- **Outbound localisation** of the citizen-facing UI via Translation API; the policymaker console ships in English + one Indian language.

---

## 7. Sector Model

All five sectors, each bound to a real district-level deficit indicator, a real named funding scheme, and the visual asset types vision should recognise. The indicator↔scheme binding is what makes a dossier credible — it is chosen to serve the funding route, not chosen first.

| Sector | Deficit indicator (real, district-level) | Source | Funding route (India) | Visual asset types |
|---|---|---|---|---|
| **Water & Sanitation** | % households without improved drinking water source; % without improved sanitation | NFHS-5 district factsheets; NITI National MPI | Jal Jeevan Mission; Swachh Bharat Mission (G) | handpump, borewell, standpost, toilet block, drain |
| **Roads & Transport** | Rural habitation connectivity deficit; % habitations unconnected | PMGSY / district statistics | PMGSY; AMRUT (urban) | road surface, culvert, bridge, bus stop |
| **Electricity** | % households without electricity | NFHS-5; NITI National MPI | RDSS; DDUGJY | transformer, pole, street light, service line |
| **Health facilities** | % institutional births; ANC coverage; sub-centre shortfall | NFHS-5; Rural Health Statistics | National Health Mission; Ayushman Bharat HWC | PHC building, sub-centre, ambulance access road |
| **Education** | Net attendance ratio; % children out of school | NFHS-5; NITI National MPI | Samagra Shiksha; PM SHRI | school building, classroom, boundary wall, school toilet |

Sectors and their bindings live in the country adapter, not in code: `adapters/<iso>/sectors.yaml`, `adapters/<iso>/schemes.yaml`.

---

## 8. The Prioritisation Engine

Computed per **(district, sector)** pair. Every term is inspectable in the UI — a black box is not deployable in government.

```
Signals(d,s)          raw request count
Needs(d,s)            distinct needs after embedding dedup (cluster count)
Severity(d,s)         mean Gemini-assigned severity, 1–5
Recency               exponential decay, 90-day half-life

RawDemand(d,s)      = Σ over needs [ severity × recency ]
DemandIndex(d,s)    = percentile-normalise RawDemand across districts → 0–100
DeficitIndex(d,s)   = normalise official deprivation % → 0–100

ParticipationRate(d) = TotalSignals(d) / Population(d) × 1000
VoiceCorrection(d)   = clamp( median(ParticipationRate) / max(ParticipationRate(d), ε), 0.5, 3.0 )
AdjustedDemand(d,s)  = DemandIndex(d,s) × VoiceCorrection(d)

EvidenceStrength(d,s) = share of needs backed by ≥ 1 image, after duplicate-photo removal
SilenceGap(d,s)       = DeficitIndex(d,s) − DemandIndex(d,s)
ForecastGrowth(d,s)   = ARIMA_PLUS 90-day slope

Priority(d,s) = w₁·AdjustedDemand + w₂·DeficitIndex + w₃·max(SilenceGap,0)
              + w₄·ForecastGrowth + w₅·EvidenceStrength
```

`EvidenceStrength` answers a real objection — *"how do you know these complaints are genuine?"* — with a number rather than an assurance. It deliberately carries the **smallest** weight: photographic evidence should raise confidence in a need, never become a prerequisite for being heard. A district where nobody owns a camera must not be penalised twice.

**The weights `w₁…w₅` are exposed as sliders in the console.** This is not a nice-to-have. A ministry will not adopt a ranking it cannot interrogate or re-weight to its own policy priorities. Making the weights visible converts the engine from an oracle into an instrument.

### Quadrants

| | **Low measured deficit** | **High measured deficit** |
|---|---|---|
| **High citizen demand** | **Expectation Gap** — complaints exceed measured deficit. Either the official data is stale, or the issue is service *quality* rather than *absence*. Investigate the data, don't build. | **Act Now** — corroborated need. Fund. |
| **Low citizen demand** | **Stable** — no action. | **Silent Need** — severe deficit, no voice. **Dispatch outreach, do not auto-fund.** |

The **Expectation Gap** quadrant is a genuine policy distinction and also a data-quality alarm: it is where the platform tells the government its own datasets are out of date.

### The critical framing on Silent Need
The system does **not** auto-fund silence. It flags for **active outreach** — dispatch an enumerator, run a targeted voice campaign in that district's language. This is a bias-correction mechanism, not an override of citizen input, and the UI must say so on the card itself. Any evaluator will raise this objection; the answer must be in the product, not only in the pitch.

---

## 9. The Project Dossier

The unit of output. Not a chart — an artifact a district officer can attach to a funding note.

**Required contents:**
1. Title, district, sector, quadrant, priority score with term-by-term breakdown
2. `Needs` count, `Signals` count, number of distinct languages the signals arrived in, **number of signals with photographic evidence**
3. Three representative verbatim citizen quotes — selected as cluster centroids — shown in **original language and English**
4. **Evidence photo strip** — up to 4 de-duplicated citizen images with vision-extracted asset type and condition flags, each resolvable to its signal ID
5. Deficit evidence: indicator name, district value, national percentile, source dataset + year
6. Estimated population affected
7. 90-day forecast direction
8. **Matched funding scheme(s)** with an eligibility note
9. Indicative cost band, derived from published scheme unit costs
10. Confidence statement and caveats, including explicit synthetic-data disclosure and `EvidenceStrength`
11. **Evidence table** — every numbered claim resolves to a signal cluster ID, an image ID, or a dataset row

**Grounding requirement:** dossier text is generated by Gemini **only** from a retrieved evidence bundle. No claim may appear that is not in the bundle. This is the first question any government buyer asks and the answer must be architectural, not aspirational.

---

## 10. Requirements

### P0 — Must have (submission is not viable without these)

| ID | Requirement | Acceptance criteria |
|---|---|---|
| P0-1 | **Multimodal web intake, no install** — mic, camera/upload, and text box in one widget | Given a browser, when a citizen submits by voice, photo, or text, then a `NormalisedSignal` is persisted within 15 s with language, sector, severity and admin unit populated |
| P0-2 | Telegram bot intake — **text, voice note, and photo** | All three message types produce an identical `NormalisedSignal` shape via the same endpoint; adapter interface documented with `WhatsAppAdapter` stub present |
| P0-3 | Bulk legacy importer | Given a CSV of pre-existing grievance records, when imported, then records normalise into the same schema — proving defragmentation, not fragment #5 |
| P0-4 | **Single Gemini multimodal extraction call** | One call accepts any combination of audio, text and image parts and returns validated JSON `{language, translation, sector, severity, asset_type, condition_flags, visual_description, people_present, relevance, geo_hint}` |
| P0-5 | Geo-grounding to admin unit | Vague human descriptions resolve to a district with ≥ 85% accuracy on a 50-case hand-built test set. **Fallback:** mandatory district picker if the gate fails |
| P0-6 | **EXIF high-confidence geo path** | When a submitted photo carries GPS EXIF, coordinates resolve via `ST_CONTAINS` and the signal is flagged `geo_confidence = high`, bypassing inference entirely |
| P0-7 | Embedding dedup → distinct needs | `ML.GENERATE_EMBEDDING` + `VECTOR_SEARCH` clusters signals; console reports Signals *and* Needs separately |
| P0-8 | **Image PII safety gate** | Given a photo where `people_present = true`, when processed, then the original is discarded and only extracted attributes + a face-free thumbnail (or no thumbnail) persist. Original photos are deleted after extraction in all cases |
| P0-9 | Real official deficit layer | All five sectors carry real district-level indicators loaded in BigQuery with source and year attribution visible in the UI |
| P0-10 | Prioritisation engine + quadrants | All formula terms in §8 computed including `EvidenceStrength`; quadrant assigned; weight sliders functional and recompute live |
| P0-11 | Policymaker console | Choropleth map of India by district, quadrant filter, sector filter, district drilldown, ranked list |
| P0-12 | Grounded dossier generation | One click produces a dossier meeting all 11 requirements in §9, including the evidence photo strip, with a resolvable evidence table |
| P0-13 | Funding route match | Every dossier names at least one real scheme; catalogue is YAML in the country adapter |
| P0-14 | Country adapter abstraction | Country is a config directory. Core modules contain zero country-specific literals. Verified by a lint check that greps `core/` for hardcoded `IN`/`India`/district names |
| P0-15 | Deployed public link | Console and API live on Cloud Run, reachable without credentials, with seeded data |
| P0-16 | Synthetic-data labelling | A persistent, visible banner distinguishes the synthetic citizen layer from the real official layer on every screen |

### P1 — Should have

| ID | Requirement |
|---|---|
| P1-1 | `ARIMA_PLUS` 90-day demand forecast per district-sector, surfaced as trend arrows |
| P1-2 | Second country adapter loaded with real data (one province, one indicator minimum) + live country switcher |
| P1-3 | Capability-probe script generating the language config, with a coverage report for the deck |
| P1-4 | **Image-embedding duplicate-submission check** — near-identical photos resubmitted to inflate a district's count are collapsed. Integrity feature, reuses existing embedding machinery |
| P1-5 | Loop 3 precomputed before/after view for one district, **using a real before/after image pair** matched by embedding + admin unit |
| P1-6 | Spoken confirmation back to the citizen via Text-to-Speech in their own language |
| P1-7 | DPGA 9-indicator self-assessment published in the repo |

### P2 — Design for, do not build

| ID | Consideration | Architectural implication |
|---|---|---|
| P2-1 | WhatsApp / IVR / SMS channels | Channel adapter interface must be stable and documented now |
| P2-2 | Federated cross-border model sharing | Keep the scoring engine's inputs an explicit contract so another nation can share weights without sharing citizen data |
| P2-3 | Swap Gemini for an open model | LLM calls sit behind a single `LanguageModel` interface — required for DPGA platform independence |
| P2-4 | Real longitudinal impact measurement | Signal schema carries `project_id` and `funded_at` from day one so the decay query works later with no migration |
| P2-5 | **Video input** | The extraction call takes a `parts[]` list; adding a video part must not change the output schema |
| P2-6 | **Asset-level tracking** (same handpump over time) | Store `asset_type` + image embedding + admin unit now so assets can be reconciled into entities later |

---

## 11. Privacy, Safety & DPG Compliance

Mapped to the **Digital Public Goods Alliance 9 indicators** — because "designed as a Digital Public Good" is a specification, not a sentiment, and most submissions will treat it as a licence choice.

| DPGA indicator | Our implementation |
|---|---|
| 1. Relevance to SDGs | SDG 6 (water/sanitation), 7 (energy), 9 (infrastructure), 11 (cities), 16 (institutions) |
| 2. Approved open licence | Apache-2.0 for code; CC-BY-4.0 for documentation, schema and reference dataset |
| 3. Clear ownership | Named in repo `OWNERSHIP.md` |
| 4. Platform independence | `LanguageModel`, `Warehouse` and `ChannelAdapter` interfaces documented with non-Google reference paths. Google AI is the reference implementation, not a dependency of the design |
| 5. Documentation | README, adapter authoring guide, OpenAPI 3.1 spec, schema docs |
| 6. Non-PII data extraction | Public API returns aggregates only; k-anonymity suppression below 5 signals per district-sector |
| 7. Privacy & applicable law | DPDP Act 2023 (IN), LGPD (BR), POPIA (ZA) |
| 8. Standards & best practice | GeoJSON, ISO 3166-2 admin codes, OpenAPI 3.1, DCAT for dataset metadata, EXIF handled per spec |
| 9. Do no harm by design | The participation correction **is** the do-no-harm mechanism. `EvidenceStrength` deliberately carries the lowest weight so camera ownership never becomes a precondition for being heard. Silent Need triggers outreach, never automatic allocation |

### Modality-specific data handling

| Input | Retention policy |
|---|---|
| **Audio** | Transcribed, then **deleted immediately**. Only `raw_text` + `detected_language` persist |
| **Image** | Vision-extracted, then **original deleted**. A downscaled thumbnail persists *only if* `people_present = false`. If people are detected, no image persists at all — attributes only |
| **Text** | Persisted as submitted, plus English normalisation. No names extracted or stored |
| **Identifiers** | Phone/Telegram IDs salted-hashed. No name, no exact citizen location — **admin unit only**, never the EXIF coordinate itself |

The EXIF point matters and is easy to get wrong: **we use GPS coordinates to resolve the district, then discard them.** Storing precise coordinates of a citizen's submission is a surveillance risk with no product benefit, and it would fail DPGA indicator 7 in any serious review.

---

## 12. Success Metrics

Framed against the actual evaluation rubric, since that is the scoreboard.

| Rubric criterion | Weight | What must be true on screen |
|---|---|---|
| **AI/Technical Execution** | 25% | **All three Google AI categories the rules name** — GenAI (grounded dossier generation), predictive modelling (`ARIMA_PLUS`), and computer vision (citizen photo analysis). Plus work a keyword list cannot do: code-mixed audio → structured JSON, geo-grounding from vague description, embedding dedup. End-to-end functional from live mic and live camera to dossier |
| **Problem–Solution Fit** | 20% | Every clause of PS-01 visibly addressed — *"voice, text, and messaging apps"* now literally satisfied, plus "measure the impact", which most submissions will silently drop |
| **Cross-Border Applicability** | 20% | Live country switch on real second-country data. `CIVOS-IN` / `CIVOS-ZA` naming mirrors `adapters/`. Lint check proving no country literals in core |
| **Deployability & Scalability** | 20% | Named scheme funding routes; inspectable weights; k-anonymity; image retention policy; real deployed link; adapter authoring guide |
| **Impact Potential** | 10% | Population-affected estimates per dossier; language coverage count from live probe; Tier-D image-only accessibility floor; Silent Need district count |
| **Presentation & Clarity** | 5% | The 1:40 silence turn lands in under 20 seconds of narration |

### Internal build metrics
- **Geo-grounding accuracy** ≥ 85% on the 50-case test set *(gate — decided Day 3)*
- **Vision sector accuracy** ≥ 80% on a 30-image hand-labelled set *(gate — decided Day 4)*
- **Dedup ratio** reported and sane (raw signals → distinct needs, expect 3–8×)
- **Intake latency** < 15 s p95 for all three modalities
- **Evidence coverage** — % of needs with ≥ 1 photo, reported honestly
- **Language coverage** — the live-probed number, whatever it is
- **Zero** country-specific literals in `core/` per lint check

---

## 13. Open Questions

**Blocking (resolve before the phase that depends on it):**
- ~~**[Day 1, engineering]** Are `AI.GENERATE` / `ML.GENERATE_EMBEDDING` / `VECTOR_SEARCH` / `ARIMA_PLUS` available in the chosen BigQuery region?~~ **RESOLVED 14 Aug — `PROCEED_BQML`.** All four are available in `asia-south1`, probed empirically ([docs/GATE0-RESULT.md](docs/GATE0-RESULT.md)). Three findings that change how the SQL gets written:
  - **Embeddings require the `CREATE MODEL … REMOTE WITH CONNECTION` form.** The newer inline `AI.GENERATE_EMBEDDING(TABLE …, connection_id => …)` surface is *not* available here — it rejects `connection_id` as an unknown argument. `ML.GENERATE_EMBEDDING` against a remote model works, so this spec's original assumption was right.
  - **`AI.GENERATE` works inline** with `connection_id` + a plain `endpoint`. No fully-qualified global endpoint is needed in `asia-south1`, contrary to the documentation note that prompted the check.
  - **Model:** `gemini-2.5-flash` for generation, `gemini-embedding-001` for embeddings at **3072 dimensions**. `gemini-3-flash` does not exist. `CREATE VECTOR INDEX` requires ≥ 5,000 rows, which our ~3,000-signal corpus is below — brute-force `VECTOR_SEARCH` is confirmed working and is the correct choice at this scale.
- **[Day 3, engineering]** Does geo-grounding clear 85%? *If not, mandatory district picker — decide and move the same day.*
- **[Day 1, data]** Are NITI National MPI district tables and NFHS-5 district factsheets machine-readable, or do they need PDF extraction? *Single biggest schedule risk in the data phase.*
- **[Day 3, data]** **Source of real evidence photos.** Openly-licensed Indian infrastructure images (Wikimedia Commons and equivalent) — need ~150 curated and attributed across five sectors. Synthetic images are not an acceptable substitute here; vision accuracy must be demonstrated on real photographs.

**Non-blocking:**
- **[Day 8]** Second country — South Africa (English, cleaner data) or Brazil (better optics, Portuguese demo)? Decide only when the three hours actually exist.
- **[User]** Which language will the live on-camera intake demo be in? A second Indian language in a different script is a stronger multimodal proof than Hindi + English alone.
- **[Day 4]** Does `EvidenceStrength` distort rankings toward urban districts in practice? If measured distortion is material, drop `w₅` to zero and keep the metric as reporting-only.

---

## 14. Timeline

| Date | Phase | Gate |
|---|---|---|
| 14 Aug | Phase 0 — Foundations | BigQuery ML feature availability confirmed |
| 15 Aug | Phase 1 — Real data layer | All 5 sectors have real district indicators loaded |
| 16 Aug | Phase 2 — Signal corpus + evidence images | **Geo-grounding gate: ≥ 85% or fall back** |
| 17 Aug | Phase 3 — Multimodal intake | Live mic **and live camera** → persisted signal |
| 18 Aug | Phase 4 — Intelligence | **Vision gate: ≥ 80%.** Quadrants populated; Silent Need list non-empty |
| 19–20 Aug | Phase 5 — Console | Deployed link live |
| 21 Aug | Phase 6 — Portability + DPG | Country switch works *or* adapter guide ships |
| 22 Aug | Phase 7 — Submission | **All 5 artefacts submitted** |
| 23–24 Aug | Buffer | Do not use. Platforms fail on deadline day. |

Detailed phase breakdown with hour budgets: [plan.md](plan.md)

---

## 15. Scope Discipline

The rule for the next eight days: **anything that does not appear in the 4-minute demo video does not get built.** The video storyboard is locked in [plan.md](plan.md) and it is the build spec. Any new idea must displace something already in it or wait for v2.

**Parking lot** — good ideas, explicitly not now: video input · live camera stream · asset-level longitudinal tracking · IVR/SMS channels · citizen-facing status tracking · elected-representative view · budget-envelope optimiser across districts · multi-year capital planning · coordinated-spike anomaly detection · federated learning across nations · OCR of handwritten paper petitions.
