# CIVOS — Decision Log

Everything decided so far and, more importantly, **why**. Written so that work can resume cold — after a gap, on a new machine, or in a new session — without re-deriving anything.

**Last updated:** 14 Aug 2026 · Status: **Phase 0 complete. Gate 0 passed (`PROCEED_BQML`). Next: Phase 1 — the real data layer.**

---

## 1. Fixed context

| | |
|---|---|
| **Event** | Build with AI: Code for Communities — Second Edition (Google Cloud × Hack2skill) |
| **Track** | PS-01 — AI for Digital Public Infrastructure & Governance (BRICS theme: Innovation) |
| **Product name** | **CIVOS** · instances `CIVOS-IN`, `CIVOS-ZA` |
| **Team** | Solo |
| **Capacity** | ~5.5 h/day |
| **Target submit** | **22 Aug 2026** (hard deadline 24 Aug — the 23rd/24th are buffer, not working days) |
| **Registration closes** | 24 Aug 2026 |
| **Shortlist announced** | 25–28 Aug · **Virtual finale 29 Aug** · **In-person Demo Day 4 Sep** |
| **Data access** | None. Open data only, no government or municipal contact |

### The five required deliverables
1. Public GitHub repo
2. Demo video, 3–5 min
3. Pitch deck, 10–12 slides
4. 2–3 line description
5. Live deployed link

### Evaluation weights — the scoreboard
| Criterion | Weight |
|---|---|
| AI / Technical Execution | **25%** |
| Problem–Solution Fit | 20% |
| Cross-Border Applicability | **20%** |
| Deployability & Scalability | **20%** |
| Impact Potential | 10% |
| Presentation & Clarity | 5% |

**Hard rule:** no Google AI integration → not considered. It's a disqualifier, not a bonus.

**The strategic read:** cross-border + deployability is 40% of the score and it's exactly what teams treat as a slide instead of a feature. That asymmetry drove most of the design decisions below.

---

## 2. Product thesis — the three things that make this different

### 2.1 Silence is the most important signal
Every voice/app feedback channel over-samples the loud, connected, urban, literate, smartphone-owning citizen. **Rank by request volume and you systematically defund the poorest districts** — the inverse of the mission. So the engine applies a participation correction and surfaces a **Silent Need** quadrant: high measured deficit, zero citizen voice.

This is the winning demo moment (video 1:45) and it's the critique a policy juror would otherwise make of *our* project.

**The objection to pre-empt, in the product not just the pitch:** *"you're recommending projects for districts with no citizen demand — isn't that ignoring citizens?"* Answer: Silent Need triggers **outreach**, never auto-funding. The button says "Dispatch outreach". We're correcting a measurement bias, not overriding citizens.

### 2.2 The output is a dossier, not a dashboard
A district officer cannot attach a heatmap to a funding request — they get audited. So the unit of output is a **budget-ready project dossier**: evidence-cited, costed, and **matched to a real named funding scheme** (Jal Jeevan Mission, PMGSY, RDSS, Ayushman Bharat HWC, Samagra Shiksha). A recommendation with no funding route is a wish; one attached to money that already exists can start next month. This is most of the 20% deployability score.

### 2.3 Cross-border is a schema problem, not a translation problem
Teams will demo two languages and call it cross-border. That's translation. The real question is *can Brazil's ministry run this next month* — which is only yes if the country layer is a **config directory** (`adapters/<iso>/`), not code. Enforced by a CI lint that fails on country literals in `core/`. The `CIVOS-IN` / `CIVOS-ZA` naming makes the architecture legible on a slide.

---

## 3. Decisions and their reasoning

### 3.1 Name: CIVOS
Chosen from a shortlist of SONAR, AGORA, CIVIC SONAR, AUDITA, CDPI.

**Why not an Indian name** — the important part. Nearly every Indian team will pick Jan-/Nagrik-/Vaani-/Setu-/Samvaad-something. Those names silently contradict a 20%-weighted portability claim: a Sanskrit or Hindi name tells a Brazilian evaluator, before a word is spoken, that this was built for one country. Neutral ground is free differentiation.

**Why CIVOS specifically** — invented, zero collision (AGORA collides with Agora.io, a major voice API; SONAR with SonarQube), reads as "civic OS", sits naturally beside MOSIP and Beckn. Needs a tagline to carry meaning, which is true of Aadhaar and UPI too.

**Rejected outright:** PRISM (permanent surveillance association — a landmine on a citizen-voice product), Ubuntu (major Linux distro, unusable in front of a Google Cloud jury).

### 3.2 Three input modalities — added 14 Aug, and *why* each exists
Not "three is better than one." Each buys something distinct:

