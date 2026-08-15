# CIVOS — Build Plan

**Solo · 14 Aug → 22 Aug 2026 · 5.5 h/day · ~44 h total**
*v1.1 — adds the image modality and reallocates hours to pay for it*

> **Target submission: 22 August.** The hard deadline is 24 August. You will not be the person filing a support ticket at 11:40 pm on deadline night — hackathon platforms fall over under submission load. The 23rd and 24th are buffer. Treat them as if they do not exist.

**Budget reality:** 44 h total − 10 h submission assets = **34 h of code.** Every hour below is allocated.

**What the image modality cost, and where it came from.** Adding image input is ~2.5 h net — cheap only because Gemini takes audio, text and image in the *same* multimodal call, so it is one code path rather than a third pipeline. It is funded by: the synthetic corpus dropping from 5,000 to 3,000 signals (nobody counts, 3,000 renders just as dense), 30 minutes trimmed from API and importer polish, and the second-country adapter tightening from 180 to 120 minutes. **The schedule holds, but the slack is gone.** The drop order in §Cut List is now load-bearing.

---

## The Storyboard — build only what is on this list

Lock this first. It is not a marketing artefact, it is the build spec. If a feature does not appear in these 4 minutes, it does not get built.

| Time | Beat | What must exist to film it |
|---|---|---|
| 0:00–0:20 | **The gap.** Millions of grievances filed last year. None of them moved a budget line. | Deck slide only |
| 0:20–0:50 | **Live voice intake.** You speak a complaint in an Indian language. Structured JSON appears: sector, severity, district, original + English. | P0-1, P0-4, P0-5 |
| 0:50–1:10 | **Live photo intake.** Photograph a broken thing. Vision returns asset type, condition flags, severity — *and the district, from EXIF, exactly.* One line of narration: *"a voice note is a claim; a photo is evidence."* | P0-1, P0-4, P0-6, P0-8 |
| 1:10–1:45 | **Zoom out.** 3,000 signals on a district choropleth. *"Here's what's wrong with this map."* Every hotspot is a well-connected district. | P0-7, P0-11 |
| 1:45–2:30 | **The turn.** Flip to equity-adjusted. New districts light up. *"These have the worst deficit and have never filed a single request. Silence isn't satisfaction."* | P0-9, P0-10, quadrant view |
| 2:30–3:10 | **The dossier.** Click a Silent Need district → generated dossier with the evidence photo strip. Citations to signal clusters, images, and dataset rows. Cost band. Named scheme. | P0-12, P0-13 |
| 3:10–3:35 | **Country flip.** `CIVOS-IN` → `CIVOS-ZA`. Same code, different adapter, real data, new language. | P1-2 (or P0-14 + adapter guide as fallback) |
| 3:35–4:00 | **Close.** Loop 3 before/after image pair, DPGA compliance, repo, adapter spec. | P1-5, P1-7 |

**Film as you build.** Screen-record each feature the day it lands. Day 9 then becomes editing, not filming — the difference between a finished video and a rushed one. For the 0:50 photo beat, shoot the real footage on your phone the day the widget works, not on submission day.

---

## Phase 0 — Foundations · 14 Aug · 3 h — ✅ **COMPLETE**

| # | Task | Time | Status |
|---|---|---|---|
| 0.1 | GCP project `civos-in`, billing linked, 10 APIs enabled, `asia-south1` BigQuery connection `civos_vertex` + `roles/aiplatform.user`, datasets created. **Maps Platform deliberately not enabled** — the console is MapLibre over our own GeoJSON, so a Maps key would be a billing surface with no consumer. | 30 m | ✅ |
| 0.2 | **Gate 0 probe** — `scripts/gate0_probe.py`, tries multiple syntax variants per capability and records the exact SQL and error for each. → `docs/GATE0-RESULT.md` | 45 m | ✅ `PROCEED_BQML` |
| 0.3 | Monorepo skeleton, `uv` + Python 3.12, Apache-2.0 `LICENSE`, `OWNERSHIP.md`, `README.md`, git initialised. | 30 m | ✅ |
| 0.4 | `ChannelAdapter`, `LanguageModel`, `Warehouse` interfaces + Pydantic models. `LanguageModel.extract()` takes a `parts[]` list. Every interface docstring names a non-Google reference path (DPGA indicator 4). `NormalisedSignal` carries `project_id`, `funded_at` and all image fields from day one. | 30 m | ✅ |
| 0.5 | Language capability probe → `config/languages.generated.yaml` + `docs/LANGUAGE-COVERAGE.md`. **All four tiers are API-probed** — Speech-to-Text has no list API, so support is established by attempting a real recognition per locale. | 45 m | ✅ 56 / 3 / 196 / universal |
| 0.6 | **Country-literal lint** brought forward from 6.1 — `scripts/lint_country_literals.py`, self-tested against a deliberate violation. The plan's original `grep -E '\bIN\b'` would match every English "in"; this scans string literals, identifiers and comments separately. | +20 m | ✅ passes on `core/` |

