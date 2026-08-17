# CIVOS — Revision Plan

**Written 17 Aug 2026 · 5 days to target submission (22 Aug) · hard deadline 24 Aug**

This is **not** a replacement for [plan.md](plan.md), which is the original day-by-day
build plan and still stands. This document covers only what a review of the built
system says should **change** before submission, in priority order, with the rubric
weight each item moves.

Every item states its effort honestly and its done-when condition. Items are
ordered so that stopping at any point leaves the system in a defensible state.

---

## The one-paragraph summary

The front end, the multimodal intake, the Telegram channel and the real deficit
layer are all built and live. Two things undermine the product's own central claim
— *measurement integrity* — and both sit in the synthesis layer rather than the
interface. One of them (`connectivity`) decided which districts appeared as **Silent
Need**, the single output the whole pitch rests on, and it was a hash of the
district code. **Both are now fixed** — see the status table below.

The largest remaining scoring gap is **Cross-Border Applicability (20%)**, which is
still unbuilt; the landing page no longer implies otherwise.

---

## Priority order

| # | Item | Status | Rubric | Risk if skipped |
|---|---|---|---|---|
| **R0** | Stop implying `adapters/za/` exists | ✅ **done** | Integrity | A judge finds a false claim on the front page |
| **R1** | Make `connectivity` a real indicator | ✅ **done** | Problem–Solution Fit 20% · Impact 10% | "Why is this district silent?" has no answer |
| **R2** | Stop the dossier prose laundering placeholders | ✅ **done** | Impact 10% | Exported dossier states a hashed number as fact |
| **R3** | Boundary provenance + licence | ✅ **done** — GADM replaced with DataMeet (CC-BY 4.0) | Deployability 20% | GADM prohibited redistribution |
| **R4** | Write down the NFHS extraction licence argument | ✅ **done** | Deployability 20% | A blank licence cell reads as an oversight |
| **R5** | Load real district population | ⬜ open · 1.5 h | Impact 10% | Last remaining placeholder in a scored output |
| **R6** | Real Roads & Transport deficit | ⬜ open · 2–3 h | Problem–Solution Fit 20% | 1 of 5 sectors stays empty |
| **R7** | `CIVOS-ZA` adapter on real data | ⬜ open · 6–10 h | **Cross-Border 20%** | Largest single scoring gap in the submission |

**R0–R4 are complete.** Every integrity and licensing issue found in the review is
closed. R7 remains the biggest score and the hardest call.

### What R3 produced — better than a licence fix

Replacing GADM with the **DataMeet Census-2011** set (CC-BY 4.0, redistribution
permitted) improved the data materially:

| | GADM (before) | DataMeet (after) |
|---|---|---|
| Licence | redistribution prohibited | **CC-BY 4.0** |
| Districts | 594 | **641** |
| NFHS-5 reconciliation | 537/594 = 90.4%, fuzzy names | **639/641 = 99.7%** |
| Match method | name matching | **628 by exact census code** |
| "No official data" in the console | 57 district-sectors | **2** |
| Rebuildable from the repo | no | **yes** (`scripts/build_boundaries.py`) |

The census-code join is the substantive win: it removes the class of silent error
that once married Sikkim's *East* district to Delhi's *East*.

**A sentinel polygon had to be caught.** The upstream shapefile carries
`DISTRICT = "Data Not Available"` with census codes `99/99` for the un-enumerated
area, and NFHS carries a matching placeholder row — so the join produced a
"district" at 0% schooling and 0% electricity. Left in, it dragged the
participation-capacity floor from 39.0 to 0.0 and compressed every real district's
connectivity. It is now flagged in the boundary properties, excluded from
reconciliation and capacity, and still rendered as no-official-data.

**Gate 1 was re-run, and the number went down.** The gazetteer changed from 594 to
641 districts, so 98.1% was no longer a measurement of the shipped system. Re-run:
**PASS at 94.2% (49/52), with 1 confidently wrong** (Nandurbar to Dhule; Nandurbar
was split from Dhule in 1998). Two original misses were stale identifiers — the
answer key encoded GADM's spellings `Dhuburi` and `Nabarangpur`, and the resolver
returned the same real districts under DataMeet's `Dhubri` and `Nabarangapur`.
Those two were updated; **the genuine Junagadh miss was left untouched**, per the
rule this project already wrote down: editing an answer key after seeing the score
is the tuning the test set exists to prevent.

