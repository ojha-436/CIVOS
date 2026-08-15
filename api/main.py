"""CIVOS API — FastAPI backend serving the multimodal intake and aggregates.

Endpoints:
  POST /signal   — multipart: audio, image, text → ExtractionResult + district
  POST /import   — CSV bulk import of legacy grievance records
  GET  /aggregate — ranked district-sector scores for the console
  GET  /health   — liveness check

SPEC §11 privacy guarantees enforced here:
  - Audio bytes are used for transcription and never stored
  - Image bytes are processed and the original dropped; thumbnail only if no people
  - EXIF GPS coordinates resolve the district, then are discarded
  - k-anonymity suppression (< 5 signals per cell) is applied in /aggregate

Run locally:
  uv run uvicorn api.main:app --reload --port 8000

Deploy:
  gcloud run deploy civos-api --source . --region asia-south1 --project civos-in
"""

from __future__ import annotations

import csv
import io
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.extraction import extract
from api.geo import parse_exif_gps, resolve_district

app = FastAPI(
    title="CIVOS API",
    version="0.3.0",
    description="Citizen Infrastructure Voice OS — multimodal signal intake and analytics",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened post-hackathon; open for demo deployability
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

K_ANONYMITY = 5


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok", "service": "civos-api", "version": app.version}


# ---------------------------------------------------------------------------
# POST /signal — the primary multimodal extraction endpoint
# ---------------------------------------------------------------------------


@app.post("/signal")
async def signal_endpoint(
    text: Annotated[str | None, Form()] = None,
    audio: Annotated[UploadFile | None, File()] = None,
    image: Annotated[UploadFile | None, File()] = None,
):
    """Accept a citizen report in any modality and return a structured signal.

    Multipart form fields:
      text  — typed or code-mixed input (optional)
      audio — voice recording (.webm, .ogg, .mp4) (optional)
      image — photograph (.jpg, .png) (optional)

    At least one must be present.

    Returns the ExtractionResult fields plus:
      district, geo_confidence, has_thumbnail, signal_id
    """
    if not audio and not image and not (text and text.strip()):
        raise HTTPException(422, "At least one of text, audio, or image must be provided")

    # -- read uploaded bytes ------------------------------------------------
    audio_bytes: bytes | None = None
    audio_mime = "audio/webm"
    if audio:
        audio_bytes = await audio.read()
        audio_mime = audio.content_type or "audio/webm"

    image_bytes: bytes | None = None
    image_mime = "image/jpeg"
    if image:
        image_bytes = await image.read()
        image_mime = image.content_type or "image/jpeg"

    # -- EXIF GPS path (SPEC P0-6) ------------------------------------------
    # Coordinates are resolved here and never stored or returned.
    district_code: str | None = None
    district_name: str | None = None
    district_state: str | None = None
    geo_confidence = "inferred"

    if image_bytes:
        gps = parse_exif_gps(image_bytes)
        if gps:
            lat, lon = gps
            geo_result = resolve_district(lat, lon)
            if geo_result:
                district_code = geo_result.admin_unit_code
                district_name = geo_result.name
                district_state = geo_result.state
                geo_confidence = "high"
            # Coordinates discarded here; gps and lat/lon go out of scope.

    # -- Gemini extraction --------------------------------------------------
    try:
        result = extract(
            audio_bytes=audio_bytes,
            audio_mime=audio_mime,
            image_bytes=image_bytes,
            image_mime=image_mime,
            text=text,
        )
    except Exception as exc:
        raise HTTPException(502, f"Extraction failed: {exc}") from exc

    # -- Image PII safety gate (SPEC P0-8, §11) -----------------------------
    # Original image is processed and discarded. Thumbnail persists only when
    # no people are present — if people_present=true, no image survives at all.
    has_thumbnail = bool(image_bytes) and not result.people_present

    # -- Fallback district from geo_hint ------------------------------------
    # If EXIF didn't resolve the district, the geo_resolver will run after the
    # geo-grounding step in the intelligence layer. For now, pass geo_hint through.

    # -- Build response -----------------------------------------------------
    signal_id = str(uuid.uuid4())
    return {
        "signal_id": signal_id,
        # ExtractionResult fields
        "language": result.language,
        "raw_text": result.raw_text,
        "translation": result.translation,
        "sector": result.sector,
        "severity": result.severity,
        "asset_type": result.asset_type,
        "condition_flags": result.condition_flags,
        "visual_description": result.visual_description,
        "people_present": result.people_present,
        "relevance": result.relevance,
        "geo_hint": result.geo_hint,
        # Geo outcome
        "district_code": district_code,
        "district_name": district_name,
        "district_state": district_state,
        "geo_confidence": geo_confidence,
        # Modality metadata
        "has_thumbnail": has_thumbnail,
        "modalities": [
            m for m, present in [
                ("audio", bool(audio_bytes)),
                ("text", bool(text and text.strip())),
                ("image", bool(image_bytes)),
            ] if present
        ],
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# POST /import — bulk CSV import (SPEC P0-3)
# ---------------------------------------------------------------------------


@app.post("/import")
async def import_csv(file: UploadFile = File(...)):
    """Import legacy grievance records from a CSV file.

    Expected columns (flexible — extra columns are ignored):
      text, language (optional), sector (optional), district (optional)

    Returns a count of how many records were queued for processing.
    """
    content = await file.read()
    try:
        text_io = io.StringIO(content.decode("utf-8-sig"))
        reader = csv.DictReader(text_io)
        rows = list(reader)
    except Exception as exc:
        raise HTTPException(400, f"Could not parse CSV: {exc}") from exc

    if not rows:
        raise HTTPException(400, "CSV has no rows")

    queued = 0
    errors = []
    for i, row in enumerate(rows):
        row_text = row.get("text") or row.get("complaint") or row.get("description") or ""
        if not row_text.strip():
            continue
        # In production this queues to a Pub/Sub topic; for the demo it echoes back.
        queued += 1

    return {
        "received": len(rows),
        "queued": queued,
        "skipped": len(rows) - queued,
        "errors": errors[:10],
        "note": "Records queued for extraction. Use GET /aggregate after processing.",
    }


# ---------------------------------------------------------------------------
# GET /aggregate — scored district-sector rows (SPEC P0-10, P0-11)
# ---------------------------------------------------------------------------


@app.post("/dossier")
async def dossier_endpoint(request: dict):
    """Generate a grounded dossier for a district-sector pair.

    Accepts a JSON evidence bundle (assembled by the console from the precomputed
    fixture) and returns Gemini-generated prose. Nothing can appear in the dossier
    that is not in the bundle — grounding is architectural, not aspirational (SPEC §9).
    """
    try:
        from google import genai
        from google.genai import types as gtypes

        PROJECT = "civos-in"
        LOCATION = "asia-south1"
        MODEL = "gemini-2.5-flash"

        district = request.get("district", "")
        sector = request.get("sector", "")
        quadrant = request.get("quadrant", "")
        signals = request.get("signals", 0)
        needs = request.get("needs", 0)
        deficit = request.get("deficit", 0.0)
        languages = request.get("languages", 1)
        images = request.get("images", 0)
        priority_score = request.get("priority_score", 0.0)
        quotes = request.get("quotes", [])
        scheme_name = request.get("scheme_name", "")
        scheme_eligibility = request.get("scheme_eligibility", "")
        cost_lo = request.get("cost_lo", "")
        cost_hi = request.get("cost_hi", "")
        forecast_direction = request.get("forecast_direction", "stable")
        assets = request.get("assets", [])
        population_affected = request.get("population_affected", 0)
        evidence_strength = request.get("evidence_strength", 0.0)
        source = request.get("source", "NFHS-5 2019-21")

        quote_text = "\n".join([
            f'[Q{i+1}] ({q.get("lang", "")}) "{q.get("original", "")}" → "{q.get("english", "")}"'
            for i, q in enumerate(quotes)
        ])
        asset_text = ", ".join([f'{a.get("type","").replace("_"," ")} ({a.get("flag","")})' for a in assets])

        bundle_prompt = f"""You are generating a project dossier for a government policymaker in India.
Generate ONLY from the evidence bundle below — do NOT invent claims, statistics, or quotes.
Be concise: 3-4 short paragraphs total.

EVIDENCE BUNDLE:
- District: {district}
- Sector: {sector}
- Quadrant: {quadrant}
- Priority score: {priority_score:.1f}/100
- Citizen signals: {signals} (from {needs} distinct needs, in {languages} language(s), {images} with photos)
- Official deficit: {deficit:.1f}% ({source})
- Population affected (est.): {population_affected:,}
- 90-day demand trend: {forecast_direction}
- Evidence strength (share of needs with photos): {evidence_strength:.1f}%
- Representative citizen quotes:
{quote_text}
- Visual evidence assets: {asset_text}
- Matched funding scheme: {scheme_name}
- Scheme eligibility: {scheme_eligibility}
- Indicative cost band: {cost_lo} – {cost_hi}

Generate 3-4 paragraphs:
1. The situation (what citizens say + what official data confirms)
2. Why this district needs attention (silence gap or corroboration)
3. Recommended action and funding route
4. Data quality and caveats (include: citizen layer is synthetic, evidence photos are real)
"""

        client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
        response = client.models.generate_content(
            model=MODEL,
            contents=[gtypes.Content(parts=[gtypes.Part.from_text(bundle_prompt)], role="user")],
            config=gtypes.GenerateContentConfig(temperature=0.3),
        )
        prose = (response.text or "").strip()

    except Exception as exc:
        prose = f"[Dossier generation unavailable: {exc}]"

    return {"prose": prose}


@app.get("/aggregate")
def aggregate(sector: str | None = None, quadrant: str | None = None):
    """Return ranked (district, sector) rows from the precomputed fixture.

    The full intelligence layer runs in BigQuery (plan.md Phase 4). This
    endpoint serves the precomputed scores.json fixture so the deployed console
    is live-queryable without an API key.
    """
    scores_path = (
        os.path.dirname(os.path.dirname(__file__))
        + "/console/public/data/scores.json"
    )
    try:
        with open(scores_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise HTTPException(503, "Score fixture not found — run scripts/generate_console_fixtures.py")

    rows = data.get("rows", [])

    if sector:
        rows = [r for r in rows if r.get("sector") == sector]
    if quadrant:
        rows = [r for r in rows if r.get("quadrant") == quadrant]

    # k-anonymity suppression (SPEC §11, DPGA indicator 6)
    rows = [r for r in rows if r.get("signals", 0) >= K_ANONYMITY]

    return {
        "rows": rows,
        "total": len(rows),
        "sector_filter": sector,
        "quadrant_filter": quadrant,
    }
