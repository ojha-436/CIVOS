"""Unit tests for the CIVOS FastAPI backend (api/main.py, api/geo.py).

Verifies endpoints, district resolution math, and EXIF GPS parsing.
Uses unittest.mock to isolate Gemini extraction calls, ensuring zero billing cost.
"""

from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.geo import resolve_district, parse_exif_gps
from api.main import app
from core.models.signal import ExtractionResult, ConditionFlag

client = TestClient(app)


# ---------------------------------------------------------------------------
# api/geo.py tests
# ---------------------------------------------------------------------------

def test_resolve_district_valid():
    """Verify that coordinates inside Nashik are correctly resolved."""
    # Nashik is approximately at (19.9975, 73.7898)
    res = resolve_district(19.9975, 73.7898)
    assert res is not None
    assert res.admin_unit_code == "IN-MH-nashik"
    assert res.name == "Nashik"
    assert res.state == "Maharashtra"
    assert res.confidence == "high"


def test_resolve_district_invalid():
    """Verify that coordinates outside India (e.g. 0, 0) return None."""
    res = resolve_district(0.0, 0.0)
    assert res is None


def test_parse_exif_gps_no_exif():
    """Verify parse_exif_gps returns None when image has no EXIF."""
    # Create a 10x10 blank image in memory without EXIF
    img_byte_arr = io.BytesIO()
    img = Image.new("RGB", (10, 10), color="red")
    img.save(img_byte_arr, format="JPEG")
    img_bytes = img_byte_arr.getvalue()

    res = parse_exif_gps(img_bytes)
    assert res is None


# ---------------------------------------------------------------------------
# api/main.py endpoint tests
# ---------------------------------------------------------------------------

def test_health_endpoint():
    """Verify that the /health endpoint is alive and returns status=ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "civos-api"


def test_aggregate_endpoint():
    """Verify GET /aggregate successfully serves precomputed scores."""
    response = client.get("/aggregate?sector=water_sanitation")
    assert response.status_code == 200
    data = response.json()
    assert "rows" in data
    assert "total" in data
    assert data["sector_filter"] == "water_sanitation"
    if data["rows"]:
        # Verify k-anonymity constraint: no rows should have less than K_ANONYMITY (5) signals
        for row in data["rows"]:
            assert row["signals"] >= 5


def test_import_endpoint():
    """Verify POST /import accepts a legacy CSV and returns correct queues."""
    csv_content = (
        "id,text,sector,district\n"
        "1,The borehole here is dry and broken,water_sanitation,Nashik\n"
        "2,No power line,electricity,Pune\n"
        "3,,empty text,,\n"
    )
    file_bytes = csv_content.encode("utf-8")
    
    response = client.post(
        "/import",
        files={"file": ("legacy.csv", file_bytes, "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 3
    assert data["queued"] == 2  # Row 3 is empty and skipped
    assert "note" in data


@patch("api.main.extract")
def test_signal_endpoint_multimodal(mock_extract):
    """Verify POST /signal handles multimodal form fields and integrates with mock Gemini."""
    # Define the mock ExtractionResult
    mock_result = ExtractionResult(
        language="mr-IN",
        raw_text="आमच्या गावात हातपंप बंद आहे.",
        translation="The handpump in our village is broken.",
        sector="water_sanitation",
        severity=4,
        asset_type="handpump",
        condition_flags=[ConditionFlag.UNUSABLE],
        visual_description="A broken metal handpump with standing water.",
        people_present=False,
        relevance=True,
        geo_hint="Nashik"
    )
    mock_extract.return_value = mock_result

    # Form inputs
    form_data = {"text": "आमच्या गावात हातपंप बंद आहे."}
    
    # Mock files
    audio_file = ("voice.webm", b"mock audio bytes", "audio/webm")
    image_file = ("photo.jpg", b"mock image bytes", "image/jpeg")

    response = client.post(
        "/signal",
        data=form_data,
        files={"audio": audio_file, "image": image_file}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["signal_id"] is not None
    assert data["language"] == "mr-IN"
    assert data["sector"] == "water_sanitation"
    assert data["severity"] == 4
    assert data["condition_flags"] == ["unusable"]
    assert "audio" in data["modalities"]
    assert "image" in data["modalities"]
    assert "text" in data["modalities"]
    assert data["has_thumbnail"] is True


def test_signal_endpoint_empty_error():
    """Verify POST /signal fails with 422 if no input field is provided."""
    response = client.post("/signal")
    assert response.status_code == 422
