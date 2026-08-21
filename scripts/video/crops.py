"""Cut the callout crops the video needs out of the live-app screenshots.

The screenshots in docs/screenshots are 2x device-scale shots of the deployed
Cloud Run console, so a crop of one is real product UI, not a mock-up. Doing the
crops here (rather than with CSS background offsets in the stage) keeps the
coordinates in one reviewable place and lets them be eyeballed as files.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
SHOTS = REPO / "docs" / "screenshots"
OUT = REPO / "video" / "assets" / "ui"

# Boxes are in the native pixels of each 2x screenshot (console shots are
# 3360x2000). left, top, right, bottom.
CROPS = {
    "console-dossier.png": {
        "dossier-head":     (34, 590, 2554, 730),
        "dossier-priority": (34, 770, 950, 1360),
        "dossier-signals":  (960, 775, 1740, 1290),
        "dossier-deficit":  (1780, 820, 2545, 1165),
        "dossier-funding":  (1780, 1245, 2545, 1625),
        "dossier-callout":  (1780, 1672, 2545, 1895),
    },
    "console-adjusted.png": {
        "quadrant-legend":  (60, 1512, 795, 1878),
        "console-map":      (0, 165, 2575, 2000),
        "console-rail":     (2590, 165, 3360, 1750),
        "console-mast":     (0, 0, 3360, 165),
    },
    "intake-result.png": {
        "intake-phone":     (0, 0, 860, 1864),
    },
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for src, boxes in CROPS.items():
        im = Image.open(SHOTS / src)
        for name, box in boxes.items():
            if box[2] > im.width or box[3] > im.height:
                raise SystemExit(f"{name}: box {box} outside {src} {im.size}")
            crop = im.crop(box)
            crop.save(OUT / f"{name}.png")
            print(f"  {name:<18} {crop.width}x{crop.height}")


if __name__ == "__main__":
    main()
