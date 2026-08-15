"""The signal schema — every field the pipeline will ever need, present on day one.

Two rules govern this module and both are load-bearing:

1. **No country literals.** `sector`, `asset_type` and `admin_unit_code` are plain
   strings validated against the loaded country adapter, never enums with values
   baked in here. A sector list in core would make the cross-border claim false
   (SPEC P0-14), so the lint in `scripts/lint_country_literals.py` fails the build
   if one appears.

2. **No later migrations.** `project_id` and `funded_at` exist now so the Loop 3
   decay query works without a schema change (SPEC P2-4). The image fields exist
   now for the same reason (plan.md 2.1).

Physical condition flags and geo-confidence levels *are* enums, because a
collapsed culvert is structurally unsafe in every country.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field


class ConditionFlag(StrEnum):
    """Visible physical state, per SPEC §6.2. Country-agnostic by nature."""

    STRUCTURALLY_UNSAFE = "structurally_unsafe"
    STANDING_WATER = "standing_water"
    UNUSABLE = "unusable"
    PARTIALLY_FUNCTIONAL = "partially_functional"


class GeoConfidence(StrEnum):
    """How the admin unit was determined.

    `HIGH` is reserved for EXIF GPS resolved through a spatial containment test —
    no inference involved (SPEC P0-6). Reporting `HIGH` separately from `INFERRED`
    is what lets the geo-grounding accuracy number stay honest.
    """

    HIGH = "high"
    INFERRED = "inferred"
    PICKED = "picked"
    UNKNOWN = "unknown"


class Modality(StrEnum):
    VOICE = "voice"
    TEXT = "text"
    IMAGE = "image"
    IMPORT = "import"


Severity = Annotated[int, Field(ge=1, le=5, description="1 = cosmetic, 5 = dangerous/absent")]


class ExtractionResult(BaseModel):
    """Output of the single multimodal extraction call (SPEC §6.2, P0-4).

    One call accepting any combination of audio, text and image parts returns
    exactly this object. The field list is a transcription of P0-4 — do not add
    fields here without adding them to the spec.
    """

    language: str = Field(description="BCP-47 tag detected from the input, not selected by the citizen")
    raw_text: str = Field(default="", description="Transcript or typed text, in the original language")
    translation: str = Field(default="", description="English normalisation, for cross-language analysis")

    sector: str | None = Field(default=None, description="Adapter-defined sector key; None if unclassifiable")
    severity: Severity | None = None

    asset_type: str | None = Field(default=None, description="Adapter-defined visual asset key")
    condition_flags: list[ConditionFlag] = Field(default_factory=list)
    visual_description: str | None = Field(
        default=None, description="Factual caption; the image's text representation for embedding"
    )

    people_present: bool = Field(
        default=False, description="Safety gate — triggers the PII path in SPEC §11"
    )
    relevance: bool = Field(
        default=True, description="False rejects images unrelated to civic infrastructure"
    )

    geo_hint: str | None = Field(
        default=None, description="Verbatim place description from the citizen, before resolution"
    )


class RawSubmission(BaseModel):
    """What a ChannelAdapter produces: an un-analysed submission, ready to extract.

    Carries no citizen identity beyond a salted hash (SPEC §11).
    """

    submission_id: str
    channel: str = Field(description="Adapter key, e.g. web / telegram / csv_import")
    received_at: datetime
    submitter_hash: str | None = Field(
        default=None, description="Salted hash of phone or messaging ID. Never the identifier itself."
    )
    part_kinds: list[str] = Field(default_factory=list, description="Kinds present, for audit")
    declared_admin_unit: str | None = Field(
        default=None, description="Set when the citizen picked a district explicitly (Gate 1 fallback)"
    )
    exif_lat: float | None = Field(
        default=None,
        repr=False,
        description="Transient only. Resolved to an admin unit and then discarded — never persisted.",
    )
    exif_lon: float | None = Field(default=None, repr=False, description="Transient only. See exif_lat.")


class NormalisedSignal(BaseModel):
    """The persisted unit of citizen input. This is what lands in the warehouse.

    Note what is absent: no name, no phone number, no coordinate, no original
    audio or photo. SPEC §11 requires the originals to be destroyed after
    extraction; only the derived attributes below survive.
    """

    signal_id: str
    submission_id: str
    channel: str
    modality: Modality
    received_at: datetime

    # -- language -----------------------------------------------------------
    detected_language: str
    raw_text: str = Field(description="The citizen's own words. Auditability requires them.")
    english_normalised: str

    # -- classification -----------------------------------------------------
    sector: str | None = None
    severity: Severity | None = None

    # -- geography ----------------------------------------------------------
    admin_unit_code: str | None = Field(
        default=None, description="ISO 3166-2 style code from the country adapter (DPGA indicator 8)"
    )
    admin_level: str | None = Field(default=None, description="Adapter-defined level name, e.g. level-2")
    geo_confidence: GeoConfidence = GeoConfidence.UNKNOWN
    geo_hint: str | None = None

    # -- image evidence (plan.md 2.1) ---------------------------------------
    has_image: bool = False
    asset_type: str | None = None
    condition_flags: list[ConditionFlag] = Field(default_factory=list)
    visual_description: str | None = None
    image_thumb_uri: str | None = Field(
        default=None,
        description="Set only when people_present is False. Original is always deleted (SPEC §11).",
    )
    people_present: bool = False

    # -- analysis, filled by the intelligence layer -------------------------
    embedding: list[float] | None = Field(
        default=None, repr=False, description="gemini-embedding-001, 3072 dims (confirmed at Gate 0)"
    )
    need_cluster_id: str | None = Field(
        default=None, description="Assigned by embedding dedup; distinct needs, not raw counts"
    )

    # -- longitudinal, unused in v1 but present so Loop 3 needs no migration --
    project_id: str | None = Field(default=None, description="SPEC P2-4. Set when a funded project is linked.")
    funded_at: date | None = Field(default=None, description="SPEC P2-4. Enables the signal-decay query.")

    # -- provenance ---------------------------------------------------------
    is_synthetic: bool = Field(
        default=False,
        description="Drives the persistent UI banner (P0-16). The citizen layer is synthetic; "
        "the official layer and the evidence photographs are not.",
    )