The run was **not** re-rolled for a better number. Live claims on the landing page
and in the dossier now read 94.2%, and the "zero confidently wrong" line is gone
because this run had one.

**Open follow-up:** two Gate 1 runs disagreed (98.1% then 94.2%, different misses),
so the resolver is nondeterministic at this sample size. A 3-run median with the
variance disclosed would be a more honest headline than any single run. Not done —
flagged.

### What R1 actually produced

Figures below are after R3's boundary swap, on 641 districts.

| | Mean *women with 10+ yrs schooling* |
|---|---|
| Silent Need districts | **33.9%** |
| All other scored districts | 43.0% |
| National mean | 40.8% |

Highest-priority Silent Need districts are **Pashchimi Singhbhum, Koraput, Jamui,
Bahraich, Chatra, Deoghar, Purnia** — schooling 14–28%, several of them NITI Aayog
Aspirational Districts. Equity-adjusted top of the ranking is **Cachar, Pakur,
Hailakandi**, with rank movements up to **▲278**.

Water & Sanitation Silent Need is now **158** district-sectors, and "no official
data" fell from 57 to **2**. **Screenshots in `docs/screenshots/` are stale and the
demo narration needs re-reading against the new ranking.**

Two things were found while implementing, neither in the original plan:

- **`docs/DATA-RECONCILIATION.md` is generated**, so the R4 text had to go into
  `scripts/build_deficit_layer.py`, not the file. A hand-edit was silently
  destroyed by the first regeneration.
- **The fixture generator could not be re-run from the repository** — it required
  the original upstream GeoJSON, which is not committed. It now also accepts its
  own previous output, so the whole data pipeline is reproducible from the repo
  alone. That was arguably a bigger reproducibility gap than anything in the plan.

---

## R0 — Stop implying `adapters/za/` exists

**Now, before anything else. 15 minutes.**

`adapters/` contains `in/` only. There is no `za/`, no second-country data, and no
country switch behind the UI. But the landing page (`console/app/page.tsx`,
section 06) renders `adapters/za/` in its repository-layout panel and ships a
`CIVOS-IN ⇄ CIVOS-ZA` toggle, which reads as a working capability.

This is the only unlabelled claim in the project, and it sits on a page whose
argument is *"a labelled substitution is worth more than mystery data."* The
inconsistency is more damaging than the missing feature.

**Two options, pick one:**

- **If R7 will be built:** leave the panel, but label the switch
  `illustrative — adapters/za/ lands in Phase 6` until it is real.
- **If R7 will not be built:** change the panel to show `adapters/za/` as the
  *shape* an adapter takes, worded as a specification rather than an inventory,
  and remove the instance toggle.

**Done when:** nothing on the deployed site asserts a capability that
`adapters/` does not contain.

---

## R1 — Make `connectivity` a real indicator

**The highest-leverage change available. 3–4 hours including regeneration.**

### What is wrong

`scripts/generate_corpus.py:211` builds the participation bias as:

```python
conn   = rnd_from("conn", code)          # sha256(district_code) → [0,1)
weight = deficit * (conn ** 1.6) + 0.05
```

The *shape* is right — real deprivation × ability-to-report is the correct model
of participation bias, and it is the reason the Silent Need quadrant populates at
all. But `conn` is **noise**: a hash of a string, with no relationship to
urbanisation, literacy or device ownership.

Consequence: the Silent Need set — the product's headline output — is decided
arbitrarily. The demo-killing question is one sentence long: *"Why is this
district silent and its neighbour not?"* There is currently no answer that can be
said out loud.

### The fix, using data already downloaded

`data/raw/` contains **105 distinct NFHS-5 indicators. Five are used.** Already
present and unused:

