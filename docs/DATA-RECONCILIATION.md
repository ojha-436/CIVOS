# Deficit layer — provenance and reconciliation

Built 2026-08-17 09:55 UTC. Regenerate with `uv run python scripts/build_deficit_layer.py`.

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

**537 of 594 rendered districts (90.4%)** carry real NFHS-5 values.

| Method | Districts |
|---|---|
| `exact_state_district` | 510 |
| `fuzzy_within_state` | 27 |

The boundary file is 2011-era, so it predates **Telangana** (created 2014) and **Ladakh** (2019), and many districts have been split or renamed since. Those states are aliased back to their parent for matching. Districts that still do not match are listed below, **excluded from the ranking, and rendered grey** — they are not given an invented value.

### Boundary districts with no NFHS-5 row (57)

Andaman Islands (Andaman and Nicobar), Nicobar Islands (Andaman and Nicobar), Cuddapah (Andhra Pradesh), Nellore (Andhra Pradesh), Warangal (Andhra Pradesh), Upper Dibang Valley (Arunachal Pradesh), North Cachar Hills (Assam), Sibsagar (Assam), Bhabua (Bihar), Kanker (Chhattisgarh), Kawardha (Chhattisgarh), Dadra and Nagar Haveli (Dadra and Nagar Haveli), Daman (Daman and Diu), Junagadh (Daman and Diu), Delhi (Delhi), Sonepat (Haryana), Anantnag (Kashmir South) (Jammu and Kashmir), Bagdam (Jammu and Kashmir), Baramula (Kashmir North) (Jammu and Kashmir), Kupwara (Muzaffarabad) (Jammu and Kashmir), Ladakh (Leh) (Jammu and Kashmir), Rajauri (Jammu and Kashmir), Koderma (Jharkhand), Saraikela Kharsawan (Jharkhand), Bangalore Urban (Karnataka), Kavaratti (Lakshadweep), East Nimar (Madhya Pradesh), Narsinghpur (Madhya Pradesh), West Nimar (Madhya Pradesh), Garhchiroli (Maharashtra), Greater Bombay (Maharashtra), East Imphal (Manipur), West Imphal (Manipur), Jaintia Hills (Meghalaya), Boudh (Orissa), Deogarh (Orissa), Keonjhar (Orissa), Sonepur (Orissa), Nawan Shehar (Punjab), East (Sikkim), North Sikkim (Sikkim), South Sikkim (Sikkim), West Sikkim (Sikkim), Nilgiris (Tamil Nadu), Tirunelveli Kattabo (Tamil Nadu), Allahabad (Uttar Pradesh), Badaun (Uttar Pradesh), Hathras (Uttar Pradesh), Kanpur (Uttar Pradesh), Lakhimpur Kheri (Uttar Pradesh), Sant Ravi Das Nagar (Uttar Pradesh), Barddhaman (West Bengal), Darjiling (West Bengal), East Midnapore (West Bengal), North 24 Parganas (West Bengal), South 24 Parganas (West Bengal), West Midnapore (West Bengal)

### NFHS-5 districts with no boundary (107)

Nicobar (Andaman & Nicobar Island), North & Middle Andaman (Andaman & Nicobar Island), South Andaman (Andaman & Nicobar Island), Sri Potti Sriramulu Nellore (Andhra Pradesh), Y.S.R. (Andhra Pradesh), Anjaw (Arunachal Pradesh), Dibang Valley (Arunachal Pradesh), Baksa (Assam), Chirang (Assam), Dima Hasao (Assam), Kamrup Metropolitan (Assam), Sivasagar (Assam), Udalguri (Assam), Arwal (Bihar), Kaimur (Bhabua) (Bihar), Bijapur (Chhattisgarh), Kabeerdham (Chhattisgarh), Narayanpur (Chhattisgarh), Uttar Bastar Kanker (Chhattisgarh), Daman (Daman & Diu), Diu (Daman & Diu), Central (NCT of Delhi), East (NCT of Delhi), New Delhi (NCT of Delhi), North (NCT of Delhi), North East (NCT of Delhi), North West (NCT of Delhi), South (NCT of Delhi), South West (NCT of Delhi), West (NCT of Delhi), Dadra & Nagar Haveli (Dadra & Nagar Haveli), Tapi (Gujarat), Mewat (Haryana), Palwal (Haryana), Sonipat (Haryana), Khunti (Jharkhand), Kodarma (Jharkhand), Ramgarh (Jharkhand), Anantnag (Jammu & Kashmir), Badgam (Jammu & Kashmir), Bandipore (Jammu & Kashmir), Baramula (Jammu & Kashmir), Data Not Available (Jammu & Kashmir), Ganderbal (Jammu & Kashmir), Kishtwar (Jammu & Kashmir), Kulgam (Jammu & Kashmir), Kupwara (Jammu & Kashmir), Rajouri (Jammu & Kashmir), Ramban (Jammu & Kashmir), Reasi (Jammu & Kashmir), Samba (Jammu & Kashmir), Shupiyan (Jammu & Kashmir), Bangalore (Karnataka), Chikkaballapura (Karnataka), Ramanagara (Karnataka), Yadgir (Karnataka), Leh (Ladakh) (Ladakh), Lakshadweep (Lakshadweep), Gadchiroli (Maharashtra), Mumbai (Maharashtra), Mumbai Suburban (Maharashtra), East Jaintia Hills (Meghalaya), North Garo Hills (Meghalaya), West Jaintia Hills (Meghalaya), Imphal East (Manipur), Imphal West (Manipur), Alirajpur (Madhya Pradesh), Khandwa (East Nimar) (Madhya Pradesh), Khargone (West Nimar) (Madhya Pradesh), Narsimhapur (Madhya Pradesh), Singrauli (Madhya Pradesh), Kiphire (Nagaland), Longleng (Nagaland), Peren (Nagaland), Baudh (Odisha), Debagarh (Odisha), Kendujhar (Odisha), Subarnapur (Odisha), Barnala (Punjab), Sahibzada Ajit Singh Nagar (Punjab)

… and 27 more.

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

Composite raw range **39.0 – 92.8**, min-max normalised to `[0,1]`. **537 of 594 districts** carry a capacity value.

**The weighting is a judgement, not a measurement.** It is stated here so it can be argued with, on the same principle that exposes the `w1..w5` scoring weights as sliders in the console rather than burying them.

**Districts missing either input get no capacity value and are excluded — not imputed.** A district a health survey failed to reach is precisely the kind of district most likely to be genuinely low-capacity, so filling it with the median would erase the signal the product exists to find.

Written to `data/fact_participation_capacity.csv`.

## Still placeholder

- **District population** — no census population loaded. The population-affected figure in dossiers is derived from a placeholder, is labelled as such in the interface, and the dossier prompt now requires the model to say so in prose as well.
- **Roads & Transport deficit** — see above.
- **Citizen signals** — synthetic by design, and labelled as such in the interface.

No longer placeholder: **participation / connectivity**, previously a hash — see above.
