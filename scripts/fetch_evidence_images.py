"""Phase 2.3 — source real, openly-licensed evidence photographs.

**These are never generated.** Vision accuracy demonstrated on synthetic images
proves nothing: a model asked to classify pictures another model drew is graded on
its ability to recognise its own dialect, not on whether it can read a photograph
of a broken handpump. Gate 2 is only meaningful on real photographs, so the whole
modality rests on this script fetching real ones.

Source is Wikimedia Commons, filtered to licences that permit redistribution.
Every image is attributed individually in docs/IMAGE-ATTRIBUTION.md with its
author, licence and source URL — which is both a licence obligation and DPG
evidence (indicator 2 covers data, not only code).

Coverage will be uneven across sectors and asset types. That is expected and is
left uneven rather than padded: a thin evidence base for one sector is a fact
about what exists on Commons, and `EvidenceStrength` having real variance is
better for the product than a manufactured balance.

Usage:
    uv run python scripts/fetch_evidence_images.py --target 150
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "console" / "public" / "evidence"
console = Console()

API = "https://commons.wikimedia.org/w/api.php"
UA = "CIVOS-evidence-fetch/0.1 (https://github.com/ojha-436/CIVOS; civic research)"
THUMB_PX = 520  # enough for vision and for a dossier strip; 800px made the repo 36 MB

# Licences that permit redistribution with attribution. Anything else is skipped,
# including NoDerivatives and NonCommercial variants — a Digital Public Good
# cannot ship assets a downstream ministry is not allowed to reuse.
ALLOWED = re.compile(
    r"^(cc0|cc[- ]by([- ]sa)?([- ]\d(\.\d)?)?|public domain|pd|"
    r"gfdl|attribution|cc[- ]by[- ]sa)", re.I
)
FORBIDDEN = re.compile(r"(nc\b|noncommercial|nd\b|noderiv|fair use|non-free)", re.I)

# Search terms per sector, aimed at the asset types SPEC §7 lists. Deliberately
# India-weighted, because a photograph of a Dutch bike lane is not evidence about
# an Indian district.
QUERIES: dict[str, list[str]] = {
    "water_sanitation": [
        "handpump India", "hand pump village India", "borewell India", "village well India",
        "public standpost India", "toilet block India", "open drain India village",
        "water tank village India", "tubewell India",
    ],
    "roads_transport": [
        "rural road India damaged", "village road India", "culvert India", "broken road India",
        "bridge village India", "bus stop rural India", "unpaved road India village",
    ],
    "electricity": [
        "electricity pole India", "distribution transformer India", "street light India village",
        "power lines rural India", "electric pole village India",
    ],
    "health": [
        "primary health centre India", "sub centre health India", "rural hospital India building",
        "health centre village India",
    ],
    "education": [
        "government school India building", "village school India", "school classroom India rural",
        "school building India damaged", "anganwadi India",
    ],
}


def api(params: dict) -> dict:
    params = {**params, "format": "json", "formatversion": "2"}
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
        return json.loads(r.read().decode("utf-8"))


def search(term: str, limit: int) -> list[str]:
    d = api({
        "action": "query", "list": "search", "srsearch": f"{term} filetype:bitmap",
        "srnamespace": "6", "srlimit": str(limit),
    })
    return [s["title"] for s in d.get("query", {}).get("search", [])]


def info(titles: list[str]) -> list[dict]:
    if not titles:
        return []
    d = api({
        "action": "query", "titles": "|".join(titles), "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime|size", "iiurlwidth": str(THUMB_PX),
    })
    return d.get("query", {}).get("pages", [])


def _reencode(path: Path) -> None:
    """Cap dimensions and re-encode as JPEG.

    Commons returns the ORIGINAL when it is narrower than the requested thumb
    width, and some originals are large PNGs. Left alone that put 38.6 MB of
    images in the repo for 150 photographs; re-encoding brings it to 6.8 MB with
    no loss that matters to either a vision model or a dossier strip.
    """
    try:
        from PIL import Image

        im = Image.open(path).convert("RGB")
        im.thumbnail((THUMB_PX, THUMB_PX))
        im.save(path, "JPEG", quality=78, optimize=True)
    except Exception:  # noqa: BLE001 — a fetched image is better than none
        pass


def clean(html: str | None) -> str:
    if not html:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()


def usable(meta: dict) -> tuple[bool, str]:
    lic = clean(meta.get("LicenseShortName", {}).get("value")) or clean(
        meta.get("License", {}).get("value")
    )
    if not lic:
        return False, "no licence stated"
    if FORBIDDEN.search(lic):
        return False, f"restrictive licence: {lic}"
    if not ALLOWED.search(lic):
        return False, f"unrecognised licence: {lic}"
    return True, lic


def main(
    target: int = typer.Option(150, "--target"),
    per_query: int = typer.Option(14, "--per-query"),
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sectors = {
        s["key"]: s for s in yaml.safe_load((REPO / "adapters" / "in" / "sectors.yaml").read_text())["sectors"]
    }
    console.rule(f"[bold]Phase 2.3 — evidence images[/bold] · target {target}")

    kept: list[dict] = []
    skipped: Counter = Counter()
    seen: set[str] = set()

    per_sector = max(1, target // len(QUERIES))
    for sector, terms in QUERIES.items():
        got = 0
        for term in terms:
            if got >= per_sector:
                break
            try:
                titles = search(term, per_query)
            except Exception as exc:  # noqa: BLE001
                console.print(f"  [yellow]search failed[/yellow] {term}: {str(exc)[:70]}")
                continue

            for page in info(titles):
                if got >= per_sector:
                    break
                ii = (page.get("imageinfo") or [{}])[0]
                if not ii or not ii.get("thumburl"):
                    continue
                if not str(ii.get("mime", "")).startswith("image/"):
                    continue
                title = page["title"]
                if title in seen:
                    continue
                seen.add(title)

                meta = ii.get("extmetadata", {})
                ok, lic = usable(meta)
                if not ok:
                    skipped[lic.split(":")[0]] += 1
                    continue

                author = clean(meta.get("Artist", {}).get("value")) or "Unknown"
                stem = re.sub(r"[^a-zA-Z0-9]+", "-", title.removeprefix("File:")).strip("-").lower()
                # Short digest suffix: truncating long Commons titles to 70 chars
                # collided, so five images silently overwrote each other and the
                # manifest claimed more files than existed on disk.
                digest = hashlib.sha1(title.encode()).hexdigest()[:6]
                fname = f"{sector}--{stem[:60]}-{digest}.jpg"
                dest = OUT / fname

                if not dest.exists():
                    try:
                        req = urllib.request.Request(ii["thumburl"], headers={"User-Agent": UA})
                        with urllib.request.urlopen(req, timeout=90) as r:  # noqa: S310
                            dest.write_bytes(r.read())
                        _reencode(dest)
                    except Exception as exc:  # noqa: BLE001
                        console.print(f"  [yellow]download failed[/yellow] {title[:50]}: {str(exc)[:50]}")
                        continue
                    time.sleep(0.15)  # be a polite API citizen

                kept.append({
                    "file": fname,
                    "sector": sector,
                    "title": title.removeprefix("File:"),
                    "author": author[:180],
                    "licence": lic,
                    "source": ii.get("descriptionurl", ""),
                    "query": term,
                    "width": ii.get("thumbwidth"),
                    "height": ii.get("thumbheight"),
                })
                got += 1
        console.print(f"  {sectors[sector]['label']:22s} {got} images")

    # -- manifest + attribution ---------------------------------------------
    (REPO / "data" / "evidence_images.json").write_text(json.dumps(kept, indent=2, ensure_ascii=False))

    by_sector: dict[str, list[dict]] = defaultdict(list)
    for k in kept:
        by_sector[k["sector"]].append(k)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md: list[str] = []
    md.append("# Evidence image attribution")
    md.append("")
    md.append(
        f"**{len(kept)} photographs**, fetched {stamp} from Wikimedia Commons. Every one is a "
        "real photograph under a licence that permits redistribution with attribution."
    )
    md.append("")
    md.append(
        "**None of these are generated.** Vision accuracy demonstrated on synthetic images would "
        "prove nothing — a model asked to classify pictures another model drew is graded on "
        "recognising its own dialect, not on reading a photograph of a broken handpump. Gate 2 is "
        "only meaningful on real photographs."
    )
    md.append("")
    md.append("Regenerate with `uv run python scripts/fetch_evidence_images.py`.")
    md.append("")
    md.append("| Sector | Images |")
    md.append("|---|---|")
    for s, items in sorted(by_sector.items()):
        md.append(f"| {sectors[s]['label']} | {len(items)} |")
    md.append("")
    md.append(
        "Coverage is uneven and is **left uneven**. What Commons happens to hold is a fact about "
        "the world, not a defect to pad out, and `EvidenceStrength` having real variance is more "
        "useful to the product than a manufactured balance."
    )
    md.append("")
    for s, items in sorted(by_sector.items()):
        md.append(f"## {sectors[s]['label']}")
        md.append("")
        md.append("| File | Title | Author | Licence | Source |")
        md.append("|---|---|---|---|---|")
        for k in sorted(items, key=lambda x: x["file"]):
            md.append(
                f"| `{k['file']}` | {k['title'][:70]} | {k['author'][:60]} | {k['licence']} | "
                f"[Commons]({k['source']}) |"
            )
        md.append("")

    (REPO / "docs" / "IMAGE-ATTRIBUTION.md").write_text("\n".join(md) + "\n")

    t = Table(title="Evidence images")
    t.add_column("sector"); t.add_column("images", justify="right")
    for s, items in sorted(by_sector.items()):
        t.add_row(sectors[s]["label"], str(len(items)))
    console.print(); console.print(t)
    if skipped:
        console.print(f"  skipped on licence: {dict(skipped.most_common(5))}")
    console.print(f"  images → {OUT.relative_to(REPO)}")
    console.print("  attribution → docs/IMAGE-ATTRIBUTION.md")


if __name__ == "__main__":
    typer.run(main)
