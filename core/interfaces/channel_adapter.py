"""ChannelAdapter — how a citizen reaches CIVOS, and why adding a channel is cheap.

The web widget, the Telegram bot and the bulk CSV importer are all the same shape:
something arrives, it becomes a `RawSubmission` plus a list of `Part`s, and it goes
into the one extraction call. Nothing downstream knows which channel produced a
signal beyond the `channel` string it carries.

That matters twice over:

  * The bulk importer is a channel, not a special case. Importing a legacy
    grievance CSV through the same path is what makes CIVOS a defragmenter rather
    than fragment #5 — which is literally the failure the problem statement names.
  * SPEC P2-1 (WhatsApp, IVR, SMS) becomes a new class implementing this Protocol,
    with no change anywhere else. `WhatsAppAdapter` ships in Phase 3 as a
    documented stub behind exactly this interface, because Meta business
    verification is unavailable to an individual on this timeline — an honest
    substitution, not a missing feature.

Non-Google reference path: none needed. This interface has no vendor in it, which
is the point.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from core.models.parts import Part
from core.models.signal import ExtractionResult, RawSubmission


@runtime_checkable
class ChannelAdapter(Protocol):
    """Normalise one inbound channel into the common submission shape."""

    channel: str
    """Stable key persisted on every signal, e.g. 'web', 'telegram', 'csv_import'."""

    def parse(self, payload: Any) -> tuple[RawSubmission, list[Part]]:
        """Convert a channel-native payload into a submission and its parts.

        Implementations must:
          * salted-hash any citizen identifier before it reaches `RawSubmission`,
            and never store the identifier itself (SPEC §11)
          * put EXIF coordinates on the transient `exif_lat`/`exif_lon` fields
            only — they are resolved to an admin unit and then discarded
          * never persist the raw payload
        """
        ...

    def confirm(self, submission: RawSubmission, result: ExtractionResult) -> None:
        """Tell the citizen they were heard, in the language they used.

        Silence here is a product failure, not a technical one: a citizen who gets
        no acknowledgement does not come back, and the participation bias the whole
        engine exists to correct gets worse. Tier D (image-only, no language) is
        confirmed with an icon and the resolved district name.
        """
        ...