> ### GATE 0 — BigQuery ML · **PASSED 14 Aug → `PROCEED_BQML`**
> All four function families are available in `asia-south1`. Full evidence, with the exact SQL and every error, in [docs/GATE0-RESULT.md](docs/GATE0-RESULT.md). The Vertex + scikit-learn fallback is **not** needed — though it was probed anyway and works, so it stays documented rather than hypothetical.
>
> Carry these three findings into Phase 4:
> - Embeddings need `CREATE MODEL … REMOTE WITH CONNECTION` + `ML.GENERATE_EMBEDDING`. The inline `AI.GENERATE_EMBEDDING(… connection_id => …)` surface is not available in this region.
> - `AI.GENERATE` works inline with a plain endpoint — no global-endpoint qualification needed.
> - `gemini-2.5-flash` and `gemini-embedding-001` (3072 dims). `CREATE VECTOR INDEX` needs ≥ 5,000 rows, so at ~3,000 signals use brute-force `VECTOR_SEARCH`, which is confirmed working.

---

## Phase 1 — The Real Data Layer · 15 Aug · 5.5 h — ✅ **COMPLETE**
*The layer judges can independently verify. Full provenance in [docs/DATA-RECONCILIATION.md](docs/DATA-RECONCILIATION.md).*

| # | Task | Status |
|---|---|---|
| 1.1 | District boundary GeoJSON — 594 districts, 33 MB simplified to 880 KB with mapshaper, topology preserved. | ✅ (done early) |
| 1.2 | NFHS-5 district indicators → tabular. **PDF extraction never happened** — `rchiips.org` 404s with an invalid TLS cert, so the official PDFs are unreachable. Two independent community extractions used instead and **cross-validated against each other**: 100% identical across 274 overlapping districts, max diff 0.00. | ✅ 644 districts |
| 1.3 | ~~NITI National MPI district table.~~ **Dropped, deliberately** — the MPI is *computed from* NFHS-5, which we already have at district level. Loading a derived index alongside its own source adds a citation, not information. | ⏭ skipped with reason |
| 1.4 | Reconcile district codes. **537/594 (90.4%) matched.** State agreement made mandatory after a national name-only fallback matched Sikkim's "East" to Delhi's "East". | ✅ |
| 1.5 | Load to BigQuery: `dim_admin_unit` (594), `fact_deficit_indicator` (2,685) with source + year. | ✅ |
| 1.6 | `adapters/in/sectors.yaml` | ✅ (done early) |
| 1.7 | `adapters/in/schemes.yaml` — 10 real central schemes with unit costs. | ✅ (done early) |

> **The time-box fallback was taken, and it paid.** The rule said "fall back to whatever is already CSV and note the substitution". That is exactly what happened — and the cross-validation between two independent extractions is stronger evidence than a single PDF parse would have been.
>
> **4 of 5 sectors carry real data.** Roads & Transport has no NFHS-5 equivalent — road connectivity is not a health-survey measure. It is left visibly empty in the console rather than filled with a proxy, per this plan's own rule that two real sectors beat five mangled ones.

---

## Phase 2 — Signal Corpus, Evidence Images + The Gate · 16 Aug · 5.25 h

| # | Task | Time |
|---|---|---|
| 2.1 | Signal schema + BigQuery table. Include `project_id`, `funded_at` (P2-4), `has_image`, `asset_type`, `condition_flags`, `geo_confidence`, `image_thumb_uri` **now** so nothing needs migrating later. | 30 m |
| 2.2 | Synthetic text/voice corpus: ~**3,000** signals via batched Gemini calls. Grounded in real district deficits, 10+ languages, realistic code-mixing, vague geo-descriptions, **deliberately biased participation rates** (urban/connected districts over-represented — you need the bias, it is what the product detects). | 90 m |
| 2.3 | **Evidence image set: ~150 real, openly-licensed photographs** across the five sectors and their asset types (Wikimedia Commons and equivalents). Attribute every one in `docs/IMAGE-ATTRIBUTION.md`. Attach to a subset of signals — deliberately *not* all of them, so `EvidenceStrength` has real variance. **Do not generate synthetic images:** vision accuracy has to be demonstrated on real photographs or the whole modality is theatre. | 45 m |
| 2.4 | Build the **50-case geo-grounding test set** by hand. Vague, realistic, messy. The most valuable hour of the week. | 60 m |
| 2.5 | Geo-grounding v1: Gemini + district gazetteer + `ST_*` reconciliation. Measure against 2.4. | 90 m |

