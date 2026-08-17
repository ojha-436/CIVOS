# Font attribution

The three typefaces used by the CIVOS console, citizen intake and landing page
are **vendored into the repository** at `console/app/fonts/` rather than fetched
from Google Fonts at build time.

## Why they are vendored

On **2026-08-17** a Cloud Build deploy of `civos-console` failed with 18
`Module not found` errors. The cause was upstream: Google Fonts had rotated the
IBM Plex Sans file hashes, and the CSS it was still serving to Next's build-time
fetcher referenced `woff2` URLs that had begun returning **404**.

```
Received response with status 404 when requesting
https://fonts.gstatic.com/s/ibmplexsans/v23/zYXZKVElMYYaJe8bpLHnCwDKr932-…woff2
                                             ^ requested — 404
https://fonts.gstatic.com/s/ibmplexsans/v23/zYXzKVElMYYaJe8bpLHnCwDKr932-…woff2
                                             ^ advertised today — 200
```

Local builds continued to pass, because `.next/` still held the previously
downloaded files. The break was therefore invisible outside CI — the worst shape
a build dependency can have.

Beyond the immediate failure, `next/font/google` made **a live network fetch a
prerequisite of compiling the project**. For something claiming to be a Digital
Public Good that is a real defect: a ministry building CIVOS on a restricted or
air-gapped network could not have compiled it at all. Vendoring makes the build
reproducible, offline-capable, and immune to upstream CDN changes.

## Licences

All three families are licensed **SIL Open Font License 1.1**, which expressly
permits redistribution — including bundled inside another work — provided the
licence travels with the fonts and they are not sold on their own.

| File | Family | Weight | Copyright |
|---|---|---|---|
| `InstrumentSerif-Regular.woff2` | Instrument Serif | 400 | © Rodrigo Fuenzalida & Iván Reyes Ramírez |
| `IBMPlexSans-Regular.woff2` | IBM Plex Sans | 400 | © IBM Corp. |
| `IBMPlexSans-Medium.woff2` | IBM Plex Sans | 500 | © IBM Corp. |
| `IBMPlexSans-SemiBold.woff2` | IBM Plex Sans | 600 | © IBM Corp. |
| `IBMPlexMono-Regular.woff2` | IBM Plex Mono | 400 | © IBM Corp. |
| `IBMPlexMono-Medium.woff2` | IBM Plex Mono | 500 | © IBM Corp. |

Full licence text: `console/app/fonts/OFL.txt`

Upstream sources:
- Instrument Serif — <https://github.com/Instrument/instrument-serif>
- IBM Plex — <https://github.com/IBM/plex>

## Subsetting

Only the **latin** subset of each face is vendored. None of these three families
ships Devanagari, so the Hindi and Marathi strings shown in the dossier and the
Telegram transcript already fall back to a system face — pulling the Cyrillic,
Greek and Vietnamese subsets would have added transfer weight for nothing.

Total vendored: **~91 KB** across six files.

## Regenerating

Retrieved from the Google Fonts CSS API with a woff2-capable user agent, taking
the `latin` `@font-face` block for each family and weight declared in
`console/app/layout.tsx`. The exact source URL for each file is recorded in the
commit that added it.
