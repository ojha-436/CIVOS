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

Both are DPGA-approved open licences. The split is deliberate: code that a
ministry may need to modify and redistribute is permissively licensed with an
explicit patent grant, while documentation and data carry an attribution
requirement so provenance survives reuse.

## Third-party assets

| Asset | Provenance |
|---|---|
| Evidence photographs | Real, openly-licensed images. Every one attributed individually in [docs/IMAGE-ATTRIBUTION.md](docs/IMAGE-ATTRIBUTION.md). None generated. |
| Official deficit indicators | Public government datasets, cited with source and year in the UI and in each dossier. |
| Administrative boundaries | Public boundary data, cited in the country adapter. |
| Synthetic citizen signals | Generated for this project. Labelled as synthetic in the interface itself and released under CC-BY-4.0 as part of the public good. |

## Ownership of a deployment's data

Nothing in this repository claims ownership of data produced by a deployment. A
government running CIVOS owns the citizen signals it collects. The platform is
built so that this is structurally true rather than merely promised: the public
API returns aggregates only, k-anonymity suppression happens inside the
warehouse, original audio and photographs are destroyed after extraction, and no
citizen coordinate is ever persisted.
