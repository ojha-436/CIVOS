"""Screenshot the console for review and for the submission deck.

Doubles as a smoke test: it fails loudly if the map never paints or a panel is
missing, which a `next build` passing tells you nothing about.

Usage:
    uv run python scripts/shoot_console.py                 # all shots
    uv run python scripts/shoot_console.py --only toggle
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from playwright.sync_api import sync_playwright
from rich.console import Console

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "screenshots"
console = Console()

BASE = "http://localhost:3000"


def main(
    only: str = typer.Option("", "--only", help="Shoot a single named frame"),
    base: str = typer.Option(BASE, "--base"),
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    with sync_playwright() as pw:
        # channel="chrome" uses the locally installed Google Chrome instead of
        # Playwright's bundled build. The bundled chromium goes missing whenever
        # the playwright package is upgraded without re-running `playwright
        # install`, which made this script fail for a reason unrelated to the app
        # it is meant to be smoke-testing. Falls back if Chrome is absent.
        try:
            browser = pw.chromium.launch(channel="chrome")
        except Exception:
            browser = pw.chromium.launch()

        # ONE shared context, not a page per browser. /console and /report became
        # gated on 18 Aug 2026, and a Firebase session lives in IndexedDB scoped to
        # the context — a fresh page per frame would land on the login screen every
        # time and the console frames would silently capture the wrong page.
        ctx = browser.new_context(device_scale_factor=2)

        def sign_in() -> None:
            """Create a throwaway account so the gated frames can be captured.

            Nothing is seeded and nothing persists past the run. A real reviewer
            signs in as themselves; this exists only so the screenshot job is not
            blocked by the gate it is meant to photograph.
            """
            import time as _t

            page = ctx.new_page()
            page.set_viewport_size({"width": 1280, "height": 900})
            page.goto(f"{base}/login", wait_until="domcontentloaded")
            page.wait_for_timeout(2600)
            page.click("text=Sign up")
            page.wait_for_timeout(700)
            page.fill("#fullName", "Screenshot Session")
            page.fill("#email", f"civos-shoot-{int(_t.time())}@example.com")
            page.fill("#password", "civos-shoot-pw-2026")
            page.click("button.auth-submit")
            page.wait_for_timeout(8000)
            if page.locator(".auth-tabs").count():
                failures.append("could not sign in — gated frames would be wrong")
            page.close()

        def shoot(name: str, path: str, w: int, h: int, prepare=None) -> None:
            if only and only != name:
                return
            page = ctx.new_page()
            page.set_viewport_size({"width": w, "height": h})
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            # domcontentloaded, not networkidle: the Firebase SDK holds a
            # long-lived connection open, so networkidle never fires and every
            # goto() times out after 30s.
            page.goto(f"{base}{path}", wait_until="domcontentloaded")
            page.wait_for_timeout(4200)
            if prepare:
                prepare(page)
            page.wait_for_timeout(900)
            page.screenshot(path=str(OUT / f"{name}.png"))
            if errors:
                failures.append(f"{name}: js errors {errors[:2]}")
            console.print(f"  [green]shot[/green] {name}.png")
            page.close()

        # The login screen is itself an artefact worth having in the deck.
        shoot("login", "/login", 1280, 900, None)

        sign_in()

        # -- console, raw demand -------------------------------------------
        def check_map(page):
            # A map that never painted is the single most likely silent failure.
            canvas = page.locator("canvas.maplibregl-canvas")
            if canvas.count() == 0:
                failures.append("map canvas absent")
            if page.locator(".rank-item").count() < 10:
                failures.append("ranked list did not populate")

        shoot("console-raw", "/console", 1680, 1000, check_map)

        # -- console, equity-adjusted (the money shot) ----------------------
        def flip(page):
            page.click(".switch")
            page.wait_for_timeout(1100)
            if page.get_attribute(".switch", "data-adjusted") != "true":
                failures.append("equity toggle did not flip")

        shoot("console-adjusted", "/console", 1680, 1000, flip)

        # -- drilldown ------------------------------------------------------
        def drill(page):
            page.click(".switch")
            page.wait_for_timeout(700)
            items = page.locator(".rank-item")
            for i in range(min(items.count(), 40)):
                page.locator(".rank-item").nth(i).click()
                page.wait_for_timeout(450)
                if page.locator(".outreach").count():
                    return
                page.keyboard.press("Escape")
                page.locator(".close-x").click()
                page.wait_for_timeout(180)
            # fall back to any district
            page.locator(".rank-item").first.click()
            page.wait_for_timeout(500)
            if page.locator(".drawer").count() == 0:
                failures.append("drilldown drawer did not open")

        shoot("console-dossier", "/console", 1680, 1000, drill)

        # -- roads sector, showing its caveat in the calibration strip -------
        # Replaces console-roads-nodata.png, which documented a gap that closed on
        # 18 Aug 2026. The frame now exists to show the opposite: the sector is
        # loaded AND its state-coding limitation is disclosed on screen.
        def roads(page):
            page.click("text=Roads & Transport")
            page.wait_for_timeout(1800)
            if page.locator(".strip-item.caveat").count() == 0:
                failures.append("roads caveat missing from the calibration strip")
            if page.locator(".rank-item").count() < 10:
                failures.append("roads ranking did not populate")

        shoot("console-roads-caveat", "/console", 1680, 1000, roads)

        # -- landing page ---------------------------------------------------
        # New in the 17 Aug revision: "/" is the landing page and the console
        # moved to /console. A submission deck that has no shot of the first page
        # an evaluator lands on is missing its own front door.
        def landing(page):
            if page.locator(".lp-h1").count() == 0:
                failures.append("landing hero absent")
            if page.locator(".lp-cell.is-silent").count() == 0:
                failures.append("landing quadrant matrix absent")

        shoot("landing", "/", 1680, 1000, landing)

        # -- citizen intake, mobile -----------------------------------------
        def intake(page):
            if page.locator(".mic").count() == 0:
                failures.append("intake mic absent")

        shoot("intake-mobile", "/report", 430, 932, intake)

        def intake_result(page):
            page.click("text=Type it")
            page.fill("textarea.say", "आमच्या वाडीतला हातपंप पाच महिन्यांपासून कोरडा आहे")
            page.click(".send")
            page.wait_for_timeout(700)
            if page.locator(".result").count() == 0:
                failures.append("intake result did not render")

        shoot("intake-result", "/report", 430, 932, intake_result)

        def profile(page):
            if page.locator("#organisation").count() == 0:
                failures.append("profile form did not render")
            page.fill("#organisation", "Ministry of Jal Shakti")
            page.select_option("#role", "District officer")
            page.wait_for_timeout(500)

        shoot("profile", "/profile", 1280, 900, profile)

        browser.close()

    if failures:
        console.print("\n[red]FAILURES[/red]")
        for f in failures:
            console.print(f"  · {f}")
        sys.exit(1)
    console.print(f"\n[green]All frames rendered[/green] → {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    typer.run(main)
