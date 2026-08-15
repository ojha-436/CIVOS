# Deficit layer — provenance and reconciliation

Built 2026-08-15 07:16 UTC. Regenerate with `uv run python scripts/build_deficit_layer.py`.

## Source

National Family Health Survey 2019-21 (NFHS-5), district factsheets. International Institute for Population Sciences (IIPS) and Ministry of Health and Family Welfare, Government of India.

`rchiips.org`, which hosts the official factsheet PDFs, currently returns 404 and presents an invalid TLS certificate, so the PDFs could not be retrieved at source. Two independent community extractions of those same PDFs were used instead, and **cross-validated against each other** rather than trusted.

| Extraction | Districts | Licence | Role |
|---|---|---|---|
| `SaiSiddhardhaKalla/NFHS` | 644 | none stated | primary — carries census district codes |
| `pratapvardhan/NFHS-5` | 341 | CC-BY-4.0 | independent cross-check |

The values themselves are Government of India statistics and are attributed to NFHS-5 above; the repositories are transport, not authorship.

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

## Still placeholder

- **District population** — no census population loaded; the population-affected figure in dossiers remains a placeholder.
- **Roads & Transport deficit** — see above.
- **Citizen signals** — synthetic by design, and labelled as such in the interface.
