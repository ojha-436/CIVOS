# The CIVOS introduction film — how it is made, and how to change it

A 2:18 launch film that explains what CIVOS is, what problem it solves, and how
the two sides of it are used. Rendered from this folder; no external video
service, no editing timeline, no HeyGen account.

**Output:** `video/out/civos-launch.mp4` — 1920×1080, 30 fps, narration by
Google Cloud Chirp3-HD.

---

## In plain language

A normal video editor is a timeline you drag things around on. This is not that.
Here the film is a **program**, and every part of it is generated:

1. **The words come first.** `video/script.json` holds the narration, split into
   ten scenes. It is the only file you edit to change what the film *says*.
2. **A voice reads it.** `narrate.py` sends each scene's text to Google Cloud
   Text-to-Speech and gets back a WAV. It then *measures* how long each WAV
   actually is and writes those lengths to `timings.json`.
3. **The animation reads those lengths.** `stage.html` is a web page that draws
   the whole film, but only ever for one instant at a time: you call
   `SEEK(37.5)` and it draws what second 37.5 looks like. It gets its scene
   boundaries from `timings.json`.
4. **A robot photographs it 4 131 times.** `render.py` opens that page in a real
   browser and, for every frame, calls `SEEK` and takes a screenshot.
5. **ffmpeg glues it together.** `assemble.py` stitches the frames to the
   narration, normalises the loudness, and writes the MP4 and the captions.

The reason for the odd middle step — *measure the audio, then draw to it* — is
that it makes narration and picture impossible to desynchronise. If you rewrite a
sentence and it takes 1.4 seconds longer to say, every scene after it shifts
automatically. Nobody has to nudge anything.

The second reason the animation is a pure function of time is repeatability. No
CSS transitions, no `requestAnimationFrame`, no `Math.random` at draw time. Frame
2 471 is identical on every run, on any machine. A screen recording could never
promise that.

---

## Changing things

| You want to change | Edit | Then run |
|---|---|---|
| What is said | `script.json` → `vo` | `narrate.py`, `render.py`, `assemble.py` |
| The voice | `narrate.py --voice <name>` | same three |
| Pacing / pauses | `script.json` → `pad` (seconds of silence after a scene) | same three |
| How a scene looks | `stage.html`, the scene's `render()` | `render.py`, `assemble.py` |
| Which UI is shown | `crops.py` boxes, or re-shoot | `crops.py`, `render.py`, `assemble.py` |

```bash
uv run python scripts/video/narrate.py --preview     # audition four voices
uv run python scripts/video/narrate.py               # full narration + timings
uv run python scripts/video/shoot_intake.py          # re-shoot live intake
uv run python scripts/video/crops.py                 # re-cut the UI crops
uv run python scripts/video/render.py --probe 5,42,96 # eyeball three moments
uv run python scripts/video/render.py                # all frames (~35 min)
uv run python scripts/video/assemble.py --bed        # mux, caption, encode

uv run python scripts/video/render.py --captions     # a 2nd pass, hard captions
uv run python scripts/video/assemble.py --subs       # …then encode that pass
```

### Captions

`civos-launch.mp4` carries the captions as a **soft subtitle track** (`mov_text`)
plus a `.srt` sidecar, so a viewer can switch them on and a viewer with sound on
is not made to read them.

Hard-burnt captions need a second frame render. That is not laziness: the local
ffmpeg is built without **libass** and without **libfreetype**, so it has neither
the `subtitles` nor the `drawtext` filter and physically cannot draw text. The
stage draws them instead — which is the better result anyway, because they come
out in IBM Plex on the film's own ground instead of libass's defaults.

To scrub the animation by hand, open `video/stage.html` in a browser: there is a
slider along the bottom and the arrow keys step one frame at a time.

---

## What is real in the film, and what is not

The film shows the deployed product, not mock-ups. Every screenshot is a crop of
`civos-console` on Cloud Run, and the citizen-intake frame is a live
`gemini-2.5-flash` round-trip captured by `shoot_intake.py` — the on-screen
"Live Gemini Extraction" note is the console's own.

Where something is *not* observed data, the frame says so, because the console
labels its own provenance and a film about it should not be less careful:

- **Scene 02** (the bar comparison) is tagged `SCHEMATIC · THE SHAPE OF THE
  PROBLEM`. It illustrates the argument; the numbers are not districts.
- **Scene 06** carries the console's provenance split: deficit values and
  boundaries are real (NFHS-5, 639/641 districts); **citizen signals are a
  synthetic fixture with a deliberate participation bias**.
- **Scene 09**'s curve is tagged `SCHEMATIC · THE LOOP, NOT OBSERVED DATA`,
  because VERIFY runs after money is spent and no post-funding data exists yet.

Claims checked against the repo before they were said on camera: 641 districts
and 5 sectors (`adapters/in/sectors.yaml`); 10 schemes (`schemes.yaml`); 22
Scheduled Languages (`languages.yaml`); 196 typed / 56 full-voice languages
(`docs/LANGUAGE-COVERAGE.md`, which measures the tiers separately — the film
quotes both rather than merging them); Karimganj's 59 signals, 17 needs, 6
languages, 38.1% and Jal Jeevan Mission (the shipped dossier).

One claim was **cut** for being untrue: an earlier draft said the build fails if
anyone hardcodes "India" into `core/`. `scripts/lint_country_literals.py` exists
and passes, but `.github/workflows/deploy.yml` does not run it — `plan.md` §6.1
still lists that wiring as outstanding. The film says only that `core/` is
scanned and passes.

The repo briefly overstated the same thing in seven places, was corrected to
"checked", and then — once the lint was actually wired into
`.github/workflows/deploy.yml` as the `Country lint (SPEC P0-14)` job on
21 Aug 2026 — restored to "enforced", which is now true. **The film's line was
written under the old, weaker state and is still correct but now understated:**
re-recording scene 09 could say the build fails, not merely that core/ is
scanned. Edit `video/script.json` → `09-verify` and the `lint` string in
`stage.html` if you want to claim the stronger version.

---

## Files

```
video/
  script.json        narration, ten scenes — the source of truth for words
  timings.json/.js   measured audio lengths, written by narrate.py
  stage.html         the animation: SEEK(t) draws the film at instant t
  assets/ui/         crops of the live console + the live intake shot
  assets/grain.png   256px tileable grain, stops the near-black banding
  out/vo/            one WAV per scene, plus voice previews
  out/frames/        the PNG sequence
  out/probes/        single-frame spot checks
scripts/video/
  narrate.py  crops.py  shoot_intake.py  render.py  assemble.py
```
