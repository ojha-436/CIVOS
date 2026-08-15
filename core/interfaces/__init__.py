"""The three interfaces every implementation sits behind.

Written before any implementation exists, on purpose. They buy three things:
the single multimodal extraction path (SPEC P0-4), the DPGA indicator 4
platform-independence claim, and the ability to swap the analytics engine after
Gate 0 without touching anything else.
"""

from core.interfaces.channel_adapter import ChannelAdapter
from core.interfaces.language_model import LanguageModel, SpeechSynthesiser
from core.interfaces.warehouse import K_ANONYMITY_THRESHOLD, Warehouse

__all__ = [
    "K_ANONYMITY_THRESHOLD",
    "ChannelAdapter",
    "LanguageModel",
    "SpeechSynthesiser",
    "Warehouse",
]
