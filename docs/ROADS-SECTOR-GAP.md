# Roads & Transport — why the sector is empty

**Investigated 17 Aug 2026. Conclusion: the indicator CIVOS wants does not exist in
any open dataset that could be found, and deriving it ourselves would be worse than
leaving the gap.**

Recorded because a disclosed gap with a reason behind it is evidence of judgement,
whereas an undisclosed one is just a hole.

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

1. **PMGSY OMMS habitation connectivity status** — the Online Management and
   Monitoring System tracks connected/unconnected status per habitation. Not part
   of the GeoSadak open release; would need a data request to the Ministry of Rural
   Development, or an API key on `data.gov.in`.
2. **Census 2011 Village Amenities (Directory)** — records approach-road type per
   village and would aggregate cleanly to district level. Behind a `data.gov.in`
   API key, which cannot be committed to a public repository.

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
