# Roads & Transport — the indicator, and the six sources rejected first

**Status as of 18 Aug 2026: LOADED, with a disclosed limitation.**

Indicator: **villages without a black-topped (pucca) road**, Census 2011 Village
Directory (Ministry of Home Affairs / Office of the Registrar General), **617
districts**, national median **27.7%**.

This document is kept in full — including everything that was rejected — because
the rejections are the reasoning. Six sources were checked and two candidate
indicators were discarded on evidence before this one was accepted, and the
accepted one ships with a caveat on screen rather than a clean claim.

**The limitation, stated first.** Census enumerators recorded this field
inconsistently between states. Within-state comparison is sound. Cross-state
comparison is weaker than for the four NFHS-5 sectors: Kerala reports 0.0% across
all 14 districts, which is credible for a state with near-universal paved access,
but **Jharkhand's 1.7% median is not credible** for a state where PMGSY runs
priority programmes, and Ballia and Mau in Uttar Pradesh both sit at 100%. That
caveat is carried in `adapters/in/sectors.yaml`, shown permanently in the console's
calibration strip whenever the sector is active, and stated in every dossier that
cites the sector.

## What the sector asks for

`adapters/in/sectors.yaml` specifies:

```yaml
- key: roads_transport
  indicator:
    primary: pct_habitations_unconnected
    label: Rural habitations without all-weather road connectivity
    source: PMGSY / district statistics
```

Four of five sectors carry a real NFHS-5 value. This one cannot: NFHS is a health
survey and road connectivity has no health-survey equivalent.

## What was checked

### 1. NFHS-5 — no equivalent indicator

All **105** indicators in the primary extraction were scanned for the terms *road,
transport, distance, travel, access, reach, vehicle, connect, market, bus*. **Zero
matches.** Expected of a health survey, and confirmed rather than assumed.

### 2. PMGSY GeoSadak open data — the right source, wrong contents

