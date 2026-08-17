"""Render the Telegram bot QR code committed at console/public/telegram-qr.svg.

The QR encodes the bot's PUBLIC t.me URL and nothing else. It never touches
`TELEGRAM_BOT_TOKEN` — a QR is a printed, photographed, screen-shared artefact,
and a token in one would be a credential leak with a very long tail.

The handle is read from the live API rather than hardcoded, so the committed
QR cannot silently drift out of sync with the bot it claims to point at. Pass
--handle to skip the network call (offline / CI).

Usage:
    uv run python scripts/make_telegram_qr.py
    uv run python scripts/make_telegram_qr.py --handle Civos_in_bot

Regenerate whenever the bot handle changes. `console/app/page.tsx` carries the
same handle in TELEGRAM_HANDLE — this script verifies the two agree.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "console" / "public" / "telegram-qr.svg"
PAGE = REPO / "console" / "app" / "page.tsx"

# Palette borrowed from console/app/globals.css so the tile sits in the design
# system. Dark modules on a light ground — scanners are trained on that polarity
# and an inverted QR fails on a meaningful share of cheap Android cameras.
INK = "#070a0e"
PAPER = "#ece5d8"


def resolve_handle() -> str:
    """Ask Telegram who this token belongs to. Public metadata only."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        try:
            from dotenv import load_dotenv

            load_dotenv(REPO / ".env")
            token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        except ImportError:
            pass
    if not token:
        sys.exit("TELEGRAM_BOT_TOKEN not set — pass --handle instead.")

    import json

    url = f"https://api.telegram.org/bot{token}/getMe"
    with urllib.request.urlopen(url, timeout=15) as r:
        payload = json.load(r)
    if not payload.get("ok"):
        sys.exit(f"getMe failed: {payload}")
    return payload["result"]["username"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--handle", help="bot username, without the @")
    args = ap.parse_args()

    handle = args.handle or resolve_handle()
    target = f"https://t.me/{handle}"

    try:
        import segno
    except ImportError:
        sys.exit("segno not installed — `uv run --with segno python scripts/make_telegram_qr.py`")

    # Error correction M: ~15% recoverable. Enough for a screen-shared or
    # printed poster without inflating the module count and hurting scan
    # distance on a projector.
    qr = segno.make(target, error="m")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    qr.save(
        OUT,
        kind="svg",
        scale=1,
        border=2,
        dark=INK,
        light=PAPER,
        svgclass=None,
        lineclass=None,
        omitsize=True,   # no width/height attrs — CSS sizes it responsively
        unit="",
    )

    svg = OUT.read_text()
    OUT.write_text(svg)

    # Keep the page constant honest.
    page_handle = None
    if PAGE.exists():
        m = re.search(r"TELEGRAM_HANDLE:\s*string \| null = '([^']*)'", PAGE.read_text())
        page_handle = m.group(1) if m else None

    print(f"encoded : {target}")
    print(f"written : {OUT.relative_to(REPO)}  ({qr.symbol_size(scale=1, border=2)[0]} modules)")
    if page_handle is None:
        print("warning : could not read TELEGRAM_HANDLE from console/app/page.tsx")
    elif page_handle.lower() != handle.lower():
        sys.exit(
            f"MISMATCH : page.tsx says '{page_handle}' but the bot is '{handle}'. "
            "Update TELEGRAM_HANDLE."
        )
    else:
        print(f"verified: console/app/page.tsx TELEGRAM_HANDLE = '{page_handle}'")


if __name__ == "__main__":
    main()
