"""
TTS Provider implementations for Scripts to Audiobook.
"""
from .base import TTSProvider, TTSRequest, TTSResult
from .edge import EdgeTTSProvider
from .elevenlabs import ElevenLabsProvider
from .iflytek import iFlytekProvider
from .baidu import BaiduProvider

__all__ = [
    "TTSProvider",
    "TTSRequest",
    "TTSResult",
    "EdgeTTSProvider",
    "ElevenLabsProvider",
    "iFlytekProvider",
    "BaiduProvider",
]