| Indicator | Proxies |
|---|---|
| `Women with 10 or more years of schooling (%)` | literacy and the agency to navigate a grievance process |
| `Population living in households with electricity (%)` | household infrastructure, device charging |
| `Female population age 6 years and above who ever attended school (%)` | already loaded as the education deficit |

Build `connectivity` as a normalised composite of the first two:

```
connectivity(d) = normalise( 0.6 · schooling_10yr(d) + 0.4 · electricity(d) )
```

Weighting is a judgement call, not a finding — state it in the docs and expose the
reasoning, the same way the `w1..w5` sliders already do.

### Implementation notes

- **Two call sites must agree.** `generate_corpus.py:210` and
  `generate_console_fixtures.py:269` both compute `conn`, and the code comment at
  `generate_corpus.py:209` says explicitly that they must match. Change both or
  the corpus and the fixture describe different worlds.
- Districts with no NFHS value need an explicit fallback. Do **not** default to
  a mid-range number — that quietly invents connectivity for exactly the
  districts most likely to be poorly surveyed. Prefer excluding them from
  sampling and flagging them, consistent with how missing deficit is handled.
- Regenerate: `generate_corpus.py` → `build_deficit_layer.py` →
  `generate_console_fixtures.py`.

### Consequence to plan for

**The Silent Need list will change**, and it will probably stop being evenly
scattered — real schooling and electricity data will likely cluster it into
Bihar, Jharkhand, eastern Uttar Pradesh and tribal Madhya Pradesh.

That is a truer and stronger story. It is also a **different map** from the one
`docs/screenshots/` and the demo narration are built around. Budget 1 hour to
re-shoot screenshots and re-read the 1:40 narration.

**Done when:** the Silent Need classification for any district can be explained
from two named real indicators, and `docs/` records the formula and the weighting
rationale.

---

## R2 — Stop the dossier prose laundering placeholders

**15 minutes. Do this even if R5 is skipped.**

The interface is honest: `components/Dossier.tsx:244` carries the visible caption
*"Derived from a placeholder district population — no census population loaded
yet."*

But the number is sent to Gemini as `population_affected`, and the caveat
instruction in `api/main.py` says only:

```
4. Data quality and caveats (include: citizen layer is synthetic, evidence photos are real)
```

So the generated prose states *"An estimated 2,70,255 residents are affected"*
**with the caveat stripped off** — in the one artefact designed to be exported and
attached to a funding note. `SPEC.md §12` prices population-affected estimates as
an Impact Potential lever, which means the laundered number is also a scored one.

**Fix:** extend the caveat instruction to name every placeholder in the bundle,
and pass the placeholder status as a field rather than relying on prompt prose:

```
4. Data quality and caveats — you MUST state: the citizen signal layer is
   synthetic; evidence photographs are real and openly licensed; and the
   population-affected figure derives from a placeholder district population,
   not a census count.
```

**Done when:** generated prose that cites a population figure also states its
provenance, verified on a live call.

---

## R3 — Boundary provenance — ⚠️ escalated

**Now the most consequential open item in the data layer. Needs a decision, not an
afternoon.**

Investigating this found the source, and the answer is worse than "undocumented".
`scripts/generate_console_fixtures.py` reads `NAME_1` and `NAME_2` — **GADM's**
property convention — and `build_deficit_layer.py` aliases state names back to
`orissa` / `uttaranchal` / `nctofdelhi`, which is GADM 2.x-era naming.

**GADM permits academic and non-commercial use but prohibits redistribution
without prior permission.** CIVOS commits a derived, simplified copy of that
geometry to a public repository under Apache-2.0 / CC-BY-4.0. If the source is
GADM — and the evidence is strong — then the repository is redistributing data it
has no licence to redistribute, and the blanket data licence in `OWNERSHIP.md` is
wrong for that layer.

For a submission whose licence posture is part of its Digital Public Good argument,
this is the one finding that could be turned against it.

**Three options:**