- **Voice → access.** No literacy, no form, no departmental vocabulary. The only channel reaching the citizens most at risk of being missed.
- **Text → scale.** Messaging apps *and* bulk import of existing grievance records. Without the legacy importer we're not defragmenting, we're becoming fragment #5 — which is literally the failure the problem statement describes.
- **Image → evidence.** A voice note is a claim; a photo is corroboration.

**Why image was cheap (~2.5 h net):** Gemini takes audio, text and image parts in the *same* multimodal request. One extraction function, one output schema — not three pipelines. This is the primary reason for choosing Gemini multimodal over a chain of Speech-to-Text + Translation + Vision.

**Three side benefits that made it clearly worth it:**
1. **Hits all three Google AI categories the rules name** — GenAI, predictive modelling, *and* computer vision — instead of one. Directly serves the 25% criterion.
2. **De-risks the project's riskiest assumption.** Photos carry GPS EXIF → exact district via `ST_CONTAINS`, no inference. A portion of the corpus becomes geo-perfect regardless of how geo-grounding performs.
3. **Makes Loop 3 real.** Before/after photos of the same asset, matched by image embedding, are genuine impact verification rather than a synthetic time series.
4. **Tier-D accessibility floor** — a photo needs no language at all. A citizen whose language nothing supports can still be heard.

**What it cost:** corpus cut 5,000 → 3,000 signals, 30 min trimmed from API/importer polish, second-country adapter tightened 180 → 120 min. Schedule holds; **slack is gone**, so the drop order in plan.md is now load-bearing.

### 3.3 EvidenceStrength carries the *lowest* weight — deliberately
Photo-backed needs score slightly higher. Only slightly. If evidence counted for much, districts where nobody owns a camera would be punished twice — inverting the entire thesis. Measured at Gate 2; **set `w₅ = 0` without hesitation** if it skews toward richer districts.

### 3.4 Weight sliders are a trust feature, not a toy
`w₁…w₅` exposed in the UI with live recompute. A ministry will not adopt a ranking it cannot interrogate or re-weight to its own policy priorities. This converts the engine from an oracle into an instrument. Deployability, not decoration.

