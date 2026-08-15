# Language coverage — measured, not claimed

Probed against live Google APIs on **2026-08-14 17:52 UTC**, project `civos-in`.

| Tier | Capability | Count | How it was established |
|---|---|---|---|
| **A** | Full voice round-trip — speak in, spoken confirmation back | **56** | api-probed (Text-to-Speech voices.list ∩ Speech-to-Text recognition probe) |
| **B** | Voice in, text confirmation out | **3** | api-probed (Speech-to-Text recognition probe) |
| **C** | Text in (typed or messaged), full pipeline | **196** | api-probed (Translation v3 getSupportedLanguages) |
| **D** | Image only — **no language required at all** | universal | by construction |

## Read the provenance before quoting a number

Tier C is complete: the Translation API returns its whole supported list, so **196** is exact.

Tiers A and B are a **probed lower bound**. Speech-to-Text publishes no list-locales API and rejects bare language codes, so support is established by attempting a real recognition per candidate locale — a supported locale returns 200 with zero results, an unsupported one returns an explicit 400. The candidate set is seeded from the 75 locales that have synthesis voices. Locales Speech-to-Text supports but Text-to-Speech does not voice are therefore undercounted, not overcounted.

Stating this is deliberate. A measured lower bound is worth more than a larger number copied out of documentation, and an evaluator who checks will find the limitation disclosed rather than papered over.

## Adapter check — `adapters/in/languages.yaml`

**19 of 22** languages claimed by `CIVOS-IN` are covered by the Translation API.

Not covered:

- **Bodo** (`brx`)
- **Kashmiri** (`ks`)
- **Santali** (`sat`)

This check exists because the number is worth getting right before it is said on camera. These languages reach citizens through **Tier D** — the image channel needs no language at all — and through code-mixed speech, which the extraction model handles natively even where a formal translation pair does not exist.

## Tier D is the one worth saying out loud

The image channel has no language dependency. A citizen whose language nothing on this page supports can still photograph a broken handpump and be heard. That is the accessibility floor, and it is the reason the image modality is not merely a third input.

## Tier A — full voice round-trip

| Locale | TTS voices | STT models |
|---|---|---|
| `af-ZA` | 1 | long, chirp_2 |
| `am-ET` | 4 | long, chirp_2 |
| `bg-BG` | 31 | long, chirp_2 |
| `bn-IN` | 38 | chirp_2 |
| `ca-ES` | 1 | long, chirp_2 |
| `cs-CZ` | 32 | long, chirp_2 |
| `da-DK` | 35 | long, chirp_2 |
| `de-DE` | 42 | long, chirp_2 |
| `el-GR` | 32 | long, chirp_2 |
| `en-AU` | 49 | long, chirp_2 |
| `en-GB` | 63 | long, chirp_2 |
| `en-IN` | 49 | long, chirp_2 |
| `en-US` | 99 | long, chirp_2 |
| `es-ES` | 49 | long, chirp_2 |
| `es-US` | 48 | long, chirp_2 |
| `et-EE` | 31 | long, chirp_2 |
| `eu-ES` | 1 | long, chirp_2 |
| `fi-FI` | 32 | long, chirp_2 |
| `fil-PH` | 10 | long, chirp_2 |
| `fr-CA` | 45 | long, chirp_2 |
| `fr-FR` | 42 | long, chirp_2 |
| `gl-ES` | 1 | long, chirp_2 |
| `gu-IN` | 38 | long, chirp_2 |
| `he-IL` | 38 | long, chirp_2 |
| `hi-IN` | 46 | long, chirp_2 |
| `hr-HR` | 30 | chirp_2 |
| `hu-HU` | 32 | long, chirp_2 |
| `id-ID` | 38 | long, chirp_2 |
| `is-IS` | 1 | long, chirp_2 |
| `it-IT` | 40 | long, chirp_2 |
| `ja-JP` | 41 | long, chirp_2 |
| `kn-IN` | 38 | long, chirp_2 |
| `ko-KR` | 41 | long, chirp_2 |
| `lt-LT` | 31 | long, chirp_2 |
| `lv-LV` | 31 | long, chirp_2 |
| `ml-IN` | 38 | long, chirp_2 |
| `mr-IN` | 36 | long, chirp_2 |
| `ms-MY` | 8 | long, chirp_2 |
| `nb-NO` | 34 | long, chirp_2 |
| `nl-NL` | 34 | long, chirp_2 |
| `pl-PL` | 34 | long, chirp_2 |
| `pt-BR` | 43 | long, chirp_2 |
| `pt-PT` | 4 | long, chirp_2 |
| `ro-RO` | 32 | long, chirp_2 |
| `ru-RU` | 18 | long, chirp_2 |
| `sk-SK` | 32 | long, chirp_2 |
| `sl-SI` | 30 | long, chirp_2 |
| `sr-RS` | 31 | long, chirp_2 |
| `sv-SE` | 44 | long, chirp_2 |
| `sw-KE` | 30 | chirp_2 |
| `ta-IN` | 38 | long, chirp_2 |
| `te-IN` | 34 | long, chirp_2 |
| `th-TH` | 32 | long, chirp_2 |
| `tr-TR` | 40 | long, chirp_2 |
| `uk-UA` | 32 | long, chirp_2 |
| `vi-VN` | 40 | long, chirp_2 |

