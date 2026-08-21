"""Synthesise the launch-video narration with Google Cloud Chirp3-HD.

One WAV per scene, not one for the whole film. The animation timeline is then
built from the *measured* audio length of each scene, so narration and motion
cannot drift apart — which is the failure mode of writing durations by hand.

Usage:
    uv run python scripts/video/narrate.py
    uv run python scripts/video/narrate.py --voice en-IN-Chirp3-HD-Charon
    uv run python scripts/video/narrate.py --preview      # scene 1 in 4 voices
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VIDEO = REPO / "video"
OUT = VIDEO / "out" / "vo"
ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
PROJECT = "civos-in"

# Candidates for the --preview pass. All en-IN Chirp3-HD; the choice is a
# judgement call about tone, and a human has to actually hear them.
PREVIEW_VOICES = [
    "en-IN-Chirp3-HD-Achernar",
    "en-IN-Chirp3-HD-Vindemiatrix",
    "en-IN-Chirp3-HD-Charon",
    "en-IN-Chirp3-HD-Alnilam",
]


def token() -> str:
    return subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def synth(text: str, voice: str, rate: float, tok: str) -> bytes:
    body = json.dumps({
        "input": {"text": text},
        "voice": {"languageCode": "-".join(voice.split("-")[:2]), "name": voice},
        # LINEAR16 at 24k: the master track stays lossless until the single
        # AAC encode at assembly. Re-encoding narration twice is audible.
        "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000,
                        "speakingRate": rate},
    }).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Authorization": f"Bearer {tok}",
                 "x-goog-user-project": PROJECT,
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return base64.b64decode(json.load(r)["audioContent"])
    except urllib.error.HTTPError as e:
        sys.exit(f"TTS failed ({e.code}) for {voice}:\n{e.read().decode()[:600]}")


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return round(float(out), 3)


def pad(src: Path, dst: Path, seconds: float) -> None:
    """Append trailing silence so a scene can hold after its last word."""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
         "-af", f"apad=pad_dur={seconds}", "-c:a", "pcm_s16le", str(dst)],
        check=True,
    )


def main() -> None:
    args = sys.argv[1:]
    script = json.loads((VIDEO / "script.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    tok = token()
    rate = 1.0
    if "--rate" in args:
        rate = float(args[args.index("--rate") + 1])

    if "--preview" in args:
        line = script["scenes"][0]["vo"]
        for v in PREVIEW_VOICES:
            p = OUT / f"preview-{v}.wav"
            p.write_bytes(synth(line, v, rate, tok))
            print(f"  {p.relative_to(REPO)}  ({duration(p)}s)")
        print("\nListen, then re-run with --voice <name>.")
        return

    voice = script["voice"]
    if "--voice" in args:
        voice = args[args.index("--voice") + 1]
        script["voice"] = voice
        (VIDEO / "script.json").write_text(
            json.dumps(script, indent=2, ensure_ascii=False) + "\n")

    timings, cursor = [], 0.0
    for i, s in enumerate(script["scenes"], 1):
        raw = OUT / f"{s['id']}.raw.wav"
        final = OUT / f"{s['id']}.wav"
        raw.write_bytes(synth(s["vo"], voice, rate, tok))
        speech = duration(raw)
        pad(raw, final, s["pad"])
        raw.unlink()
        dur = duration(final)
        timings.append({"id": s["id"], "label": s["label"], "start": round(cursor, 3),
                        "dur": dur, "speech": speech, "vo": s["vo"]})
        cursor += dur
        print(f"  {i:02d} {s['id']:<12} speech {speech:6.2f}s  +pad {s['pad']}  = {dur:6.2f}s")

    fps = script["fps"]
    meta = {"voice": voice, "rate": rate, "fps": fps,
            "width": script["width"], "height": script["height"],
            "total": round(cursor, 3), "frames": int(round(cursor * fps)),
            "scenes": timings}
    (VIDEO / "timings.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    # Also as a plain script tag. A file:// page cannot fetch() a sibling JSON
    # (CORS), and stage.html has to be openable straight from Finder for preview.
    (VIDEO / "timings.js").write_text(
        "window.TIMINGS = " + json.dumps(meta, indent=2, ensure_ascii=False) + ";\n")
    print(f"\n  voice   {voice}")
    print(f"  runtime {cursor:.2f}s  ({int(cursor // 60)}:{cursor % 60:04.1f})  "
          f"= {meta['frames']} frames @ {fps}fps")
    print(f"  wrote   video/timings.json + timings.js")


if __name__ == "__main__":
    main()
