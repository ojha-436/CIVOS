"""Re-shoot the citizen intake against the LIVE deployment, for the film.

docs/screenshots/intake-result.png was taken against localhost with no API
reachable, so it shows the offline-sandbox fallback and a placeholder English
line. In a launch film that reads as "the product does not work". This shoots the
same flow against the deployed console so the extraction on screen is the real
Gemini round-trip.

Usage:
    uv run python scripts/video/shoot_intake.py
    uv run python scripts/video/shoot_intake.py --base http://localhost:3000
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "video" / "assets" / "ui"
LIVE = "https://civos-console-924096812044.asia-south1.run.app"
SAY = "आमच्या वाडीतला हातपंप पाच महिन्यांपासून कोरडा आहे"


def main() -> None:
    args = sys.argv[1:]
    base = args[args.index("--base") + 1] if "--base" in args else LIVE

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="chrome")
        except Exception:
            browser = pw.chromium.launch()
        ctx = browser.new_context(device_scale_factor=2,
                                  viewport={"width": 430, "height": 932})
        page = ctx.new_page()

        # /report is gated; a throwaway account is the only way to photograph it.
        page.goto(f"{base}/login", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        if page.locator(".auth-tabs").count():
            page.click("text=Sign up")
            page.wait_for_timeout(800)
            page.fill("#fullName", "Film Session")
            page.fill("#email", f"civos-film-{int(time.time())}@example.com")
            page.fill("#password", "civos-film-pw-2026")
            page.click("button.auth-submit")
            page.wait_for_timeout(9000)

        page.goto(f"{base}/report", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        if page.locator(".mic").count() == 0:
            sys.exit("intake did not render — still on the gate?")

        page.click("text=Type it")
        page.wait_for_timeout(600)
        page.fill("textarea.say", SAY)
        page.click(".send")
        # A live extraction is a Gemini round-trip, not a local mock.
        page.wait_for_timeout(14000)

        if page.locator(".result").count() == 0:
            sys.exit("no .result panel — extraction never returned")
        body = page.inner_text("body")
        offline = "Offline Sandbox" in body or "offline or unreachable" in body
        page.screenshot(path=str(OUT / "intake-phone.png"))
        print(f"  wrote video/assets/ui/intake-phone.png")
        print(f"  offline fallback on screen: {offline}")
        if offline:
            print("  → the API was unreachable; the frame still says sandbox.")
        browser.close()


if __name__ == "__main__":
    main()
