"""LanguageModel — the seam that makes DPGA indicator 4 (platform independence) real.

Every model call in CIVOS goes through this Protocol. Google AI is the *reference
implementation*, not a dependency of the design, which is what resolves the
apparent tension between "designed as a Digital Public Good" and a hackathon rule
mandating Google AI: the rule is satisfied by the shipped implementation, the DPG
requirement is satisfied by the interface.

Non-Google reference paths, kept honest by being specific:

    extract()           any multimodal chat-completions endpoint with structured
                        output (vLLM/Ollama serving Qwen-VL or Llama-Vision,
                        an OpenAI-compatible gateway, Azure OpenAI)
    generate_grounded() the same endpoint, text-only; no vendor-specific grounding
                        feature is used — grounding is enforced by only passing an
                        EvidenceBundle
    embed()             sentence-transformers (multilingual-e5, LaBSE) served
                        locally, or any /v1/embeddings endpoint

Anything a Google implementation needs that this interface cannot express is a
bug in the interface, not a reason to bypass it.
"""

from __future__ import annotations

from typing import Protocol, Sequence, TypeVar, runtime_checkable

from pydantic import BaseModel

from core.models.evidence import EvidenceBundle
from core.models.parts import Part

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@runtime_checkable
class LanguageModel(Protocol):
    """One model surface for extraction, grounded generation and embedding."""

    def extract(self, parts: Sequence[Part], schema: type[SchemaT]) -> SchemaT:
        """Turn any combination of audio, text and image into one structured object.

        `parts` — not `audio=`, `text=`, `image=` — is the entire point. A voice
        note, a photo, a typed sentence, or all three at once take the same code
        path and produce the same schema. Adding video (SPEC P2-5) means adding a
        `PartKind`; it must not change this signature or the output schema.

        Implementations must:
          * detect the language rather than accept a declared one (SPEC §6.4)
          * survive code-mixing within a single sentence
          * return schema-valid output or raise — never a best-effort dict
        """
        ...

    def generate_grounded(self, bundle: EvidenceBundle, template: str) -> str:
        """Generate dossier prose from a retrieved evidence bundle and nothing else.

        There is deliberately no `context: str` parameter and no way to pass free
        text about a district. If a claim is not in `bundle.items`, the generator
        was never told it (SPEC §9).
        """
        ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed text for dedup and clustering.

        Used by the Vertex-direct fallback path. When BigQuery ML is available —
        which Gate 0 confirmed it is in our region — clustering pushes down into
        SQL instead and this method is only used for ad-hoc work.
        """
        ...


@runtime_checkable
class SpeechSynthesiser(Protocol):
    """Spoken confirmation back to the citizen in their own language (SPEC P1-6).

    Separate from LanguageModel because it is optional: Tier B and Tier C
    languages get a text confirmation instead, and Tier D needs no language at all.
    Non-Google reference path: Piper, Coqui TTS, or any local TTS server.
    """

    def synthesise(self, text: str, language: str) -> bytes: ...

    def supported_languages(self) -> list[str]: ...
