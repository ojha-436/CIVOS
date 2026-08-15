"""Evidence bundle — the mechanism that makes dossier grounding architectural.

SPEC §9 requires that no claim appears in a dossier that is not in the retrieved
bundle. That is enforced here by construction: `generate_grounded()` accepts an
`EvidenceBundle` and nothing else. There is no code path that hands the model a
free-text prompt about a district, so there is no code path that can hallucinate
one. "Grounded" is a type signature, not a promise in a system prompt.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EvidenceKind = Literal["signal_cluster", "image", "dataset_row", "scheme"]


class EvidenceItem(BaseModel):
    """One citable fact. Every numbered claim in a dossier resolves to one of these."""

    ref_id: str = Field(description="Stable citation handle, e.g. C-12, IMG-4, DS-NFHS5-2021-r881")
    kind: EvidenceKind
    content: str = Field(description="The fact itself, already resolved to plain language")
    source: str | None = Field(default=None, description="Dataset name + year, or the signal cluster id")
    original_language_text: str | None = Field(
        default=None, description="Citizen quotes are shown in their own language beside English"
    )


class ScoreBreakdown(BaseModel):
    """Every term in SPEC §8, exposed. A black box is not deployable in government."""

    demand_index: float
    deficit_index: float
    participation_rate: float
    voice_correction: float
    adjusted_demand: float
    evidence_strength: float
    silence_gap: float
    forecast_growth: float
    priority: float
    quadrant: str
    weights: dict[str, float] = Field(description="w1..w5 as applied, so a score is reproducible")


class EvidenceBundle(BaseModel):
    """Everything the generator is allowed to know about one (district, sector)."""

    admin_unit_code: str
    admin_unit_name: str
    sector: str
    signals_count: int
    needs_count: int
    languages_count: int
    images_count: int
    population_affected: int | None = None
    scores: ScoreBreakdown
    items: list[EvidenceItem] = Field(default_factory=list)
    suppressed: bool = Field(
        default=False,
        description="True when k-anonymity suppression applies (<5 signals). Blocks dossier generation.",
    )
