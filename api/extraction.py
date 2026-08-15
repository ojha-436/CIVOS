"""Gemini multimodal extraction — the single call that handles audio, text and image.

One call, not three pipelines. `parts` carries any combination of audio bytes,
text, and image bytes; the model returns one validated ExtractionResult.
This is what makes adding the image modality cheap (plan.md §3.2).

Gate 0 confirmed that `gemini-2.5-flash` is available in asia-south1 via
`AI.GENERATE` inline. For the extraction call we use the Vertex AI python SDK
directly so audio and image content never leaves the GCP project boundary.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from google import genai
from google.genai import types as gtypes

from core.models.signal import ConditionFlag, ExtractionResult

PROJECT = "civos-in"
LOCATION = "asia-south1"
MODEL = "gemini-2.5-flash"

SECTOR_KEYS = [
    "water_sanitation",
    "roads_transport",
    "electricity",
    "health",
    "education",
]
ASSET_TYPES = [
    "handpump", "borewell", "standpost", "toilet_block", "drain", "overhead_tank",
    "road_surface", "culvert", "bridge", "bus_stop", "footpath",
    "transformer", "pole", "street_light", "service_line", "feeder",
    "phc_building", "sub_centre", "ambulance_access_road", "waiting_area",
    "school_building", "classroom", "boundary_wall", "school_toilet", "playground",
]
CONDITION_FLAGS = ["structurally_unsafe", "standing_water", "unusable", "partially_functional"]

SYSTEM_PROMPT = f"""You are the extraction engine for CIVOS, a civic infrastructure
reporting system serving BRICS governments.

From the provided audio, text and/or image, extract exactly the following JSON:

{{
  "language": "<BCP-47 language code auto-detected from input — do NOT ask the citizen>",
  "raw_text": "<transcript or typed text in the original language; empty string for image-only>",
  "translation": "<English normalisation; empty string for image-only>",
  "sector": "<one of {SECTOR_KEYS} or null>",
  "severity": <integer 1-5 where 1=cosmetic, 5=dangerous or absent infrastructure; null if unclear>,
  "asset_type": "<one of {ASSET_TYPES} or null>",
  "condition_flags": [<zero or more of {CONDITION_FLAGS}>],
  "visual_description": "<factual one-sentence caption for images; null for text/audio-only>",
  "people_present": <true if human faces or identifiable people appear in an image; false otherwise>,
  "relevance": <true if this concerns civic infrastructure; false for selfies, food, unrelated content>,
  "geo_hint": "<verbatim place name or description if the citizen mentions one; null otherwise>"
}}

Rules that must be followed:
1. Auto-detect language from audio/text. Code-mixing (Hindi+English, Marathi+Hindi) is normal — handle it natively.
2. For image-only submissions set language="none", raw_text="", translation="".
3. Return ONLY valid JSON. No explanation, no markdown, no extra fields.
4. If no sector can be determined, set sector to null. Do not guess wildly.
5. geo_hint must be the citizen's exact words — never an inference or a corrected name.
"""

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    return _client


def extract(
    *,
    audio_bytes: bytes | None = None,
    audio_mime: str = "audio/webm",
    image_bytes: bytes | None = None,
    image_mime: str = "image/jpeg",
    text: str | None = None,
) -> ExtractionResult:
    """Call Gemini once and return a validated ExtractionResult.

    Any combination of the three inputs is accepted — none, one, or all three.
    Raises ValueError if nothing is provided.
    """
    if not audio_bytes and not image_bytes and not (text and text.strip()):
        raise ValueError("At least one of audio_bytes, image_bytes, or text must be provided")

    parts: list[gtypes.Part] = []

    if audio_bytes:
        parts.append(
            gtypes.Part.from_bytes(data=audio_bytes, mime_type=audio_mime)
        )

    if image_bytes:
        parts.append(
            gtypes.Part.from_bytes(data=image_bytes, mime_type=image_mime)
        )

    if text and text.strip():
        parts.append(gtypes.Part.from_text(text=text.strip()))

    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=[gtypes.Content(parts=parts, role="user")],
        config=gtypes.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.0,
        ),
    )

    raw_json = (response.text or "").strip()
    # Strip any accidental markdown fences the model might add.
    raw_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_json, flags=re.S).strip()

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini returned non-JSON: {raw_json[:500]}") from exc

    # Normalise condition_flags to ConditionFlag enum values; drop unrecognised ones.
    raw_flags = data.get("condition_flags") or []
    valid_flags = {f.value for f in ConditionFlag}
    data["condition_flags"] = [f for f in raw_flags if f in valid_flags]

    return ExtractionResult.model_validate(data)