1. **Confirm and replace.** Swap to **DataMeet** Census-2011 district boundaries
   (ODbL — redistribution permitted, share-alike, needs a per-layer carve-out in
   `OWNERSHIP.md`). District codes are already `IN-<state>-<slug>` and the fixture
   generator now round-trips its own output, so the swap is mostly a re-run plus a
   name-reconciliation pass. **Estimate 2–3 h.** This is what I would do.
2. **Confirm and request permission.** Email GADM. Free, but the answer will not
   arrive before the 22nd.
3. **Document the uncertainty and ship.** Already done in the README — the risk is
   named rather than hidden, which is the minimum defensible position. Weakest of
   the three, but not indefensible.

**First step regardless:** find the file that was passed to `--geojson` and check
its actual provenance. Everything above is inference from the code, and the
inference should not be written down as fact until confirmed.

### Original scope (still applies once the source is settled)

**45 minutes. This one has a legal edge, not just a documentation one.**

`console/public/data/districts.geojson` (594 features) is the **only real layer
with no attribution document.** `DATA-RECONCILIATION.md`, `IMAGE-ATTRIBUTION.md`
and `FONT-ATTRIBUTION.md` all exist; boundaries have nothing.

The origin is not recoverable from the file — `generate_console_fixtures.py`
rewrites `properties` down to `{code, name, state}`, discarding whatever the
source carried. What is knowable from the repo:

- `build_deficit_layer.py:106` calls it *"the 2011-era boundary file"*
- `STATE_ALIASES` maps modern names **back** to `orissa`, `uttaranchal`,
  `nctofdelhi` — i.e. the file uses pre-rename Census 2011 state names
- 594 districts is consistent with a Census 2011 district set

That points to a Census-2011-derived boundary set, of which the widely used open
one is **DataMeet's** — but do not write that down until it is confirmed against
whatever file was actually passed to `--geojson`.

**Why it matters beyond tidiness:** DataMeet publishes under **ODbL**, which is
share-alike. `OWNERSHIP.md` currently claims **CC-BY-4.0** across docs, schema and
data. If the boundary file is ODbL, that blanket claim is wrong for this layer and
needs carving out.

**Actions:**
1. Identify the actual file passed to `--geojson` and its upstream.
2. Create `docs/BOUNDARY-ATTRIBUTION.md` on the model of the other attribution docs.
3. Reconcile with `OWNERSHIP.md` — per-layer licensing, not one blanket claim.
4. Consider preserving a `source` property through the fixture generator so
   provenance travels with the data instead of being stripped.

**Done when:** every real layer has a named source and a licence, and
`OWNERSHIP.md` matches all of them.

---

## R4 — Write down the NFHS extraction licence argument

**15 minutes.**

`docs/DATA-RECONCILIATION.md` lists the primary extraction
(`SaiSiddhardhaKalla/NFHS`) with licence **"none stated"**. No licence means all
rights reserved by default, which looks like an unresolved risk sitting in a table.

The defence is genuinely sound and already half-written in that file — the values
are Government of India statistics, facts are not copyrightable, and the
repositories are *transport, not authorship*. The problem is that this is
currently implied rather than argued.

**Fix:** state the reasoning explicitly, note that the same values were obtained
from a second CC-BY-4.0 extraction and matched to the decimal (which is itself
evidence neither repo is the origin of the data), and record that the canonical
source is `rchiips.org` — unreachable at build time, with the 404 and TLS failure
already documented.

**Done when:** a reviewer reading the licence table finds an argument, not a gap.

---

## R5 — Load real district population

**1.5 hours. Removes the last placeholder from a scored output.**

`generate_console_fixtures.py:271`:

```python
population = int(180_000 + rnd("pop", code) * 3_400_000)   # hash, not data
```

**Source:** Census of India 2011 district-level population, published on
`data.gov.in` under the **Government Open Data Licence – India (OGDL)**. It is the
natural match, because the boundary set is already Census-2011 vintage — district
codes should join without fuzzy matching.

Doing this makes `population_affected` a real derived figure and retires R2's
caveat rather than merely disclosing it. It also strengthens Impact Potential,
where per-dossier population estimates are an explicit line in `SPEC.md §12`.