### 3.5 Data strategy: real official layer, synthetic citizen layer, *real* photos
- **Official layer 100% real** — NITI National MPI (district-level deprivation) + NFHS-5 district factsheets + boundary GeoJSON. This is the layer judges can independently verify, so it cannot be faked. *(Note: the SDG India Index is state-level only — it won't carry a district story.)*
- **Citizen text/voice synthetic**, generated from real deficits and real geography, with **deliberately biased participation rates** — the bias is required, it's what the product detects. **Labelled as synthetic in the UI itself.** Judges respect a labelled substitution far more than mystery data.
- **Evidence photos must be real** — ~150 openly-licensed, attributed. Vision accuracy demonstrated on generated images proves nothing.
- **Turn the weakness into a feature:** the generator ships as part of the DPG — a reference dataset + pilot simulator so a ministry can trial CIVOS *before* it has data. Every DPG has this problem; we solved it.

### 3.6 Stack: BigQuery as the analytical spine
`ML.GENERATE_EMBEDDING` + `VECTOR_SEARCH` (dedup + duplicate-photo detection), `ST_*` (spatial joins), `ARIMA_PLUS` (forecast in ~10 lines of SQL), `AI.GENERATE` (dossier text). One service, one auth, no infra glue — the difference between a solo builder shipping and not. FastAPI on Cloud Run, Next.js + MapLibre console.

**Next.js, not Streamlit** — and the reason is the **20% deployability score, not the 5% presentation score.** Streamlit reads as "prototype"; a ministry-grade console reads as "pilotable in weeks."

**No Vertex AutoML custom training** — `ARIMA_PLUS` satisfies "predictive modelling" in an afternoon instead of three days.

### 3.7 Telegram, not WhatsApp
WhatsApp Business API needs Meta business verification — days of latency, unavailable to an individual. Telegram: bot token in 5 minutes, native voice notes *and* photos, no verification. Ships with a documented `WhatsAppAdapter` stub behind the same interface. Honest substitution, no deduction.

### 3.8 Second country: deferred, not dropped
User initially chose India-only. Overridden as a *deferral*: the adapter abstraction is built on **Day 1** (nearly free then, a rewrite if bolted on later), and the second country is a 120-minute Phase 6 task with an explicit drop rule. **The decision happens 21 Aug, when it's known whether the hours exist** — not now.

South Africa preferred over Brazil: Stats SA municipal service-delivery data is English and cleanest. Brazil has better optics and a nicer Portuguese demo.

### 3.9 Privacy decisions worth remembering
- **Audio deleted immediately** after transcription
- **Original photos deleted** after extraction; thumbnail persists only if `people_present = false`; if people are detected, nothing visual is kept
- **EXIF GPS used to resolve the district, then discarded.** Storing precise citizen coordinates is a surveillance risk with zero product benefit and fails DPGA indicator 7 in any serious review
- Phone/Telegram IDs salted-hashed; admin unit only, never a point location
- k-anonymity suppression below 5 signals per district-sector

### 3.10 DPG compliance is a spec, not a vibe
Mapped against all **nine DPGA indicators** (see SPEC §11). Most submissions will read "designed as a Digital Public Good" as "MIT license." Apache-2.0 code, CC-BY-4.0 docs/data/schema, `LanguageModel`/`Warehouse`/`ChannelAdapter` interfaces documented with non-Google reference paths so platform independence is real. Google AI is the *reference implementation*, not a dependency of the design — which resolves the apparent tension with the mandatory-Google-AI rule.

---

### 3.11 Phase 0 build decisions — 14 Aug

**Cloud footprint.** New project `civos-in` (number `924096812044`), BigQuery and
all datasets in **`asia-south1` (Mumbai)**, billed to `018DA3-2878A5-EFBD38`
("Google developer prince", INR). Ten APIs enabled; BigQuery connection
`asia-south1.civos_vertex` holds `roles/aiplatform.user`.

*Worth revisiting:* an **unlinked USD GDP-credit billing account**
(`017792-FCAD52-97708C`, opened 14 Aug, zero projects) exists on the same account
and looks like redeemed hackathon credit. The INR account was chosen deliberately,
so spend hits a real payment method. Relinking is one command if that credit turns
out to be for this event.

**Maps Platform deliberately not enabled**, despite plan.md 0.1 listing it. The
console is MapLibre GL rendering our own simplified district GeoJSON — there is no
Google Maps call anywhere in the design, so a Maps key would be a billing surface
with no consumer.

**Region choice held, and it paid off.** `asia-south1` was the higher-risk Gate 0
path — the documentation warns that `AI.GENERATE` needs a fully-qualified global
endpoint there. Probed empirically, it does not: everything works in Mumbai, so
the DPDP-residency talking point costs nothing.

### 3.12 Gate 0 findings that change how the SQL gets written

Full evidence in `docs/GATE0-RESULT.md` — every attempt, with its exact SQL and error.

- **Embeddings need the `CREATE MODEL … REMOTE WITH CONNECTION` form.** The newer
  inline `AI.GENERATE_EMBEDDING(TABLE …, connection_id => …)` surface rejects
  `connection_id` in this region. SPEC's original `ML.GENERATE_EMBEDDING`
  assumption was correct — the concern that prompted the check was unfounded, and
  that is worth recording so nobody re-opens it.
- **`AI.GENERATE` works inline** with `connection_id` + a plain endpoint.
- **`gemini-2.5-flash`** for generation; **`gemini-embedding-001` at 3072 dims**.
  `gemini-3-flash` does not exist. Only three models are visible to the project.
- **`CREATE VECTOR INDEX` requires ≥ 5,000 rows.** Our corpus is ~3,000, so
  brute-force `VECTOR_SEARCH` is the correct choice — confirmed working. This is
  a precondition, not an unavailability, and the probe classifies it that way;
  reporting it as a failure would have sent Phase 4 chasing a non-problem.
- **The Vertex fallback was probed anyway and works** (generate + 3072-dim
  embeddings). It stays documented rather than hypothetical, which is what makes
  the `Warehouse` interface's platform-independence claim credible.

### 3.13 Language coverage — two claims that measurement corrected

Measured 14 Aug against live APIs: **Tier A 56 · Tier B 3 · Tier C 196 · Tier D
universal**. Both corrections are now automated so they cannot age badly.

1. **Tier C covers 19 of the 22 Scheduled Languages of India, not all 22.** No
   Translation pair exists for **Santali**, **Kashmiri** or **Bodo**. Konkani and
   Manipuri *are* covered but under `gom` and `mni-Mtei` — checking the obvious
   `kok`/`mni` would have under-reported them. The check now runs on every probe
   via `--check-list adapters/in/languages.yaml`, with the scheduled-language list
   living in the country adapter so the probe itself stays country-agnostic.
2. **Tiers A and B are a probed lower bound.** Speech-to-Text has no list-locales
   API and rejects bare language codes, so support is established by attempting a
   real recognition per candidate locale — 200 with zero results means supported,
   400 means not. Candidates are seeded from locales that have TTS voices, so
   Speech-to-Text locales without a voice are undercounted. Stated plainly in the
   coverage report: a measured lower bound beats a larger number copied from docs.

Also learned: `chirp_2` is not available in `asia-south1` (it is in `us-central1`),
and it accepts ~6 more locales than `long`. Both are probed and recorded per locale.

### 3.14 The country lint was brought forward from Phase 6

`scripts/lint_country_literals.py` + `config/country_literals.yaml` shipped in
Phase 0 rather than Day 8, because a rule enforced from the first commit is much
cheaper than one retrofitted onto finished code.

The plan's original `grep -riE '\b(india|IN)\b' core/` does not work: `IN` is a SQL
keyword and `in` is an English preposition, so it matches nearly every line of
Python ever written. The lint parses instead — string literals and identifiers are
**violations**, docstrings and comments are **notes** — and the watch list is YAML,
so adding a country to it is a config edit. Self-tested against a deliberate
violation, because a lint that never fires proves nothing.

---

## 4. Process decisions

- **Storyboard the video first; build only what appears in it.** Judges spend ~8 minutes total on a submission. Nobody reads the code. Locked storyboard is at the top of plan.md and functions as the build spec.
- **Film clips as each feature lands**, from Day 4 onward. Day 9 becomes editing, not filming. Shoot the phone-camera footage the day the widget works.
- **Two hard gates**, each decided the same day it's tested — never carried forward:
  - **Gate 1 (Day 3): geo-grounding ≥ 85%** on a hand-built 50-case set. Below that → mandatory district picker, reframed as "assisted geo-tagging with human confirmation." *This is the riskiest assumption in the whole project — everything downstream inherits its error.*
  - **Gate 2 (Day 5): vision sector accuracy ≥ 80%** on 30 hand-labelled images. Below → `w₅ = 0`, photos stay as dossier evidence but stop influencing the ranking.
- **Time-box every task at 1.5× estimate**, then take the fallback. A finished submission with three fallbacks beats an unfinished one with none.
- **Commit and push daily.** "Built during the hackathon period" is an explicit rule; commit history is the evidence.

---

## 5. Still open

**Needs the user's answer (non-blocking):**
- Which language for the live on-camera intake demo? A second Indian language in a **different script** is a stronger multimodal proof than Hindi + English.
- `.org` domain and GitHub org availability for CIVOS — worth 60 seconds before the repo URL goes into a submission.

**Resolved during build:**
- ✅ **[Day 1 — RESOLVED]** BigQuery ML/AI availability. **`PROCEED_BQML`** in `asia-south1`; no fallback needed. Details in §3.12, evidence in `docs/GATE0-RESULT.md`.
- **[Day 1]** Are NFHS-5 factsheets and NITI MPI tables machine-readable or PDF-locked? **Biggest schedule risk in the data phase.** 90-minute time-box, then fall back to data.gov.in CSVs and disclose the substitution. *Now the top open risk, since Gate 0 cleared.*
- **[Day 3]** Source ~150 openly-licensed infrastructure photos across five sectors and their asset types. Uneven coverage is acceptable and realistic; shoot a handful personally if needed.
- **[Day 8]** South Africa or Brazil — decide only when the 120 minutes actually exist.

---

## 6. Documents

| File | What it holds |
|---|---|
| [SPEC.md](SPEC.md) | Full PRD — personas, three loops, multimodal + multilingual spec, sector model, prioritisation formulas, dossier requirements, P0/P1/P2, privacy, DPGA mapping, metrics |
| [plan.md](plan.md) | 8 phases, hour-budgeted, locked storyboard, two gates, cut list, drop order, risk register |
| [EXPLAINER.md](EXPLAINER.md) | Plain-language version + the 30-second spoken pitch |
| **memory.md** | This file — decisions and reasoning |

---

## 7. Next action

**Phase 0 is done and Gate 0 passed.** Next is **Phase 1 — the real data layer,
15 Aug, 5.5 h**, and it is now the riskiest phase in the project.

The one thing that actually matters tomorrow: find out within 90 minutes whether
NFHS-5 district factsheets and the NITI National MPI district table are
machine-readable or PDF-locked. If extraction blows the time-box, fall back to
whatever is already CSV on data.gov.in for that sector and disclose the
substitution in the README. **Two real sectors with clean data beat five sectors
with mangled numbers.**

Order of work: boundary GeoJSON first (1.1), because district code reconciliation
(1.4) is the boring task that silently breaks everything downstream and it needs
the boundaries in hand.

Everything Phase 1 writes goes through `Warehouse.load_table()` — the interface
already exists, so there is nothing to design first.