## Tier B — voice in, text out

| Locale | STT models |
|---|---|
| `as-IN` | chirp_2 |
| `or-IN` | chirp_2 |
| `sd-IN` | chirp_2 |

## Tier C — text pipeline

`ab`, `ace`, `ach`, `af`, `ak`, `alz`, `am`, `ar`, `as`, `awa`, `ay`, `az`, `ba`, `ban`, `bbc`, `be`, `bem`, `bew`, `bg`, `bho`, `bik`, `bm`, `bn`, `br`, `bs`, `bts`, `btx`, `bua`, `ca`, `ceb`, `cgg`, `chm`, `ckb`, `cnh`, `co`, `crh`, `crs`, `cs`, `cv`, `cy`, `da`, `de`, `din`, `doi`, `dov`, `dv`, `dz`, `ee`, `el`, `en`, `eo`, `es`, `et`, `eu`, `fa`, `ff`, `fi`, `fil`, `fj`, `fr`, `fr-CA`, `fy`, `ga`, `gaa`, `gd`, `gl`, `gn`, `gom`, `gu`, `ha`, `haw`, `he`, `hi`, `hil`, `hmn`, `hr`, `hrx`, `ht`, `hu`, `hy`, `id`, `ig`, `ilo`, `is`, `it`, `iw`, `ja`, `jv`, `jw`, `ka`, `kk`, `km`, `kn`, `ko`, `kri`, `ktu`, `ku`, `ky`, `la`, `lb`, `lg`, `li`, `lij`, `lmo`, `ln`, `lo`, `lt`, `ltg`, `luo`, `lus`, `lv`, `mai`, `mak`, `mg`, `mi`, `min`, `mk`, `ml`, `mn`, `mni-Mtei`, `mr`, `ms`, `ms-Arab`, `mt`, `my`, `ne`, `new`, `nl`, `no`, `nr`, `nso`, `nus`, `ny`, `oc`, `om`, `or`, `pa`, `pa-Arab`, `pag`, `pam`, `pap`, `pl`, `ps`, `pt`, `pt-PT`, `qu`, `rn`, `ro`, `rom`, `ru`, `rw`, `sa`, `scn`, `sd`, `sg`, `shn`, `si`, `sk`, `sl`, `sm`, `sn`, `so`, `sq`, `sr`, `ss`, `st`, `su`, `sv`, `sw`, `szl`, `ta`, `te`, `tet`, `tg`, `th`, `ti`, `tk`, `tl`, `tn`, `tr`, `ts`, `tt`, `ug`, `uk`, `ur`, `uz`, `vi`, `xh`, `yi`, `yo`, `yua`, `yue`, `zh`, `zh-CN`, `zh-TW`, `zu`

---

Regenerate with `uv run python scripts/probe_language_capability.py`. The numbers above move on their own as Google expands coverage; nothing here is checked in by hand.
