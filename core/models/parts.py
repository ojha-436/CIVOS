"""Input parts — the reason CIVOS has one extraction path instead of three.

A citizen submission is a *list of parts*, not a set of named fields. Voice, text
and image arrive as `Part` objects of different `kind` and go into a single
multimodal request. Adding video later (SPEC P2-5) adds a `kind`, not a pipeline.

This module is country-agnostic and model-agnostic by construction: nothing here
names a vendor, a country, or a language.
"""

from __future__ import annotations

import base64
from typing import Literal

from pydantic import BaseModel, Field, model_validator

PartKind = Literal["audio", "text", "image", "video"]

# Kinds whose payload is deleted immediately after extraction (SPEC §11).
# Text is the only modality we are permitted to retain as submitted.
EPHEMERAL_KINDS: frozenset[str] = frozenset({"audio", "image", "video"})


class Part(BaseModel):
    """One piece of a citizen submission.

    Exactly one of `data` (inline bytes) or `uri` (object-store reference) must
    be set. `text` parts carry their content in `data` as UTF-8.
    """

    kind: PartKind
    mime_type: str = Field(description="e.g. audio/ogg, image/jpeg, text/plain")
    data: bytes | None = Field(default=None, repr=False)
    uri: str | None = None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> Part:
        if (self.data is None) == (self.uri is None):
            raise ValueError("Part requires exactly one of `data` or `uri`")
        return self

    @property
    def is_ephemeral(self) -> bool:
        """True if SPEC §11 requires this payload to be destroyed after extraction."""
        return self.kind in EPHEMERAL_KINDS

    @classmethod
    def from_text(cls, text: str) -> Part:
        return cls(kind="text", mime_type="text/plain", data=text.encode("utf-8"))

    @classmethod
    def from_bytes(cls, kind: PartKind, mime_type: str, payload: bytes) -> Part:
        return cls(kind=kind, mime_type=mime_type, data=payload)

    def as_text(self) -> str:
        if self.kind != "text" or self.data is None:
            raise ValueError("as_text() is only valid for inline text parts")
        return self.data.decode("utf-8")

    def as_base64(self) -> str:
        if self.data is None:
            raise ValueError("as_base64() requires inline data")
        return base64.b64encode(self.data).decode("ascii")