**Done when:** no hash-derived number reaches a dossier, and README's
"what is real" table moves population from *Not loaded* to *Real*.

---

## R6 — Real Roads & Transport deficit

**2–3 hours. Medium risk — data shape unverified.**

Roads & Transport is 1 of 5 sectors and currently carries no deficit values,
because NFHS is a health survey with no road-connectivity equivalent. This is
disclosed honestly in the interface, which is the right call — but it is also the
only sector where the map is empty.

**Candidate source:** PMGSY (Pradhan Mantri Gram Sadak Yojana) habitation
connectivity, published by the Ministry of Rural Development on `data.gov.in`
under OGDL. `adapters/in/sectors.yaml:33` already names the intended indicator —
*"Rural habitations without all-weather road connectivity"* — which is exactly
what PMGSY reports.

Risk is real: district-level aggregation and code matching are unverified, and
this could consume an afternoon and produce nothing. **Attempt only after R0–R4
are done**, and time-box it.

**Done when:** 5 of 5 sectors carry real deficit values, or the attempt is
documented as a dead end with the reason — which is itself a defensible artefact.

---

## R7 — `CIVOS-ZA` adapter on real data

**6–10 hours realistically. The largest single scoring gap: Cross-Border 20%.**

`plan.md` budgeted 120 minutes for this. That estimate assumes config authoring
only; it does not cover sourcing, cleaning and reconciling a second country's
real deprivation data, which is where the time actually goes.

`SPEC.md §12` requires *"live country switch on real second-country data"* —
config files alone will not satisfy it, and the lint (`lint_country_literals.py`)
already proves the core is country-agnostic, so the architectural half of the
claim is done and evidenced.

**Candidate sources for South Africa:**
- **Statistics South Africa** (Census 2011 / Community Survey 2016) — municipal
  and district-level household access to water, sanitation and electricity, which
  maps closely onto three of the five CIVOS sectors
- Municipal boundary geometry from the **Municipal Demarcation Board**

**The honest decision this plan cannot make for you:** 20% of the score against
6–10 hours of a remaining ~25, with the demo re-cut from R1 also competing for
that time. The realistic options are:

1. **Full ZA** — highest score, highest risk of arriving half-finished.
2. **Three sectors, one province, labelled** — a real switch on real data with
   scope stated on screen. Probably captures most of the 20% and is far safer.
3. **Skip and relabel** (R0 option two) — protects integrity, forfeits the 20%.

I would take **option 2**. A narrow-but-real switch, honestly scoped, is worth
more than a broad one that breaks on stage — and it is consistent with how the
rest of this project already handles partial data.

---

## Cut list — the order things get dropped

If time runs out, drop from the bottom:

1. R6 (Roads deficit) — the gap is already disclosed
2. R5 (real population) — R2 makes the placeholder honest at 1/6 the cost
3. R7 scope — degrade from option 1 → option 2 → option 3
4. R3 step 4 (provenance in the fixture generator) — the doc is what matters

**Never cut:** R0, R1, R2, R4. Together they are about 4 hours and they protect
the one thing this submission cannot afford to lose — that its numbers mean what
they say.

---

## Suggested sequencing

| Day | Focus |
|---|---|
| **17 Aug (today)** | R0 (15 min), R2 (15 min), R4 (15 min) — all three integrity quick wins closed same day |
| **18 Aug** | R1 — connectivity, regeneration, re-shoot screenshots |
| **19 Aug** | R3 + R5, then start R7 sourcing |
| **20 Aug** | R7 build |
| **21 Aug** | Submission assets, deck, demo recording |
| **22 Aug** | Submit. R6 only if genuinely idle |

The 23rd and 24th remain buffer, per `plan.md`. Treat them as if they do not exist.

---

## Open questions this plan does not answer

1. **Is the 1:40 demo narration tied to named districts or to the mechanism?**
   If named, R1 forces a re-cut and that cost belongs in the R1 estimate.
2. **What file was passed to `--geojson`?** R3 cannot complete without it.
3. **Which ZA option?** R7 cannot start without that decision.
