# District boundary attribution

Built 2026-08-17 10:29 UTC. Regenerate with `uv run --with pyshp python scripts/build_boundaries.py`.

## Source

**DataMeet India community — Census 2011 district boundaries**, licensed **CC-BY 4.0**.

<https://github.com/datameet/maps/tree/master/Districts/Census_2011>

> District boundaries by the [DataMeet India community](http://datameet.org/)
> ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)).

The upstream file is a shapefile (`2011_Dist.shp`, ~10 MB, already in WGS 84).
`scripts/build_boundaries.py` converts it to GeoJSON, simplifies it for web
rendering, and writes `console/public/data/districts.geojson`.

| | Value |
|---|---|
| Districts | 641 |
| Simplification | `4%` retained vertices, topology preserved |
| Rendered size | 823 KB |
| Coordinate precision | 4 decimal places (~11 m) |

## Why this source, and what it replaced

The previous boundary file came from an unrecorded 33 MB "public GeoJSON" that the
code strongly indicates was **GADM** — `scripts/generate_console_fixtures.py` read
`NAME_1`/`NAME_2`, GADM's property convention, and the deficit builder aliased
state names back to GADM 2.x spellings (`orissa`, `uttaranchal`, `nctofdelhi`).

**GADM prohibits redistribution without prior permission.** CIVOS publishes a
derived copy of the geometry in a public repository, so that was a licensing
conflict as well as an unattributed layer — and it undercut the Digital Public Good
argument the project makes about itself.

The replacement is better on the merits, not only on licensing:

| | GADM (previous) | DataMeet (current) |
|---|---|---|
| Licence | redistribution prohibited | **CC-BY 4.0** |
| Districts | 594 | **641** |
| Census codes in properties | absent | **`st_cen_cd` + `dt_cen_cd`** |
| NFHS-5 reconciliation | 90.4%, fuzzy name matching | **exact census-code join** |
| State naming | 2011-era | modern |

Carrying the census codes is the substantive gain. NFHS-5's own extraction carries
the same `ST_CEN_CD` / `DT_CEN_CD` pair, so districts join on integers rather than
on fuzzy-matched English names. That removes a class of silent error the project
had already been bitten by once: the earlier name matcher married Sikkim's **East**
district to Delhi's **East**, which would have painted one district's deprivation
onto another with nothing on screen to indicate it (see `memory.md`).

## Properties carried

```json
{"code": "IN-OR-dhenkanal", "name": "Dhenkanal", "state": "Odisha",
 "st_cen_cd": 21, "dt_cen_cd": 15}
```

Codes stay in the human-readable `IN-<ISO 3166-2 subdivision>-<slug>` form, because
that string is shown in the console drilldown and in dossiers where it tells a
reader something. Census codes travel alongside rather than replacing it. Spelling
variants across sources (`Odisha`/`Orissa`, `&`/`and`, the upstream `Arunanchal`
typo) are aliased to the same subdivision code in `scripts/india_admin.py`, so a
change of boundary source does not silently renumber districts.
