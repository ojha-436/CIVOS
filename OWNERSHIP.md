# Ownership

DPGA indicator 3 asks who owns a digital public good. Answering it vaguely is a
common way to fail an otherwise sound submission, so this file is explicit.

## Copyright holder

Prince Kumar Ojha — sole author and copyright holder of all original code,
documentation and configuration in this repository.

Contact: prince.kumar@premnathrail.com

## Licensing

| Asset | Licence |
|---|---|
| Source code (`core/`, `api/`, `console/`, `scripts/`, `adapters/`) | Apache-2.0 — see [LICENSE](LICENSE) |
| Documentation (`docs/`, `*.md`) | CC-BY-4.0 |
| Schema, configuration and the generated reference dataset | CC-BY-4.0 |
| **Third-party data redistributed in this repository** | **Under its own upstream licence — see the table below.** Not covered by the CC-BY-4.0 above |

### Third-party data licences

Stated per layer rather than as one blanket claim, because a blanket claim over
data the project did not author is wrong even when the licences happen to be
compatible.

| Layer | Upstream | Licence | Redistribution |
|---|---|---|---|
| District boundaries — `console/public/data/districts.geojson` | [DataMeet India community](https://github.com/datameet/maps), Census 2011 districts | **CC-BY 4.0** | Permitted with attribution — see [docs/BOUNDARY-ATTRIBUTION.md](docs/BOUNDARY-ATTRIBUTION.md) |
| Sector deficit indicators | NFHS-5 2019-21 (IIPS / MoHFW, Government of India) | Government statistics — reasoning in [docs/DATA-RECONCILIATION.md](docs/DATA-RECONCILIATION.md) | Facts, not copyrightable expression |
| Evidence photographs | Wikimedia Commons contributors | **CC-BY / CC0**, per image | Permitted with attribution — see [docs/IMAGE-ATTRIBUTION.md](docs/IMAGE-ATTRIBUTION.md) |
| Typefaces — `console/app/fonts/` | IBM; Rodrigo Fuenzalida & Iván Reyes Ramírez | **SIL OFL 1.1** | Permitted — see [docs/FONT-ATTRIBUTION.md](docs/FONT-ATTRIBUTION.md) |

The boundary layer was previously derived from a source the code indicates was
**GADM**, which prohibits redistribution without prior permission. Publishing a
derived copy in this repository was therefore a licensing conflict, and it is
recorded here rather than quietly corrected. It was replaced on 17 Aug 2026 with
the DataMeet Census-2011 set, which permits redistribution under CC-BY 4.0 and is
reproducible via `scripts/build_boundaries.py`.

Both are DPGA-approved open licences. The split is deliberate: code that a
ministry may need to modify and redistribute is permissively licensed with an
explicit patent grant, while documentation and data carry an attribution
requirement so provenance survives reuse.

## Third-party assets

| Asset | Provenance |
|---|---|
| Evidence photographs | Real, openly-licensed images. Every one attributed individually in [docs/IMAGE-ATTRIBUTION.md](docs/IMAGE-ATTRIBUTION.md). None generated. |
| Official deficit indicators | Public government datasets, cited with source and year in the UI and in each dossier. |
| Administrative boundaries | DataMeet Census-2011 district boundaries, CC-BY 4.0, attributed in [docs/BOUNDARY-ATTRIBUTION.md](docs/BOUNDARY-ATTRIBUTION.md) and rebuildable with `scripts/build_boundaries.py`. |
| Synthetic citizen signals | Generated for this project. Labelled as synthetic in the interface itself and released under CC-BY-4.0 as part of the public good. |

## Ownership of a deployment's data

Nothing in this repository claims ownership of data produced by a deployment. A
government running CIVOS owns the citizen signals it collects. The platform is
built so that this is structurally true rather than merely promised: the public
API returns aggregates only, k-anonymity suppression happens inside the
warehouse, original audio and photographs are destroyed after extraction, and no
citizen coordinate is ever persisted.
