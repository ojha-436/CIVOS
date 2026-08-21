"""Assemble the rendered frames and per-scene narration into the finished film.

Produces, in video/out/:
    civos-launch.mp4          the film — narration only
    civos-launch.srt          sidecar captions (also embedded as a soft
                              subtitle track inside the MP4, toggleable in any
                              player — this ffmpeg has no libass, so hard-burnt
                              captions come from render.py --captions instead)
    civos-launch-subs.mp4     hard captions (needs: render.py --captions)
    civos-launch-bed.mp4      narration plus a very quiet synthesised drone
                              (--bed; generated so it can be auditioned, not
                              because a bed is assumed to be wanted)

Usage:
    uv run python scripts/video/assemble.py
    uv run python scripts/video/assemble.py --bed --subs
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VIDEO = REPO / "video"
OUT = VIDEO / "out"
FRAMES = OUT / "frames"
VO = OUT / "vo"


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"$ {' '.join(cmd[:8])} …\n{r.stderr[-1800:]}")


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def cues(T: dict) -> list[tuple[float, float, str]]:
    """Split each scene's narration into caption-sized chunks.

    Time inside a scene is apportioned by character count. That is an
    approximation — Chirp3-HD gives no word timings — but it tracks a steady
    reading rate closely enough that captions never lag a sentence behind.
    """
    out: list[tuple[float, float, str]] = []
    for sc in T["scenes"]:
        parts = [p.strip() for p in re.split(r"(?<=[.?!])\s+", sc["vo"]) if p.strip()]
        # Fold very short fragments into the previous cue rather than flashing them.
        merged: list[str] = []
        for p in parts:
            if merged and (len(p) < 28 or len(merged[-1]) < 28):
                merged[-1] = f"{merged[-1]} {p}"
            else:
                merged.append(p)
        total = sum(len(p) for p in merged) or 1
        t = sc["start"]
        for p in merged:
            d = sc["speech"] * len(p) / total
            out.append((t, t + d, p))
            t += d
    return out


def wrap(text: str, width: int = 44) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines[:3])


def main() -> None:
    args = sys.argv[1:]
    T = json.loads((VIDEO / "timings.json").read_text())
    fps, total = T["fps"], T["total"]

    n = len(list(FRAMES.glob("f*.png")))
    if n < T["frames"]:
        sys.exit(f"only {n}/{T['frames']} frames in {FRAMES} — run render.py first")
    print(f"  {n} frames · {total:.2f}s · voice {T['voice']}")

    # ── narration: concat the per-scene WAVs, then one loudness pass ────────
    lst = OUT / "_vo.txt"
    lst.write_text("".join(f"file '{(VO / (s['id'] + '.wav')).as_posix()}'\n"
                           for s in T["scenes"]))
    raw, nar = OUT / "_narration-raw.wav", OUT / "narration.wav"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(raw)])
    # TTS comes out well below broadcast level; -16 LUFS is the streaming target
    # and keeps the film from being the quiet tab in a reviewer's browser.
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "pcm_s16le", str(nar)])
    print(f"  narration → {nar.relative_to(REPO)}")

    # ── captions ───────────────────────────────────────────────────────────
    srt = OUT / "civos-launch.srt"
    srt.write_text("".join(
        f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{wrap(txt)}\n\n"
        for i, (a, b, txt) in enumerate(cues(T), 1)))
    print(f"  captions  → {srt.relative_to(REPO)} ({len(cues(T))} cues)")

    V = ["-framerate", str(fps), "-i", str(FRAMES / "f%06d.png")]
    # crf 17 + slow: the ground is near-black with 1px hairlines, and anything
    # cheaper smears the rules and bands the vignette.
    ENC = ["-c:v", "libx264", "-preset", "slow", "-crf", "17",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           "-c:a", "aac", "-b:a", "192k", "-shortest"]

    main_out = OUT / "civos-launch.mp4"
    # Two steps, deliberately. Muxing the .srt into the SAME command as the encode
    # deadlocks: -shortest waits for every input to signal EOF, and a subtitle
    # stream is sparse — with no packet due for seconds at a time, ffmpeg sleeps
    # forever at 0% CPU rather than finishing. So encode picture + sound first,
    # then attach the caption track in a copy-only pass (fast, and -shortest is
    # not needed once the durations already match).
    tmp = OUT / "_av.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", *V, "-i", str(nar), *ENC, str(tmp)])
    # mov_text rather than a burnt-in overlay: the captions stay switchable, and
    # a viewer with sound on is not made to read them.
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-i", str(srt),
         "-map", "0:v", "-map", "0:a", "-map", "1:0",
         "-c", "copy", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng",
         "-disposition:s:0", "default", "-movflags", "+faststart", str(main_out)])
    tmp.unlink(missing_ok=True)
    print(f"  film      → {main_out.relative_to(REPO)}  (+ soft caption track)")

    if "--subs" in args:
        cf = OUT / "frames-captioned"
        if len(list(cf.glob("f*.png"))) < T["frames"]:
            print("  captioned → skipped: run `render.py --captions` first "
                  "(this ffmpeg has no libass, so the stage draws them)")
        else:
            subs_out = OUT / "civos-launch-subs.mp4"
            run(["ffmpeg", "-y", "-loglevel", "error",
                 "-framerate", str(fps), "-i", str(cf / "f%06d.png"),
                 "-i", str(nar), *ENC, str(subs_out)])
            print(f"  captioned → {subs_out.relative_to(REPO)}")

    if "--bed" in args:
        bed = OUT / "_bed.wav"
        # A drone, not music: three low sines a fifth apart, slow tremolo, rolled
        # off above 700 Hz, sitting ~30 dB under the voice. Included so it can be
        # auditioned against the dry mix — the dry mix is the default.
        run(["ffmpeg", "-y", "-loglevel", "error",
             "-f", "lavfi", "-i", f"sine=frequency=55:duration={total:.3f}",
             "-f", "lavfi", "-i", f"sine=frequency=82.4:duration={total:.3f}",
             "-f", "lavfi", "-i", f"sine=frequency=110:duration={total:.3f}",
             "-filter_complex",
             "[0:a]volume=0.55[a];[1:a]volume=0.30[b];[2:a]volume=0.22[c];"
             "[a][b][c]amix=inputs=3:normalize=0,"
             "tremolo=f=0.12:d=0.35,lowpass=f=700,"
             f"afade=t=in:st=0:d=3,afade=t=out:st={total-4:.3f}:d=4,"
             "volume=-30dB[out]",
             "-map", "[out]", "-c:a", "pcm_s16le", str(bed)])
        bed_out = OUT / "civos-launch-bed.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", *V, "-i", str(nar), "-i", str(bed),
             "-filter_complex", "[1:a][2:a]amix=inputs=2:normalize=0:duration=first[a]",
             "-map", "0:v", "-map", "[a]", *ENC, str(bed_out)])
        print(f"  with bed  → {bed_out.relative_to(REPO)}")

    for f in (lst, raw):
        f.unlink(missing_ok=True)

    for f in sorted(OUT.glob("civos-launch*.mp4")):
        d = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration,size", "-of", "csv=p=0:s=,", str(f)],
                           capture_output=True, text=True).stdout.strip().split(",")
        print(f"\n  {f.name:<26} {float(d[0]):.2f}s  {int(d[1])/1e6:.1f} MB")


if __name__ == "__main__":
    main()
