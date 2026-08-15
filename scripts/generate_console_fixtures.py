"""Generate the console's data fixture — the frozen contract Phases 1–4 will fill.

Why this exists: the policymaker console is the most likely phase to overrun
(plan.md risk register: likelihood High), and it is what judges actually click.
Building it against a fixture that matches `Warehouse.aggregate_scores()` exactly
means the expensive UI work happens now and the real data slots in behind an
interface that does not move.

**Everything this script emits about citizens is synthetic and is labelled as such
in the interface itself.** District boundaries and names are real. **Deficit values
are now real too** — NFHS-5 2019-21, built by `scripts/build_deficit_layer.py` and
reconciled onto this boundary set. Where a district or sector has no real value it
is marked `has_deficit = false`, assigned the `no_data` quadrant, excluded from the
ranking and rendered grey. It is never given an invented number.

The participation bias is deliberate and is the whole point. Connectivity drives
three things at once: it *raises* how much a district complains, it *lowers* how
much of its real deficit gets voiced, and it *raises* how often a complaint carries
a photograph. That last one is the urban skew SPEC §13 warns about — modelled on
purpose so the `w5 = 0` decision can be demonstrated rather than described.

Deterministic: the same inputs always produce the same fixture, so a reviewer can
regenerate and diff.

Usage:
    uv run python scripts/generate_console_fixtures.py --geojson <path>
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml
from rich.console import Console

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "console" / "public" / "data"
console = Console()

STATE_ABBR_OVERRIDES = {
    "Andaman and Nicobar": "AN",
    "Arunachal Pradesh": "AR",
    "Andhra Pradesh": "AP",
    "Madhya Pradesh": "MP",
    "Uttar Pradesh": "UP",
    "Himachal Pradesh": "HP",
    "West Bengal": "WB",
    "Tamil Nadu": "TN",
    "Jammu and Kashmir": "JK",
    "Dadra and Nagar Haveli": "DN",
    "Daman and Diu": "DD",
    "Uttaranchal": "UK",
    "Orissa": "OR",
    "NCT of Delhi": "DL",
}


def rnd(*parts: str) -> float:
    """Deterministic float in [0,1) from any key. Reproducible across machines."""
    h = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") / float(1 << 64)


def slug(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def state_abbr(state: str) -> str:
    if state in STATE_ABBR_OVERRIDES:
        return STATE_ABBR_OVERRIDES[state]
    words = [w for w in re.split(r"\s+", state) if w]
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return state[:2].upper()


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# synthetic citizen voices — labelled as synthetic everywhere they surface
# ---------------------------------------------------------------------------

QUOTES: dict[str, list[tuple[str, str, str]]] = {
    "water_sanitation": [
        ("mr", "आमच्या वाडीतला हातपंप पाच महिन्यांपासून कोरडा आहे.",
         "The handpump in our hamlet has been dry for five months."),
        ("hi", "बोरवेल बंद पड़ा है, औरतों को दो किलोमीटर चलकर पानी लाना पड़ता है.",
         "The borewell is out of order; women walk two kilometres to fetch water."),
        ("bn", "নলকূপের জল নোনতা, খেলে পেট খারাপ হয়।",
         "The tubewell water is brackish and makes people ill."),
        ("ta", "பொது கழிப்பறை பூட்டப்பட்டுள்ளது, ஒரு வருடமாக பழுது பார்க்கவில்லை.",
         "The community toilet block is locked and has not been repaired in a year."),
        ("hi", "नाली टूटी है, बरसात में घर के सामने पानी भर जाता है.",
         "The drain is broken and water collects in front of our houses in the rains."),
    ],
    "roads_transport": [
        ("hi", "बरसात में सड़क कीचड़ बन जाती है, एम्बुलेंस गाँव तक नहीं आ पाती.",
         "In the rains the road turns to mud and the ambulance cannot reach the village."),
        ("mr", "पुलाचा भाग वाहून गेला आहे, मुलं शाळेत जाऊ शकत नाहीत.",
         "Part of the culvert has washed away and children cannot get to school."),
        ("te", "బస్సు ఇక్కడ ఆగదు, రోడ్డు అంత గోతులమయం.",
         "The bus does not stop here any more because the road is full of pits."),
        ("kn", "ರಸ್ತೆ ಹಾಳಾಗಿದೆ, ಮಳೆಗಾಲದಲ್ಲಿ ಸಂಪೂರ್ಣ ಸಂಪರ್ಕ ಕಡಿತ.",
         "The road has broken up and we are cut off entirely during the monsoon."),
    ],
    "electricity": [
        ("hi", "ट्रांसफार्मर तीन महीने से जला पड़ा है, शिकायत की पर कोई नहीं आया.",
         "The transformer has been burnt out for three months; we complained and nobody came."),
        ("mr", "रस्त्यावरचे दिवे बंद आहेत, मुली संध्याकाळी बाहेर पडायला घाबरतात.",
         "The street lights are dead and girls are afraid to go out after dark."),
        ("bn", "দিনে ছয় ঘণ্টাও বিদ্যুৎ থাকে না, সেচের পাম্প চালানো যায় না।",
         "We do not get six hours of power a day and cannot run the irrigation pump."),
        ("gu", "થાંભલો નમી ગયો છે, વાયર માણસના માથા સુધી લટકે છે.",
         "The pole is leaning and the wire hangs down to head height."),
    ],
    "health": [
        ("hi", "उपकेंद्र में नर्स हफ्ते में एक बार आती है, प्रसव के लिए शहर जाना पड़ता है.",
         "The nurse visits the sub-centre once a week; for deliveries we must travel to town."),
        ("ml", "പ്രാഥമികാരോഗ്യ കേന്ദ്രത്തിന്റെ കെട്ടിടം ചോർന്നൊലിക്കുന്നു.",
         "The primary health centre building leaks badly."),
        ("mr", "रुग्णवाहिका येण्याचा रस्ता नाही, खाटेवरून न्यावं लागतं.",
         "There is no road for the ambulance; we carry patients on a cot."),
    ],
    "education": [
        ("hi", "स्कूल की दीवार गिर गई है, बच्चे बरामदे में बैठते हैं.",
         "The school wall has collapsed and the children sit in the verandah."),
        ("ta", "பள்ளியில் பெண் குழந்தைகளுக்கு தனி கழிப்பறை இல்லை.",
         "The school has no separate toilet for girls."),
        ("bn", "একটাই ঘরে তিনটে ক্লাস একসঙ্গে বসে।",
         "Three classes sit together in a single room."),
        ("mr", "पावसाळ्यात वर्गात पाणी गळतं, वह्या भिजतात.",
         "The classroom leaks in the monsoon and the notebooks get soaked."),
    ],
}

ASSETS: dict[str, list[str]] = {
    "water_sanitation": ["handpump", "borewell", "standpost", "toilet_block", "drain"],
    "roads_transport": ["road_surface", "culvert", "bridge", "bus_stop"],
    "electricity": ["transformer", "pole", "street_light", "service_line"],
    "health": ["phc_building", "sub_centre", "ambulance_access_road"],
    "education": ["school_building", "classroom", "boundary_wall", "school_toilet"],
}

FLAGS = ["structurally_unsafe", "standing_water", "unusable", "partially_functional"]


# ---------------------------------------------------------------------------


def load_real_deficits() -> dict[tuple[str, str], float]:
    """Real NFHS-5 deprivation per (district, sector), from the Phase 1 build.

    Where a sector has more than one indicator (water AND sanitation), the sector
    deficit is their mean — SPEC §7 names both for Water & Sanitation and neither
    alone represents the sector.

    Districts or sectors with no real value are simply absent from this map. The
    caller marks them `has_deficit = false` and the console renders them grey and
    excludes them from the ranking, rather than inventing a number.
    """
    path = REPO / "data" / "fact_deficit_indicator.csv"
    if not path.exists():
        console.print("[yellow]No deficit layer found — run scripts/build_deficit_layer.py first.[/yellow]")
        return {}
    acc: dict[tuple[str, str], list[float]] = {}
    for r in csv.DictReader(path.open(encoding="utf-8")):
        acc.setdefault((r["admin_unit_code"], r["sector"]), []).append(float(r["deficit_pct"]))
    return {k: sum(v) / len(v) for k, v in acc.items()}


def bbox_centroid(geom: dict) -> tuple[float, float]:
    xs: list[float] = []
    ys: list[float] = []

    def walk(c):
        if isinstance(c, (int, float)):
            return
        if c and isinstance(c[0], (int, float)):
            xs.append(c[0])
            ys.append(c[1])
            return
        for sub in c:
            walk(sub)

    walk(geom.get("coordinates", []))
    if not xs:
        return (0.0, 0.0)
    return (round(sum(xs) / len(xs), 4), round(sum(ys) / len(ys), 4))


def main(
    geojson: str = typer.Option(..., "--geojson", help="Simplified district GeoJSON"),
) -> None:
    src = Path(geojson)
    gj = json.loads(src.read_text())
    sectors_cfg = yaml.safe_load((REPO / "adapters" / "in" / "sectors.yaml").read_text())
    schemes_cfg = yaml.safe_load((REPO / "adapters" / "in" / "schemes.yaml").read_text())
    sectors = sectors_cfg["sectors"]
    real_deficits = load_real_deficits()
    console.print(f"Real deficit values loaded: [bold]{len(real_deficits)}[/bold] district-sector pairs")
    schemes = {s["key"]: s for s in schemes_cfg["schemes"]}

    console.print(f"Districts in source: [bold]{len(gj['features'])}[/bold]")

    # -- pass 1: identity, geography, connectivity --------------------------
    districts: list[dict] = []
    seen: set[str] = set()
    for feat in gj["features"]:
        props = feat.get("properties") or {}
        state = (props.get("NAME_1") or "Unknown").strip()
        name = (props.get("NAME_2") or "Unknown").strip()
        code = f"IN-{state_abbr(state)}-{slug(name)}"
        n = 2
        base = code
        while code in seen:
            code = f"{base}-{n}"
            n += 1
        seen.add(code)

        # Connectivity stands in for urbanisation, literacy and smartphone
        # ownership — the things that decide whether a citizen can complain.
        connectivity = rnd("conn", code)
        lon, lat = bbox_centroid(feat["geometry"])
        population = int(180_000 + rnd("pop", code) * 3_400_000)

        feat["properties"] = {"code": code, "name": name, "state": state}
        districts.append(
            {
                "code": code,
                "name": name,
                "state": state,
                "lon": lon,
                "lat": lat,
                "population": population,
                "connectivity": connectivity,
            }
        )

    # -- pass 2: per (district, sector) terms -------------------------------
    rows: list[dict] = []
    for d in districts:
        conn = d["connectivity"]
        for sec in sectors:
            key = sec["key"]
            k = f"{d['code']}|{key}"

            # Deficit is REAL where Phase 1 could load it: NFHS-5 2019-21,
            # reconciled onto this boundary set. Absent for districts that did not
            # reconcile and for Roads & Transport, which has no health-survey
            # equivalent — those are flagged, not filled.
            real = real_deficits.get((d["code"], key))
            has_deficit = real is not None
            deficit = real if has_deficit else 0.0

            # A district is only heard from when it has BOTH a problem and the
            # means to report it. This is the bias the engine exists to correct.
            heard = (deficit / 100) * (0.18 + 0.82 * conn)
            demand = clamp(heard * 92 + rnd("dem", k) * 20 - 6, 0, 99)

            participation = round(clamp(0.35 + conn * 7.4 + rnd("par", k) * 1.1, 0.05, 9.5), 2)
            signals = max(0, int(participation * d["population"] / 1000 / 42))
            needs = max(0, int(signals / (3.1 + rnd("dedup", k) * 4.4))) if signals else 0
            languages = 1 + int(rnd("lang", k) * 6) if signals else 0

            # Camera ownership tracks connectivity — the urban skew SPEC §13
            # warns about, modelled deliberately so w5=0 can be demonstrated.
            evidence = clamp(conn * 62 + rnd("ev", k) * 26, 0, 96) if needs else 0
            images = int(needs * evidence / 100)

            forecast = round((rnd("fc", k) - 0.42) * 26, 1)
            suppressed = signals < 5

            rows.append(
                {
                    "code": d["code"],
                    "sector": key,
                    "signals": signals,
                    "needs": needs,
                    "languages": languages,
                    "images": images,
                    "demand": round(demand, 1),
                    "deficit": round(deficit, 1),
                    "has_deficit": has_deficit,
                    "participation": participation,
                    "evidence": round(evidence, 1),
                    "forecast": forecast,
                    "suppressed": suppressed,
                }
            )

    # -- voice correction needs the cross-district median --------------------
    prs = sorted(r["participation"] for r in rows)
    median_pr = prs[len(prs) // 2]
    for r in rows:
        vc = clamp(median_pr / max(r["participation"], 1e-6), 0.5, 3.0)
        r["voice_correction"] = round(vc, 2)
        r["adjusted_demand"] = round(min(100.0, r["demand"] * vc), 1)
        r["silence_gap"] = round(r["deficit"] - r["demand"], 1)

    # -- quadrants off cross-district medians --------------------------------
    # Medians over rows that actually carry a real deficit. Including the zeros
    # written for unmatched districts would drag both medians down and mislabel
    # the whole map.
    scored = [r for r in rows if r["has_deficit"]]
    med_dem = sorted(r["demand"] for r in scored)[len(scored) // 2]
    med_def = sorted(r["deficit"] for r in scored)[len(scored) // 2]
    for r in rows:
        if not r["has_deficit"]:
            r["quadrant"] = "no_data"
            continue
        hi_d, hi_x = r["demand"] >= med_dem, r["deficit"] >= med_def
        r["quadrant"] = (
            "act_now" if (hi_d and hi_x)
            else "silent_need" if (not hi_d and hi_x)
            else "expectation_gap" if hi_d
            else "stable"
        )

    # -- representative quotes + evidence, for drilldown and dossier ---------
    for r in rows:
        pool = QUOTES[r["sector"]]
        assets = ASSETS[r["sector"]]
        k = f"{r['code']}|{r['sector']}"
        # Quote text lives once in `quote_pool`; rows carry indices. Inlining the
        # strings on all 2,970 rows made the fixture 3.7 MB for no added meaning.
        if r["needs"]:
            idx = int(rnd("q", k) * len(pool))
            r["quotes"] = [(idx + i) % len(pool) for i in range(min(3, len(pool)))]
        else:
            r["quotes"] = []
        r["assets"] = (
            [
                {
                    "type": assets[int(rnd("a", k, str(i)) * len(assets))],
                    "flag": FLAGS[int(rnd("f", k, str(i)) * len(FLAGS))],
                    "severity": 1 + int(rnd("s", k, str(i)) * 5),
                }
                for i in range(min(4, r["images"]))
            ]
            if r["images"]
            else []
        )

    # -- write ---------------------------------------------------------------
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "districts.geojson").write_text(json.dumps(gj, separators=(",", ":")))

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "instance": "CIVOS-IN",
            "provenance": {
                "boundaries": "real — public district boundary data, simplified for web rendering",
                "district_names": "real",
                "deficit_indicators": "REAL — NFHS-5 2019-21 (IIPS/MoHFW), reconciled onto this boundary set. See docs/DATA-RECONCILIATION.md",
                "citizen_signals": "SYNTHETIC — generated with a deliberate participation bias",
                "population": "PLACEHOLDER",
                "quotes": "SYNTHETIC — illustrative phrasing, real languages",
            },
            "median_participation_rate": median_pr,
            "counts": {"districts": len(districts), "rows": len(rows)},
        },
        "quote_pool": {
            key: [{"lang": lang, "original": orig, "english": eng} for lang, orig, eng in pool]
            for key, pool in QUOTES.items()
        },
        "sectors": [
            {
                "key": s["key"],
                "label": s["label"],
                "short": s["short"],
                "indicator": s["indicator"]["label"],
                "source": s["indicator"]["source"],
                "year": s["indicator"]["year"],
                "schemes": [
                    {
                        "name": schemes[k]["name"],
                        "ministry": schemes[k]["ministry"],
                        "eligibility": " ".join(schemes[k]["eligibility"].split()),
                        "unit": schemes[k]["unit"],
                        "unit_cost_inr": schemes[k]["unit_cost_inr"],
                    }
                    for k in s["schemes"]
                    if k in schemes
                ],
            }
            for s in sectors
        ],
        "districts": [
            {k: d[k] for k in ("code", "name", "state", "lon", "lat", "population")} for d in districts
        ],
        "rows": rows,
    }
    (OUT / "scores.json").write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))

    from collections import Counter

    q = Counter(r["quadrant"] for r in rows)
    console.print(f"Wrote [bold]{len(rows)}[/bold] rows over {len(districts)} districts → {OUT}")
    for name, n in q.most_common():
        console.print(f"  {name:18s} {n}")
    sn = [r for r in rows if r["quadrant"] == "silent_need" and not r["suppressed"]]
    console.print(f"Silent Need (unsuppressed): [bold]{len(sn)}[/bold] — must be non-empty and plausible")
    for f in [OUT / "districts.geojson", OUT / "scores.json"]:
        console.print(f"  {f.name}: {f.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    typer.run(main)
