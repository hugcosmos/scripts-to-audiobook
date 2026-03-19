"""
Base TTS Provider Interface
Defines the abstract interface that all TTS providers must implement.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, AsyncGenerator
from pathlib import Path


@dataclass
class TTSRequest:
    """Request for TTS synthesis."""
    text: str
    voice_id: str
    rate: str = "+0%"  # Speed adjustment (Edge TTS style)
    pitch: str = "+0Hz"  # Pitch adjustment (Edge TTS style)
    volume: str = "+0%"  # Volume adjustment
    output_path: Optional[Path] = None  # If provided, save to file


@dataclass
class TTSResult:
    """Result of TTS synthesis."""
    audio_data: Optional[bytes] = None
    audio_path: Optional[Path] = None
    duration_ms: float = 0.0
    word_boundaries: list = None  # List of word timing info
    content_type: str = "audio/mpeg"

    def __post_init__(self):
        if self.word_boundaries is None:
            self.word_boundaries = []


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    name: str = "base"
    display_name: str = "Base TTS"
    requires_auth: bool = False
    supported_languages: list[str] = []

    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """
        Synthesize text to audio.

        Args:
            request: TTS request with text, voice_id, and parameters

        Returns:
            TTSResult with audio data or file path
        """
        pass

    @abstractmethod
    async def list_voices(self, lang: Optional[str] = None) -> list[dict]:
        """
        List available voices for this provider.

        Args:
            lang: Optional language filter (e.g., "en", "zh")

        Returns:
            List of voice dictionaries with standardized format:
            {
                "voice_id": str,
                "display_name": str,
                "language": str,
                "gender": str,
                "quality_score": float,
                "preview_url": Optional[str],
                "labels": list[str]
            }
        """
        pass

    async def test_connection(self) -> bool:
        """
        Test if the provider is properly configured and credentials are valid.

        Returns:
            True if connection is successful, False otherwise
        """
        return True

    async def preview_voice(self, voice_id: str, text: Optional[str] = None) -> Optional[bytes]:
        """
        Generate a short preview for a voice.

        Args:
            voice_id: Voice to use for preview
            text: Optional custom text for preview

        Returns:
            Audio bytes or None if preview is not available
        """
        preview_text = text or "Hello, this is a voice preview."
        try:
            result = await self.synthesize(TTSRequest(
                text=preview_text[:200],  # Limit preview length
                voice_id=voice_id
            ))
            return result.audio_data
        except Exception:
            return None

    def get_quality_score(self, voice: dict) -> float:
        """
        Calculate a combined quality score for a voice.

        Args:
            voice: Voice dictionary

        Returns:
            Combined quality score (0-1)
        """
        # Default implementation - can be overridden by providers
        narrator_score = voice.get("narrator_fit_score", 0.5)
        dialogue_score = voice.get("dialogue_fit_score", 0.5)
        return (narrator_score + dialogue_score) / 2