> ### GATE 1 — Geo-grounding accuracy *(the riskiest assumption in the project)*
> Everything downstream inherits this error. Mushy geo-grounding makes `DemandIndex` noise, which makes the quadrants noise, which makes the silence turn collapse.
>
> - **≥ 85%** → proceed as designed.
> - **< 85%** → add a **mandatory district picker** to the intake UI. Reframe in the pitch as *"assisted geo-tagging with human confirmation"* — honestly what a real deployment would want anyway.
>
> **The image modality softens this gate.** Photos with GPS EXIF resolve exactly via `ST_CONTAINS` with no inference at all, so a portion of your corpus is geo-perfect regardless of how 2.5 performs. Report the two paths separately: `geo_confidence = high` (EXIF) vs `inferred`.
>
> **Decide today. Do not carry this question into Day 5.**

---

## Phase 3 — Multimodal Intake · 17 Aug · 6 h
*Runs half an hour long. Budgeted for — Phase 6 gave it up.*

| # | Task | Time |
|---|---|---|
| 3.1 | **Single Gemini multimodal extraction call.** Accepts any combination of audio, text and image parts; returns one schema-enforced JSON object (SPEC §6.2 field list). One call, not a chain — this is the whole reason image was cheap to add. | 90 m |
| 3.2 | FastAPI on Cloud Run: `POST /signal` (multipart — audio, image, text), `POST /import` (bulk CSV), `GET /aggregate`. OpenAPI 3.1 emitted. | 60 m |
| 3.3 | **Multimodal web widget:** mic (`MediaRecorder`) + camera/upload (`<input capture>`) + text box, all posting to the same endpoint. Auto language detect, no dropdown. Shows the structured result live — this is the 0:20 and 0:50 shots, make them look good. | 105 m |
| 3.4 | **EXIF GPS path:** parse EXIF, resolve via `ST_CONTAINS`, flag `geo_confidence = high`, then **discard the coordinates** (SPEC §11 — storing them is a surveillance risk with no product benefit). | 30 m |
| 3.5 | **Image PII safety gate:** `people_present = true` → discard original, persist attributes only, no thumbnail. All originals deleted after extraction regardless. Mirror the existing audio-deletion policy so the retention story is one sentence. | 30 m |
| 3.6 | Telegram bot: text + voice note + **photo**, all to the same endpoint. `WhatsAppAdapter` stub with a docstring explaining the verification constraint. | 45 m |
| 3.7 | Bulk legacy importer — proves defragmentation rather than becoming fragment #5. | 20 m |

---

## Phase 4 — The Intelligence Layer · 18 Aug · 5.5 h
*Mostly SQL. This is where BigQuery earns its place.*

| # | Task | Time |
|---|---|---|
| 4.1 | `ML.GENERATE_EMBEDDING` over signal text — including `visual_description` for image-only signals, so photos cluster alongside voice notes about the same problem. | 30 m |
| 4.2 | `VECTOR_SEARCH` dedup → distinct-need clusters. Pick centroid signals as the representative quotes, and centroid images as the dossier evidence strip. | 75 m |
| 4.3 | Scoring SQL: `DemandIndex`, `DeficitIndex`, `ParticipationRate`, `VoiceCorrection`, `AdjustedDemand`, **`EvidenceStrength`**, `SilenceGap`, `Priority`. Materialise as a view. | 90 m |
| 4.4 | Quadrant assignment: Act Now / Silent Need / Expectation Gap / Stable. | 30 m |
| 4.5 | `ARIMA_PLUS` 90-day forecast per district-sector. ~10 lines of SQL — do not let this expand. | 30 m |
| 4.6 | k-anonymity suppression (< 5 signals per district-sector) + scheme match join. | 45 m |
| 4.7 | **Vision accuracy check:** hand-label 30 images by sector and asset type, measure the extraction against them. | 30 m |

