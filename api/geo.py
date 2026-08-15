"""EXIF GPS extraction and district resolution via spatial containment.

SPEC P0-6: When a submitted photo carries GPS EXIF, coordinates resolve via
ST_CONTAINS and the signal is flagged geo_confidence=high, bypassing inference.

SPEC §11 / DPGA indicator 7: The coordinate is used once to work out the district,
then discarded. Nothing in the API response or the warehouse carries a citizen's
precise location — admin unit only.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from PIL import Image
import io


class GeoResult(NamedTuple):
    admin_unit_code: str
    name: str
    state: str
    confidence: str  # 'high' (EXIF) or 'inferred' (text)


_GEOJSON_PATH = (
    Path(__file__).resolve().parent.parent
    / "console" / "public" / "data" / "districts.geojson"
)


@lru_cache(maxsize=1)
def _load_features() -> list[dict]:
    """Load district features once. The GeoJSON has simplified polygons — fast."""
    with open(_GEOJSON_PATH) as f:
        gj = json.load(f)
    return gj["features"]


def _point_in_polygon_ray(px: float, py: float, ring: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon for a single ring (exterior or hole)."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _contains(geometry: dict, lon: float, lat: float) -> bool:
    """True if (lon, lat) is inside the GeoJSON geometry (Polygon or MultiPolygon)."""
    gtype = geometry.get("type", "")
    coords = geometry.get("coordinates", [])

    if gtype == "Polygon":
        if not _point_in_polygon_ray(lon, lat, coords[0]):
            return False
        for hole in coords[1:]:
            if _point_in_polygon_ray(lon, lat, hole):
                return False
        return True

    if gtype == "MultiPolygon":
        for poly in coords:
            if _contains({"type": "Polygon", "coordinates": poly}, lon, lat):
                return True
    return False


def resolve_district(lat: float, lon: float) -> GeoResult | None:
    """Return the district containing (lat, lon), or None if outside all boundaries."""
    for feat in _load_features():
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        if _contains(geom, lon, lat):
            return GeoResult(
                admin_unit_code=str(props.get("code", props.get("district_code", ""))),
                name=str(props.get("district", props.get("name", ""))),
                state=str(props.get("state_name", props.get("state", ""))),
                confidence="high",
            )
    return None


def parse_exif_gps(image_bytes: bytes) -> tuple[float, float] | None:
    """Return (lat, lon) from EXIF GPS, or None if absent or malformed.

    The coordinates are used once to resolve the district and then discarded —
    they must never be stored or returned to the caller.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif_data = img._getexif()  # type: ignore[attr-defined]
        if not exif_data:
            return None

        from PIL.ExifTags import TAGS, GPSTAGS

        gps_info: dict = {}
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for gps_tag_id, gps_val in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag] = gps_val

        if not gps_info:
            return None

        def _dms_to_dd(dms, ref: str) -> float:
            d, m, s = float(dms[0]), float(dms[1]), float(dms[2])
            dd = d + m / 60 + s / 3600
            if ref in ("S", "W"):
                dd = -dd
            return dd

        lat = _dms_to_dd(gps_info["GPSLatitude"], gps_info.get("GPSLatitudeRef", "N"))
        lon = _dms_to_dd(gps_info["GPSLongitude"], gps_info.get("GPSLongitudeRef", "E"))
        return lat, lon
    except Exception:  # noqa: BLE001
        return None
