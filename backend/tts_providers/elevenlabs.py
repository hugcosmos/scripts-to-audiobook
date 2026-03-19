"""
ElevenLabs TTS Provider
Integration with ElevenLabs API for high-quality voice synthesis.
"""
import aiohttp
import json
import logging
from pathlib import Path
from typing import Optional
import tempfile

from .base import TTSProvider, TTSRequest, TTSResult

logger = logging.getLogger(__name__)


class ElevenLabsProvider(TTSProvider):
    """ElevenLabs TTS provider (paid, high quality)."""

    name = "elevenlabs"
    display_name = "ElevenLabs"
    requires_auth = True
    supported_languages = ["en", "zh", "ja", "ko", "de", "fr", "es", "it", "pt", "ru", "ar", "hi"]

    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._voices_cache = None

    def set_credentials(self, api_key: str):
        """Set API credentials."""
        self.api_key = api_key
        self._voices_cache = None

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """Synthesize text using ElevenLabs API."""
        if not self.api_key:
            raise ValueError("ElevenLabs API key not configured")

        output_path = request.output_path
        if output_path is None:
            output_path = Path(tempfile.mktemp(suffix=".mp3"))

        # Map Edge TTS rate/pitch to ElevenLabs style
        # ElevenLabs uses stability and similarity_boost instead
        stability = 0.5
        similarity_boost = 0.75

        # Parse rate if provided
        if request.rate and request.rate != "+0%":
            try:
                rate_val = float(request.rate.replace("+", "").replace("%", ""))
                # Map rate to stability (faster = lower stability)
                stability = max(0.1, min(1.0, 0.5 - (rate_val / 200)))
            except:
                pass

        url = f"{self.BASE_URL}/text-to-speech/{request.voice_id}"

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "text": request.text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "use_speaker_boost": True
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"ElevenLabs API error: {response.status} - {error_text}")

                audio_data = await response.read()

        # Write to file
        with open(output_path, "wb") as f:
            f.write(audio_data)

        # Get duration
        duration_ms = self._get_duration_ms(output_path)

        return TTSResult(
            audio_data=audio_data,
            audio_path=output_path,
            duration_ms=duration_ms,
            word_boundaries=[],  # ElevenLabs doesn't provide word boundaries
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
        """List ElevenLabs voices from API or cached catalog."""
        if self._voices_cache is not None:
            voices = self._voices_cache
        else:
            if self.api_key:
                # Fetch from API
                api_voices = await self._fetch_voices_from_api()
                # Load local catalog to check which voices are deleted
                local_voices = self._load_local_catalog()
                if local_voices:
                    # Get voice IDs that are not deleted (present in local catalog)
                    local_voice_ids = {v.get("voice_id") for v in local_voices}
                    # Filter API voices to only include those not deleted
                    voices = [v for v in api_voices if v.get("voice_id") in local_voice_ids]
                else:
                    # No local catalog, use all API voices
                    voices = api_voices
                    # Save all API voices to local catalog for future management
                    self._save_to_local_catalog(voices)
            else:
                # No API key, load from local catalog or defaults
                local_voices = self._load_local_catalog()
                if local_voices:
                    voices = local_voices
                else:
                    voices = self._get_default_voices()
            self._voices_cache = voices

        if lang:
            voices = [v for v in voices if v.get("language", "").lower().startswith(lang.lower())]

        return voices
        
    def _save_to_local_catalog(self, voices: list[dict]):
        """Save voices to local catalog file."""
        import json
        from pathlib import Path
        
        catalog_path = Path(__file__).parent.parent.parent / "catalog" / "voices_elevenlabs.json"
        try:
            # Create directory if it doesn't exist
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(catalog_path, 'w', encoding='utf-8') as f:
                json.dump(voices, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[ElevenLabs] Failed to save to local catalog: {e}")

    async def _fetch_voices_from_api(self) -> list[dict]:
        """Fetch voices from ElevenLabs API."""
        if not self.api_key:
            return []

        url = f"{self.BASE_URL}/voices"
        headers = {"xi-api-key": self.api_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        return self._load_local_catalog()

                    data = await response.json()
                    voices = data.get("voices", [])
                    normalized_voices = [self._normalize_voice(v) for v in voices]
                    # Log API voices for debugging
                    logger.debug(f"[ElevenLabs] API returned {len(normalized_voices)} voices")
                    for v in normalized_voices:
                        logger.debug(f"  - {v['display_name']} (ID: {v['voice_id']})")
                    return normalized_voices
        except Exception as e:
            logger.error(f"[ElevenLabs] API error: {e}")
            return self._load_local_catalog()

    def _load_local_catalog(self) -> list[dict]:
        """Load voices from local catalog file or return defaults."""
        import json
        from pathlib import Path

        catalog_path = Path(__file__).parent.parent.parent / "catalog" / "voices_elevenlabs.json"
        if catalog_path.exists():
            with open(catalog_path) as f:
                return json.load(f)
        
        # Return default popular voices
        return self._get_default_voices()
    
    def _get_default_voices(self) -> list[dict]:
        """Return default ElevenLabs voice list."""
        return [
            {
                "voice_id": "21m00Tcm4TlvDq8ikWAM",
                "display_name": "Rachel",
                "language": "en",
                "locale": "en-US",
                "base_language": "English",
                "gender": "Female",
                "age_bucket": "adult",
                "quality_score": 0.9,
                "narrator_fit_score": 0.85,
                "dialogue_fit_score": 0.9,
                "preview_url": None,
                "labels": ["conversational", "friendly"],
                "provider": "elevenlabs"
            },
            {
                "voice_id": "AZnzlk1XvdvUeBnXmlld",
                "display_name": "Domi",
                "language": "en",
                "locale": "en-US",
                "base_language": "English",
                "gender": "Female",
                "age_bucket": "adult",
                "quality_score": 0.88,
                "narrator_fit_score": 0.8,
                "dialogue_fit_score": 0.88,
                "preview_url": None,
                "labels": ["strong", "energetic"],
                "provider": "elevenlabs"
            },
            {
                "voice_id": "EXAVITQu4vr4xnSDxMaL",
                "display_name": "Bella",
                "language": "en",
                "locale": "en-US",
                "base_language": "English",
                "gender": "Female",
                "age_bucket": "adult",
                "quality_score": 0.9,
                "narrator_fit_score": 0.88,
                "dialogue_fit_score": 0.85,
                "preview_url": None,
                "labels": ["calm", "soft"],
                "provider": "elevenlabs"
            },
            {
                "voice_id": "ErXwobaYiN019PkySvjV",
                "display_name": "Antoni",
                "language": "en",
                "locale": "en-US",
                "base_language": "English",
                "gender": "Male",
                "age_bucket": "adult",
                "quality_score": 0.87,
                "narrator_fit_score": 0.85,
                "dialogue_fit_score": 0.88,
                "preview_url": None,
                "labels": ["well-rounded", "clear"],
                "provider": "elevenlabs"
            },
            {
                "voice_id": "MF3mGyEYCl7XYWbV9V6O",
                "display_name": "Elli",
                "language": "en",
                "locale": "en-US",
                "base_language": "English",
                "gender": "Female",
                "age_bucket": "adult",
                "quality_score": 0.85,
                "narrator_fit_score": 0.82,
                "dialogue_fit_score": 0.85,
                "preview_url": None,
                "labels": ["warm", "grandma"],
                "provider": "elevenlabs"
            }
        ]

    def _normalize_voice(self, voice: dict) -> dict:
        """Normalize ElevenLabs voice format to standard format."""
        labels = voice.get("labels", {})

        # Determine language from labels
        language = labels.get("language", "en")
        if isinstance(language, list):
            language = language[0] if language else "en"

        # Map language code to full language name
        lang_map = {
            "en": "English",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "de": "German",
            "fr": "French",
            "es": "Spanish",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "ar": "Arabic",
            "hi": "Hindi"
        }

        # Determine gender
        gender = labels.get("gender", "unknown")
        if gender.lower() in ["male", "man"]:
            gender = "Male"
        elif gender.lower() in ["female", "woman"]:
            gender = "Female"
        else:
            gender = "Unknown"

        return {
            "voice_id": voice.get("voice_id", ""),
            "display_name": voice.get("name", ""),
            "full_name": voice.get("name", ""),
            "language": language,
            "locale": language,
            "base_language": lang_map.get(language, language.upper()),
            "gender": gender,
            "age_bucket": "adult",  # Default age bucket for ElevenLabs voices
            "quality_score": 0.85,  # ElevenLabs voices are generally high quality
            "narrator_fit_score": 0.8,
            "dialogue_fit_score": 0.9,
            "preview_url": f"https://api.elevenlabs.io/v1/voices/{voice.get('voice_id', '')}/preview",
            "labels": [labels.get("accent", ""), labels.get("description", "")],
            "provider": "elevenlabs"
        }

    async def test_connection(self) -> bool:
        """Test ElevenLabs API connection."""
        if not self.api_key:
            return False

        url = f"{self.BASE_URL}/user"
        headers = {"xi-api-key": self.api_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    return response.status == 200
        except Exception:
            return False

    def get_quality_score(self, voice: dict) -> float:
        """ElevenLabs voices are generally high quality."""
        return voice.get("quality_score", 0.85)
