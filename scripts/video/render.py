"""Render video/stage.html to a PNG frame sequence by seeking, not recording.

Screen-recording a page gives you whatever frames the compositor felt like
emitting. Here the renderer drives time itself: SEEK(t) for t = 0, 1/fps, 2/fps …
and screenshots each result. Deterministic, exactly fps frames per second, and a
dropped frame is impossible.

Usage:
    uv run python scripts/video/render.py                    # the whole film
    uv run python scripts/video/render.py --probe 0,6,20,70  # just those seconds
    uv run python scripts/video/render.py --scene 08-dossier # one scene
    uv run python scripts/video/render.py --sheet 24         # contact sheet
    uv run python scripts/video/render.py --captions         # burnt-in captions
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
VIDEO = REPO / "video"
FRAMES = VIDEO / "out" / "frames"
PROBES = VIDEO / "out" / "probes"


def launch(pw):
    # Same reasoning as scripts/shoot_console.py: prefer the installed Chrome,
    # because Playwright's bundled chromium goes missing on package upgrades.
    try:
        return pw.chromium.launch(channel="chrome")
    except Exception:
        return pw.chromium.launch()


def open_stage(pw, T, captions=False):
    browser = launch(pw)
    page = browser.new_page(
        viewport={"width": T["width"], "height": T["height"]},
        device_scale_factor=1,
    )
    errs: list[str] = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append(f"console.{m.type}: {m.text}")
            if m.type == "error" else None)
    # Suppresses the interactive scrubber and the keyboard handler.
    page.add_init_script("window.__RENDERING = true;")
    if captions:
        # This ffmpeg build has no libass and no libfreetype, so hard captions
        # cannot come from the encoder. The stage draws them instead, in the
        # film's own type — which is the better result anyway.
        page.add_init_script("window.__CAPTIONS = true;")
    page.goto((VIDEO / "stage.html").as_uri(), wait_until="load")

    # Fonts and every crop must be decoded before frame 0, or the first second
    # of the film renders in a fallback face at the wrong metrics.
    page.wait_for_function("document.fonts && document.fonts.status === 'loaded'", timeout=30000)
    page.wait_for_function(
        "Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)",
        timeout=30000)
    page.wait_for_timeout(350)

    if errs:
        browser.close()
        sys.exit("stage.html raised:\n  " + "\n  ".join(errs[:6]))
    return browser, page, errs


def main() -> None:
    args = sys.argv[1:]
    T = json.loads((VIDEO / "timings.json").read_text())
    fps = T["fps"]

    def arg(flag, cast=str, default=None):
        return cast(args[args.index(flag) + 1]) if flag in args else default

    with sync_playwright() as pw:
        captions = "--captions" in args
        browser, page, errs = open_stage(pw, T, captions)
        shot = page.locator("#stage")

        # ---- probe: a handful of timestamps, for eyeballing -----------------
        if "--probe" in args or "--sheet" in args:
            PROBES.mkdir(parents=True, exist_ok=True)
            for f in PROBES.glob("*.png"):
                f.unlink()
            if "--sheet" in args:
                n = arg("--sheet", int, 24)
                times = [T["total"] * i / n for i in range(n)]
            else:
                times = [float(x) for x in arg("--probe").split(",")]
            for t in times:
                page.evaluate(f"SEEK({t})")
                shot.screenshot(path=str(PROBES / f"t{t:07.2f}.png"))
                print(f"  probe {t:7.2f}s")
            if errs:
                print("\n  JS errors:", *errs[:6], sep="\n   ")
            browser.close()
            return

        # ---- full sequence --------------------------------------------------
        scene = arg("--scene")
        if scene:
            s = next((x for x in T["scenes"] if x["id"] == scene), None)
            if not s:
                sys.exit(f"no scene {scene}; have {[x['id'] for x in T['scenes']]}")
            t0, t1 = s["start"], s["start"] + s["dur"]
            out = VIDEO / "out" / f"frames-{scene}"
        else:
            t0, t1 = 0.0, T["total"]
            out = (VIDEO / "out" / "frames-captioned") if captions else FRAMES

        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True, exist_ok=True)

        n0, n1 = int(round(t0 * fps)), int(round(t1 * fps))
        total = n1 - n0
        started = time.time()
        for i, n in enumerate(range(n0, n1)):
            page.evaluate(f"SEEK({n / fps})")
            shot.screenshot(path=str(out / f"f{n:06d}.png"))
            if i and i % 120 == 0:
                el = time.time() - started
                print(f"  {i}/{total}  {el:.0f}s elapsed  "
                      f"~{el / i * (total - i):.0f}s left", flush=True)
        el = time.time() - started
        print(f"  {total} frames in {el:.0f}s ({total / el:.1f} fps) → "
              f"{out.relative_to(REPO)}")
        if errs:
            print("\n  JS errors during render:", *errs[:6], sep="\n   ")
        browser.close()


if __name__ == "__main__":
    main()