> ### GATE 2 — Vision accuracy
> - **≥ 80% sector accuracy** → keep `w₅·EvidenceStrength` in the ranking.
> - **< 80%** → keep the photos as dossier *evidence* (they still corroborate visually to a human reader) but **set `w₅ = 0`** and demote `EvidenceStrength` to a reported metric. The modality still earns its computer-vision credit; it just stops influencing the ranking on shaky ground.
>
> Also check for the urban-skew distortion flagged in SPEC §13 — if evidence-rich districts are simply the richer ones, `w₅ = 0` regardless of accuracy.

> **Sanity check before you sleep:** the Silent Need list must be non-empty and its districts plausible — genuinely deprived, genuinely quiet. Empty means your participation bias was too weak; everything means your normalisation is broken. Five minutes, protects the entire narrative.

---

## Phase 5 — The Console · 19–20 Aug · 11 h
*What judges click. Carries the 20% deployability score, which is why this is Next.js and not Streamlit — a ministry-grade console reads as pilotable, a notebook-style app reads as a prototype.*

**Day 6 (19 Aug) — 5.5 h** · ⚡ **built early, 15 Aug** — see §Console, below

| # | Task | Time | Status |
|---|---|---|---|
| 5.1 | Next.js app, single page, three panels. No routing, no state library. | 60 m | ✅ |
| 5.2 | MapLibre GL district choropleth, colour-ramped by `Priority`. 594 real districts. | 120 m | ✅ |
| 5.3 | Sector filter + quadrant filter. **The raw ↔ equity-adjusted toggle is the 1:45 money shot.** | 90 m | ✅ |
| 5.4 | Ranked district list synced to map selection, with rank-movement deltas. | 60 m | ✅ (modality mix pending real data) |

**Day 7 (20 Aug) — 5.5 h**

| # | Task | Time | Status |
|---|---|---|---|
| 5.5 | District drilldown drawer: every score term broken out, signal samples in original language + English, evidence strip, scheme + cost band. | 90 m | ✅ |
| 5.6 | **Weight sliders** (`w₁…w₅`) with live recompute. An instrument, not an oracle. | 60 m | ✅ |
| 5.7 | Dossier view: all 11 required elements including the **evidence photo strip**, numbered claims resolving to an evidence table. Grounded Gemini generation from a retrieved bundle only. | 120 m |
| 5.8 | Synthetic-data banner (persistent, honest — and note that *evidence images are real, citizen text is synthetic*, because that distinction is to your credit) + Silent Need card with the **"Dispatch outreach"** action label, pre-empting the *"you're ignoring citizens"* objection inside the product. | 30 m |
| 5.9 | Deploy to Cloud Run. Verify the public link works in an incognito window with no credentials, **including camera and mic permission prompts over HTTPS.** | 30 m |

> **Browser permissions are a classic submission-day failure.** `getUserMedia` for both mic and camera requires a secure context — test the deployed URL on a phone as well as your laptop before you film.

---

## Phase 6 — Portability & DPG · 21 Aug · 5.5 h

| # | Task | Time |
|---|---|---|
| 6.1 | ~~Lint check for country literals in `core/`.~~ **Already shipped in Phase 0** as `scripts/lint_country_literals.py` + `config/country_literals.yaml`. Remaining work here is only wiring it into CI. | ~~30 m~~ 10 m |
| 6.2 | **Second country adapter.** One province, one real indicator, boundary GeoJSON, language list, ~5 real schemes. South Africa (Stats SA municipal service-delivery data — English, cleanest) or Brazil (IBGE — better optics, Portuguese demo). **Tightened to 120 m — first thing to drop.** | 120 m |
| 6.3 | Country switcher in the console (`CIVOS-IN` / `CIVOS-ZA`). The 3:10 shot. | 45 m |
| 6.4 | Loop 3 precomputed before/after for one district, **using a real before/after image pair** matched by embedding + admin unit. Labelled as a demonstration. | 60 m |
| 6.5 | DPGA 9-indicator self-assessment → `docs/DPG-COMPLIANCE.md`. Adapter authoring guide. `docs/IMAGE-ATTRIBUTION.md`. README. | 75 m |

> **If Gate 1 failed or Phase 1 overran, drop 6.2 and 6.3.** Ship the adapter guide + lint check and argue portability from the architecture. Costs some of the 20%, but a broken country switch on camera costs more.

---

## Phase 7 — Submission · 22 Aug · 5.5 h

