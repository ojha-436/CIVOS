"""Warehouse — storage, clustering and scoring behind one interface.

This is the seam the Gate 0 fork runs through. Gate 0 returned `PROCEED_BQML`
(see docs/GATE0-RESULT.md), so `BigQueryWarehouse` pushes embedding, clustering,
scoring and forecasting down into SQL. Had it returned `FALLBACK_VERTEX`, a
`HybridWarehouse` pulling embeddings out and clustering in scikit-learn would
implement this *same* interface. Deciding that on day one is the difference
between a swap and a rewrite.

Non-Google reference path: PostgreSQL 16 + PostGIS + pgvector implements every
method here — `cluster_needs` becomes a pgvector nearest-neighbour join,
`forecast_demand` becomes statsmodels, `score_districts` is the same SQL with
different function names. That is a real migration path, not a hand-wave, which
is what DPGA indicator 4 asks for.

Two guarantees every implementation must honour:

  * `aggregate_*` methods return k-anonymised results. Suppression below 5 signals
    per (admin unit, sector) happens in the warehouse, not in the API layer, so no
    caller can accidentally route around it (SPEC §11, DPGA indicator 6).
  * No method accepts or returns a citizen coordinate. Admin unit only.
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence, runtime_checkable

from core.models.evidence import EvidenceBundle
from core.models.signal import NormalisedSignal

K_ANONYMITY_THRESHOLD = 5
"""Minimum signals per (admin unit, sector) before a cell may be reported."""


@runtime_checkable
class Warehouse(Protocol):
    """Persistence and analytics for signals, official data and scores."""

    # -- ingest -------------------------------------------------------------

    def upsert_signals(self, signals: Sequence[NormalisedSignal]) -> int:
        """Persist signals idempotently by `signal_id`. Returns rows written."""
        ...

    def load_table(self, table: str, rows: Sequence[dict[str, Any]], *, replace: bool = False) -> int:
        """Bulk-load a reference table — admin units, deficit indicators, schemes."""
        ...

    # -- geography ----------------------------------------------------------

    def resolve_admin_unit(self, lat: float, lon: float) -> str | None:
        """Resolve a coordinate to an admin unit code by spatial containment.

        The EXIF high-confidence path (SPEC P0-6). Callers pass the coordinate,
        keep the returned code, and discard the coordinate — this interface
        offers no way to store one, deliberately.
        """
        ...

    # -- intelligence -------------------------------------------------------

    def embed_signals(self, *, only_missing: bool = True) -> int:
        """Compute embeddings for stored signals. Returns rows embedded.

        Includes `visual_description` for image-only signals, so a photograph of a
        dry handpump clusters with a voice note about the same problem.
        """
        ...

    def cluster_needs(self, *, distance_threshold: float) -> int:
        """Collapse near-duplicate signals into distinct needs (SPEC P0-7).

        Sets `need_cluster_id`. The console reports Signals *and* Needs separately
        because 800 complaints about one dry borewell is one problem, not 800.
        """
        ...

    def score_districts(self, weights: dict[str, float]) -> int:
        """Recompute every term in SPEC §8 and assign quadrants.

        `weights` (w1..w5) is a parameter rather than configuration because the
        console exposes it as live sliders. A ministry will not adopt a ranking it
        cannot re-weight to its own policy priorities.
        """
        ...

    def forecast_demand(self, *, horizon_days: int = 90) -> int:
        """Fit and store a per (admin unit, sector) demand forecast (SPEC P1-1)."""
        ...

    # -- read ---------------------------------------------------------------

    def aggregate_scores(
        self, *, sector: str | None = None, quadrant: str | None = None
    ) -> list[dict[str, Any]]:
        """Ranked (admin unit, sector) rows for the console and the public API.

        k-anonymised. Cells below `K_ANONYMITY_THRESHOLD` are suppressed here.
        """
        ...

    def evidence_bundle(self, admin_unit_code: str, sector: str) -> EvidenceBundle:
        """Retrieve everything a dossier is permitted to cite, and nothing more.

        The retrieval half of grounded generation: whatever this returns is the
        complete universe of facts available to `LanguageModel.generate_grounded`.
        """
        ...

    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Escape hatch for analysis and scripts. Not used by request paths."""
        ...
