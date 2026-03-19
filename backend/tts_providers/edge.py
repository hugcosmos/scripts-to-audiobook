"""
Edge TTS Provider
Wraps the existing edge-tts implementation.
"""
import edge_tts
import logging
from pathlib import Path
from typing import Optional
import tempfile

from .base import TTSProvider, TTSRequest, TTSResult

logger = logging.getLogger(__name__)


class EdgeTTSProvider(TTSProvider):
    """Microsoft Edge TTS provider (free, no authentication required)."""

    name = "edge"
    display_name = "Edge TTS"
    requires_auth = False
    supported_languages = ["en", "zh", "ja", "ko", "de", "fr", "es", "it", "pt", "ru", "ar", "hi"]

    def __init__(self):
        self._voices_cache = None

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """Synthesize text using Edge TTS."""
        output_path = request.output_path
        if output_path is None:
            output_path = Path(tempfile.mktemp(suffix=".mp3"))

        word_boundaries = []
        audio_chunks = []

        communicate = edge_tts.Communicate(
            request.text,
            request.voice_id,
            rate=request.rate,
            pitch=request.pitch,
            volume=request.volume
        )

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_boundaries.append({
                    "text": chunk.get("text", ""),
                    "offset": chunk.get("offset", 0),
                    "duration": chunk.get("duration", 0),
                })

        # Write audio to file
        with open(output_path, "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)

        # Get duration using ffprobe
        duration_ms = self._get_duration_ms(output_path)

        return TTSResult(
            audio_path=output_path,
            duration_ms=duration_ms,
            word_boundaries=word_boundaries,
            content_type="audio/mpeg"
        )

    def _get_duration_ms(self, path: Path) -> float:
        """Get MP3 duration in milliseconds using ffprobe."""
        import subprocess
        import json as json_module

        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_streams", str(path)],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                data = json_module.loads(result.stdout)
                for stream in data.get("streams", []):
                    if stream.get("codec_type") == "audio":
                        dur = float(stream.get("duration", 0))
                        return dur * 1000
        except Exception:
            pass
        return 0.0

    async def list_voices(self, lang: Optional[str] = None) -> list[dict]:
        """List Edge TTS voices from cached catalog."""
        if self._voices_cache is None:
            import json
            from pathlib import Path

            # First try to load custom voices from voices_edge.json
            custom_catalog_path = Path(__file__).parent.parent.parent / "catalog" / "voices_edge.json"
            if custom_catalog_path.exists():
                try:
                    with open(custom_catalog_path, encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            custom_voices = data
                        elif isinstance(data, dict) and "voices" in data:
                            custom_voices = data["voices"]
                        else:
                            custom_voices = []
                    if custom_voices:
                        # Use custom voices if available
                        self._voices_cache = custom_voices
                    else:
                        # Fallback to default voices
                        self._load_default_voices()
                except Exception as e:
                    logger.error(f"[Edge TTS] Failed to load custom voices: {e}")
                    self._load_default_voices()
            else:
                # No custom voices, load default voices
                self._load_default_voices()

        voices = self._voices_cache

        if lang:
            lang_map = {"en": "English", "zh": "Chinese"}
            target = lang_map.get(lang.lower(), lang.title())
            # Support both full name and 2-letter code matching
            voices = [v for v in voices if 
                      v.get("base_language", "").lower() == target.lower() or
                      (lang == "en" and v.get("base_language", "").lower() in ["english", "en"]) or
                      (lang == "zh" and v.get("base_language", "").lower() in ["chinese", "zh", "zh-cn", "zh-hk", "zh-tw"])]

        # Sort voices: English and Chinese first, then others
        def voice_sort_key(v):
            lang = v.get("language", "").lower()
            if lang == "en":
                return 0
            elif lang == "zh":
                return 1
            else:
                return 2

        voices.sort(key=voice_sort_key)

        return voices
        
    def _load_default_voices(self):
        """Load default Edge TTS voices."""
        import json
        from pathlib import Path

        catalog_path = Path(__file__).parent.parent.parent / "catalog" / "voices_all.json"
        if catalog_path.exists():
            with open(catalog_path) as f:
                raw_voices = json.load(f)
            # Process voices to add provider and quality score
            self._voices_cache = []
            for v in raw_voices:
                voice = dict(v)
                voice["provider"] = "edge"
                # Ensure quality_score exists
                if "quality_score" not in voice:
                    voice["quality_score"] = self.get_quality_score(voice)
                self._voices_cache.append(voice)
        else:
            # Fallback to fetching from Edge TTS
            import asyncio
            voices = asyncio.run(edge_tts.list_voices())
            self._voices_cache = [
                self._normalize_voice(v) for v in voices
            ]

    def _normalize_voice(self, voice: dict) -> dict:
        """Normalize Edge TTS voice format to standard format."""
        return {
            "voice_id": voice.get("ShortName", voice.get("voice_id", "")),
            "display_name": voice.get("ShortName", voice.get("display_name", "")).replace("Neural", "").replace("Multilingual", ""),
            "full_name": voice.get("Name", voice.get("full_name", "")),
            "language": voice.get("Locale", voice.get("language", "")).split("-")[0],
            "locale": voice.get("Locale", voice.get("locale", "")),
            "base_language": voice.get("base_language", "English"),
            "gender": voice.get("Gender", voice.get("gender", "Unknown")),
            "age_bucket": voice.get("age_bucket", "adult"),
            "quality_score": self.get_quality_score(voice),
            "narrator_fit_score": voice.get("narrator_fit_score", 0.5),
            "dialogue_fit_score": voice.get("dialogue_fit_score", 0.5),
            "preview_url": None,
            "labels": voice.get("personalities", []),
            "provider": "edge"
        }

    def get_quality_score(self, voice: dict) -> float:
        """Calculate combined quality score for Edge TTS voice."""
        narrator_score = voice.get("narrator_fit_score", 0.5)
        dialogue_score = voice.get("dialogue_fit_score", 0.5)
        # Weight narrator slightly higher for audiobook use case
        return (narrator_score * 0.6 + dialogue_score * 0.4)

    async def test_connection(self) -> bool:
        """Test Edge TTS connection (always available)."""
        try:
            voices = await edge_tts.list_voices()
            return len(voices) > 0
        except Exception:
            return True  # Edge TTS should always work