| # | Task | Time |
|---|---|---|
| 7.1 | Edit the 4-minute video from clips already recorded during Phases 3–6. Record narration last, over locked picture. | 150 m |
| 7.2 | 11-slide deck: Problem · Insight (the silence thesis) · Solution · Three modalities and why · Live demo stills · Architecture · Google AI mapping (all three categories) · Cross-border adapter · DPG compliance · Impact · Deployment path. | 120 m |
| 7.3 | 2–3 line description. Write it last — by now you know what you actually built. | 15 m |
| 7.4 | Repo hygiene: README with setup, screenshots, architecture diagram, image attribution, honest limitations section. **Judges trust a stated limitation more than a silent gap.** | 30 m |
| 7.5 | **Submit all five artefacts.** Repo · video · deck · description · deployed link. | 15 m |

---

## Cut List — already decided

Do not relitigate these at 1 am on Day 6.

| Cut | Why |
|---|---|
| WhatsApp Business API | Meta business verification is not available to an individual on this timeline. Telegram proves the same requirement in 5 minutes. |
| **Video input** | 10× the payload for marginal signal over a photo. The `parts[]` interface accepts it later. |
| Auth / RBAC / user accounts | Zero rubric marks. Role is a URL parameter. |
| PDF export of dossiers | Browser print is free. |
| Vertex AutoML custom training | `ARIMA_PLUS` satisfies "predictive modelling" in ten lines of SQL. |
| Real-time / websockets | Indistinguishable from polling in a video. |
| Live Loop 3 | Requires months of elapsed time. Precomputed with a real image pair is honest and demos identically. |
| Long-term photo storage | Privacy liability, no product benefit. Thumbnail + attributes only. |
| Synthetic evidence images | Vision accuracy demonstrated on generated images proves nothing. Real, attributed, openly-licensed photos or none. |
| Mobile-responsive console | Judges evaluate on a laptop. The **citizen widget** must be mobile-perfect — it now has a camera in it; the policymaker console does not. |
| Elaborate simulator framework | The corpus generator is one batch script. |

### Drop order if you fall behind
Now load-bearing, since the image modality consumed the slack. Drop from the top:

1. **6.2 + 6.3** — second country adapter and switcher *(argue portability from the lint check and adapter guide instead)*
2. **P1-4** — image-embedding duplicate-submission check
3. **6.4** — Loop 3 before/after
4. **5.6** — weight sliders
5. **5.4** — modality mix in the ranked list

Never drop: the equity toggle (5.3), the dossier (5.7), or either live intake shot (3.3). Those are the video.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Geo-grounding under 85% | Medium | **High** — collapses the core narrative | Gate 1 on Day 3; district-picker fallback pre-designed; EXIF path gives a geo-perfect subset regardless |
| NFHS-5 / MPI data locked in PDFs | **High** | Medium | 90-minute time-box; fall back to data.gov.in CSVs and disclose the substitution |
| Vision misclassifies sector | Medium | Medium | Gate 2 on Day 5; `w₅ = 0` fallback keeps photos as evidence without letting them skew the ranking |
| Openly-licensed photos hard to find per asset type | Medium | Medium | Accept uneven coverage across sectors — uneven `EvidenceStrength` is realistic and honest. Shoot a handful yourself if needed |
| `EvidenceStrength` skews ranking toward urban districts | Medium | **High** — inverts the entire thesis | Explicitly measured at Gate 2. Lowest weight by design; zero it without hesitation |
| Camera/mic permissions fail on the deployed URL | Medium | **High** — kills two demo shots | Test on deployed HTTPS on both phone and laptop at 5.9, days before filming |
| BigQuery ML unavailable in region or quota-capped | Low | High | Gate 0 today; Vertex embeddings + sklearn/statsmodels fallback |
| Console overruns its 11 h | **High** | Medium | Single page, no routing, no state library. Follow the drop order |
| Second-country data harder than expected | Medium | Medium | Scoped to one province, one indicator, 120 m. Drop first |
| Video rushed on Day 9 | **High** | Medium | Film clips continuously from Day 4. Shoot the phone-camera footage the day the widget works |
| Solo illness / life event | Low | **Fatal** | Submit on the 22nd, not the 24th. That is what the buffer is for |

---

## Daily Discipline

1. **Start every day by re-reading the storyboard.** If today's work does not appear in those 4 minutes, you are building the wrong thing.
2. **Screen-record whatever you finish, the day you finish it.**
3. **Commit and push every day.** "Built during the hackathon period" is a rule — your commit history is the evidence.
4. **Time-box every task at 1.5× the estimate.** At the limit, take the fallback and move. A finished submission with three fallbacks beats an unfinished one with none.
5. **Cite every reused component, and every photograph.** Explicit rule, thirty seconds, and the image attribution file doubles as DPG evidence.
