# Deficit layer — provenance and reconciliation

Built 2026-08-18 05:55 UTC. Regenerate with `uv run python scripts/build_deficit_layer.py`.

## Source

National Family Health Survey 2019-21 (NFHS-5), district factsheets. International Institute for Population Sciences (IIPS) and Ministry of Health and Family Welfare, Government of India.

`rchiips.org`, which hosts the official factsheet PDFs, currently returns 404 and presents an invalid TLS certificate, so the PDFs could not be retrieved at source. Two independent community extractions of those same PDFs were used instead, and **cross-validated against each other** rather than trusted.

| Extraction | Districts | Licence | Role |
|---|---|---|---|
| `SaiSiddhardhaKalla/NFHS` | 644 | none stated | primary — carries census district codes |
| `pratapvardhan/NFHS-5` | 341 | CC-BY-4.0 | independent cross-check |

The values themselves are Government of India statistics and are attributed to NFHS-5 above; the repositories are transport, not authorship.

### On the "none stated" licence

The primary extraction states no licence, which by default means all rights reserved. That is worth addressing directly rather than leaving as a blank cell in a table, because it reads as an unexamined risk and it is not one.

1. **The figures are facts, not expression.** A district's measured percentage of households without piped water is a Government of India survey statistic. Facts are not copyrightable; only a creative arrangement of them is, and a factsheet transcription is the opposite of a creative arrangement.
2. **Neither repository is the origin.** The canonical source is `rchiips.org` (IIPS / MoHFW), recorded above together with the exact 404 and TLS failure that prevented retrieval at source.
3. **Two independent extractions agree to the decimal.** The cross-validation below is not only a quality check — it is evidence that neither repository *authored* anything. Two parties cannot independently produce identical creative work from the same PDFs; they can only both transcribe the same facts.
4. **A CC-BY-4.0 route to the same values exists.** The cross-check extraction is CC-BY-4.0 and covers 341 districts, independently licensing the same figures where it overlaps.

CIVOS therefore attributes the data to **NFHS-5 (IIPS / MoHFW, Government of India)** and treats both repositories as retrieval mechanisms. If IIPS restores `rchiips.org`, this script should be pointed at the source PDFs and this section reduced to a footnote.

This is a reasoned position, not legal advice. A ministry deploying CIVOS in production should retrieve the factsheets from IIPS directly, which is correct practice regardless of licensing.

## Cross-validation

Both extractions cover **275 districts** in common.

| Indicator | Compared | Identical | Max difference |
|---|---|---|---|
| `pct_households_no_improved_water` | 274 | 274 (100.0%) | 0.0 |
| `pct_households_no_improved_sanitation` | 274 | 274 (100.0%) | 0.0 |
| `pct_households_no_electricity` | 274 | 274 (100.0%) | 0.0 |
| `pct_births_non_institutional` | 274 | 274 (100.0%) | 0.0 |
| `pct_females_never_attended_school` | 274 | 274 (100.0%) | 0.0 |

Two independent PDF extractions agreeing to the decimal across every indicator is good evidence that neither mangled the source. This check re-runs on every build.

## Reconciliation against the boundary set

**639 of 641 rendered districts (99.7%)** carry real NFHS-5 values.

| Method | Districts |
|---|---|
| `census_code` | 628 |
| `exact_state_district` | 10 |
| `excluded_sentinel` | 1 |
| `fuzzy_within_state` | 1 |

The boundary file is 2011-era, so it predates **Telangana** (created 2014) and **Ladakh** (2019), and many districts have been split or renamed since. Those states are aliased back to their parent for matching. Districts that still do not match are listed below, **excluded from the ranking, and rendered grey** — they are not given an invented value.

### Boundary districts with no NFHS-5 row (2)

Data Not Available (Jammu & Kashmir), Saraikela-kharsawan (Jharkhand)

### NFHS-5 districts with no boundary (16)

Data Not Available (Jammu & Kashmir), East Jaintia Hills (Meghalaya), North Garo Hills (Meghalaya), Theni (Tamil Nadu), Adilabad (Telangana), Hyderabad (Telangana), Karimnagar (Telangana), Khammam (Telangana), Mahabubnagar (Telangana), Medak (Telangana), Nalgonda (Telangana), Nizamabad (Telangana), Ranga Reddy (Telangana), Warangal Rural (Telangana), Warangal Urban (Telangana), Paschim Medinipur (West Bengal)

## Sector coverage

| Sector | Indicator | Status |
|---|---|---|
| Water & Sanitation | Households without an improved drinking water source | ✅ real, NFHS-5 2021 |
| Roads & Transport | — | ❌ **no real indicator loaded** |
| Electricity | Households without an electricity connection | ✅ real, NFHS-5 2021 |
| Health Facilities | Births not delivered in a health facility | ✅ real, NFHS-5 2021 |
| Education | Females age 6+ who never attended school | ✅ real, NFHS-5 2021 |

**roads_transport** has no NFHS-5 equivalent — road connectivity is not a health-survey indicator. It needs PMGSY habitation-connectivity data, which is not loaded. The sector is left visibly empty rather than filled with a proxy: plan.md's rule is that two real sectors beat five mangled ones.

## Deficit direction

NFHS-5 reports **coverage** ("% with an improved water source"). The engine needs **deprivation**, so `deficit_pct = 100 − coverage_pct`. Stated explicitly because getting it backwards would invert the entire product.

## Participation capacity — who can actually file a complaint

The synthetic corpus applies a participation bias of `deficit × connectivity^1.6`. The shape is the whole argument — real deprivation multiplied by ability-to-report is what makes the Silent Need quadrant populate. But `connectivity` used to be `sha256(district_code)`: a hash with no real-world meaning, which meant the specific set of districts classified Silent Need was **arbitrary**. "Why is this district silent?" had no answer.

It is now built from two real NFHS-5 values on the same districts:

| Input | Proxies | Weight |
|---|---|---|
| Women with 10 or more years of schooling (%) | literacy and the agency to navigate a grievance process | 0.6 |
| Population living in households with electricity (%) | household infrastructure a phone depends on | 0.4 |

Composite raw range **39.0 – 92.8**, min-max normalised to `[0,1]`. **639 of 641 districts** carry a capacity value.

**The weighting is a judgement, not a measurement.** It is stated here so it can be argued with, on the same principle that exposes the `w1..w5` scoring weights as sliders in the console rather than burying them.

**Districts missing either input get no capacity value and are excluded — not imputed.** A district a health survey failed to reach is precisely the kind of district most likely to be genuinely low-capacity, so filling it with the median would erase the signal the product exists to find.

Written to `data/fact_participation_capacity.csv`.

## Still placeholder

- **District population** — no census population loaded. The population-affected figure in dossiers is derived from a placeholder, is labelled as such in the interface, and the dossier prompt now requires the model to say so in prose as well.
- **Roads & Transport deficit** — see above.
- **Citizen signals** — synthetic by design, and labelled as such in the interface.

No longer placeholder: **participation / connectivity**, previously a hash — see above.