The Ministry of Rural Development publishes the PMGSY national GIS release at
<https://geosadak-pmgsy.nic.in/OpenData>, mirrored at
[`datameet/pmgsy-geosadak`](https://github.com/datameet/pmgsy-geosadak) under the
**Government Open Data License – India** (explicitly redistribution-friendly and
CC-BY compatible, so licensing was not the obstacle).

Two layers were downloaded and their attributes inspected:

**`Habitation/<state>.zip`** — 39,382 habitations for Assam alone:

```
fields: HAB_ID, STATE_ID, DISTRICT_I, BLOCK_ID, HAB_NAME, TOT_POPULA
```

**`Road_DRRP/<state>.zip`** — 40,712 road segments for Assam:

```
fields: ER_ID, STATE_ID, BLOCK_ID, DISTRICT_I, DRRP_ROAD_, RoadCatego, RoadName, RoadOwner
RoadCatego values: RR(VR) 37035 · RR(TRACK) 1879 · RR(ODR) 1032 · MDR 322 · NH 212 · SH 197
```

**There is no connectivity status field in either layer.** The habitation layer is
an inventory with population; the road layer carries road *category* (village road,
track, other district road, major district road, state and national highway) but
no condition, no all-weather flag, and no link saying which habitations are served.

`MasterData.xls` is a state/district/block ID lookup table only.

**`Proposals/<state>.zip`** was also checked, in case it carried a completion status:

```
fields: MRL_ID, STATE_ID, DISTRICT_I, BLOCK_ID, CN_CODE, PROPOSED_L,
        WORK_NAME, IMS_YEAR, IMS_BATCH
```

It carries proposed road *length* for a single batch year (509 records for Assam, all
`IMS_YEAR = 2020`) and no completion or connectivity status. Even as a proxy it would
be wrong here: proposal volume reflects **administrative activity** as much as need,
so a district that files more proposals would score as more deprived. That is the
same participation bias CIVOS exists to correct, and importing it into the deficit
axis would make the engine circular.

### 3. Road category — considered and rejected

`RoadCatego` distinguishes `RR(TRACK)` from proper road classes, so "% of the rural
network that is only a track" looks usable at first glance.

Rejected because it is **biased by recording completeness**. The DRRP is a survey of
what has been mapped, and mapping coverage varies by state and district. A district
with a well-surveyed network that includes some tracks would score worse than one
whose network is barely recorded at all. Ranking districts by an artefact of survey
completeness — inside a product whose whole thesis is that measurement bias distorts
funding — would be the most ironic error available.

### 4. data.gov.in — credentialed, and that is the only real blocker

```
GET https://api.data.gov.in/resource/<id>?format=json
{"error": "Authorization field missing"}
```

Every relevant resource needs an API key. Registration is free, but a key cannot be
committed to a public repository, so this route is open to a **deployment** and not
to this repository as it stands. It is the shortest path to closing the gap — see
below.

### 5. The indicator has now been located — and named

The Census 2011 **Village Directory** does carry it. Confirmed via the SHRUG
metadata, which documents the Village Directory road fields:

| Variable | Meaning |
|---|---|
| `pc11_vd_rd_all_wthr` | **All Weather Road** ← exactly what `sectors.yaml` asks for |
| `pc11_vd_rd_p_btr` | Black-topped (pucca) road |
| `pc11_vd_rd_k_grav` | Gravel (kuchha) road |
| `pc11_vd_rd_nhw` / `_shw` / `_mdr` / `_odr` | highway and district-road classes |

Aggregations exist at village, subdistrict, **district** and constituency level, so
no habitation-level spatial work is needed — the figure is a straight count of
villages with all-weather road access over total villages per district.

So the sector is not blocked by the indicator not existing. It is blocked by
licensing and credentials, below.

### 6. SHRUG — the convenient mirror, rejected on licence

[SHRUG](https://www.devdatalab.org/shrug) (Development Data Lab) republishes the
Village Directory with clean district aggregations and would make this a one-hour
job. It is licensed **CC BY-NC-SA 4.0**.

**Rejected.** Two independent problems:

- **NC (non-commercial)** is not an open licence under the Open Definition, and
  DPGA indicator 2 requires an *approved open licence*. CIVOS argues for itself as
  a Digital Public Good; importing an NC-restricted layer would break that claim
  and would restrict what a ministry could do with the result.
- **SA (share-alike)** would force the derived data to carry BY-NC-SA, propagating
  the restriction into `OWNERSHIP.md`'s CC-BY-4.0 data claim.

This is the **same class of error as the GADM boundary layer**, which was found and
replaced on the same day. Fixing one licence conflict and then introducing another
would be worse than leaving the sector grey.

The underlying figures are Government of India census statistics and are openly
licensed *at source*. It is only this particular republication that is restricted.

### 7. The Census indicator was LOADED, tested, and rejected on evidence

The catalogue turned out to need no API key at all. data.gov.in's own front end
calls a public backend — `/backend/dmspublic/v1/resources?filters[catalog_reference]=534901`
— which enumerates all **631** district resources, and each record's `datafile_url`
points straight at `censusindia.gov.in`. So the full Village Directory was
downloaded and aggregated: **612 of 641 districts**, joined by exact all-India
census district code (`censuscode`, now carried in the boundary properties).

The aggregation is correct. Darjiling: 306 villages without an all-weather road out
of 634 with a recorded status = **48.3%**, matching a hand-check of the raw file.

**And the indicator still cannot be used.** The `All Weather Road (Status A(1)/NA(2))`
field is not coded comparably across states:

| State | Districts | Median deficit |
|---|---|---|
| Kerala | 14 | **all exactly 0.0%** |
| Haryana | 21 | **all exactly 0.0%** |
| Andhra Pradesh | 18 | **all exactly 0.0%** |
| Delhi · Tripura · Puducherry · Chandigarh · Daman & Diu | 13 | all exactly 0.0% |
| Rajasthan | 33 | **73.0%** (minimum 47.0%) |
| Uttarakhand | 13 | 69.3% |

At village level, the same split:

| District | status 1 (has road) | status 2 (none) |
|---|---|---|
| Mau, Uttar Pradesh | **3** | **1,496** |
| Kupwara, Jammu & Kashmir | **351** | **0** |
| Darjiling, West Bengal | 328 | 306 |

Kerala does have good rural connectivity — but *exactly zero* villages lacking an
all-weather road across all fourteen of its districts, and Haryana 21 of 21, and
Andhra Pradesh 18 of 18, is an **enumeration convention**, not a physical fact. Two
enumerators applied `A(1)/NA(2)` in opposite directions.

CIVOS ranks districts **nationally** against per-sector medians. Loading this would
score every Kerala, Haryana, Andhra Pradesh and Delhi district as having perfect
roads and every Rajasthan district as catastrophic — a state-level artefact driving
a national funding ranking. That is the same failure mode as §3, and the same
failure mode the entire product exists to correct.

**What was kept.** `scripts/build_roads_layer.py` and
`data/fact_roads_deficit.csv` remain in the repository, because the finding is worth
more than the file. Consumption is gated behind an explicit `--with-roads` flag on
`scripts/build_deficit_layer.py`, **off by default**, so the sector cannot quietly
acquire a bad indicator. If a comparably-coded column or source appears, this
becomes a one-flag change.

Two incidental fixes came out of it: the district CSVs are **latin-1**, not UTF-8
(19 files failed to decode before this was found), and `censusindia.gov.in` serves
an **incomplete certificate chain** that Python rejects even with `certifi`, so the
downloader shells out to `curl` — which keeps verification ON rather than disabling
it.

## Why it was not derived anyway

The connectivity figure *could* be approximated: buffer every road that is not
`RR(TRACK)`, count habitations falling outside all buffers, aggregate by district.

That was rejected, for a reason that matters more than the missing sector:

**every number CIVOS displays is meant to trace to a citable official source.** A
spatially-derived connectivity percentage would be *our* estimate wearing the
costume of an official statistic — sensitive to an arbitrary buffer distance, to
road geometry completeness, and to habitation point placement, with no published
figure to validate against. It would be the single least defensible number in the
product, sitting in the same table as NFHS-5 values that are cross-validated to the
decimal.

`plan.md` already states the rule this follows: *two real sectors beat five mangled
ones.*

## What would actually close the gap

1. **Census 2011 Village Amenities on `data.gov.in`** — the authoritative source
   for the fields in §5, published by the **Ministry of Home Affairs / Office of the
   Registrar General** under the **Open Government License – India**, which *is*
   compatible with this project's licensing. This is the right answer. It needs a
   free `data.gov.in` API key.
2. **PMGSY OMMS habitation connectivity status** — the Online Management and
   Monitoring System tracks connected/unconnected per habitation. Not in the
   GeoSadak open release; would need a data request to the Ministry of Rural
   Development.

Both are viable for a real deployment. Neither is reachable from a public repository
with no credentials, which is the constraint this build works under.

**The shortest path is a free data.gov.in API key.** Registration takes a couple of
minutes at <https://data.gov.in/user/register>. The key would live in `.env`
alongside `TELEGRAM_BOT_TOKEN` — gitignored, never committed — and read as
`CIVOS_DATAGOV_API_KEY`, exactly the pattern every other credential in this project
already follows. With it, `pct_habitations_unconnected` becomes loadable and the
sector lights up with no change to `sectors.yaml`, the scoring code, or the console.

Until then the sector stays honestly empty. That is the correct state: an empty
sector with a documented reason costs one grey column, whereas a fabricated
indicator would put a number nobody can defend next to NFHS-5 values that are
cross-validated to the decimal.

## How the gap presents in the product

Not hidden anywhere:

- the sector renders with every district grey and is labelled **no official data**
- those district-sectors are excluded from the ranking rather than scored on a zero
- the calibration strip counts them permanently on screen
- `docs/DATA-RECONCILIATION.md` marks the sector ❌ with the reason
- the README provenance table lists it as **Absent**

A ministry deploying CIVOS with OMMS access fills `pct_habitations_unconnected` and
the sector lights up with no code change — the indicator name is already in
`sectors.yaml` waiting for it.
