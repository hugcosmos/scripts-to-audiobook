"""
Baidu TTS Provider
Integration with Baidu Voice API for Chinese TTS.
"""
import aiohttp
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional
import tempfile
import base64

from .base import TTSProvider, TTSRequest, TTSResult

logger = logging.getLogger(__name__)


class BaiduProvider(TTSProvider):
    """Baidu TTS provider (paid, good Chinese voices)."""

    name = "baidu"
    display_name = "百度语音"
    requires_auth = True
    supported_languages = ["zh", "en"]

    # API endpoints
    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    TTS_URL = "https://tsn.baidu.com/text2audio"

    def __init__(
        self,
        app_id: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None
    ):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self._access_token = None
        self._token_expires = 0
        self._voices_cache = None

    def set_credentials(self, app_id: str, api_key: str, api_secret: str):
        """Set API credentials."""
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self._access_token = None
        self._voices_cache = None

    def clear_cache(self):
        """Clear voice cache to force reloading from catalog."""
        self._voices_cache = None

    async def _get_access_token(self) -> str:
        """Get Baidu API access token."""
        if self._access_token and time.time() < self._token_expires:
            return self._access_token

        if not self.api_key or not self.api_secret:
            raise ValueError("Baidu API credentials not configured")

        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.api_secret
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.TOKEN_URL, params=params) as response:
                if response.status != 200:
                    raise Exception(f"Failed to get Baidu access token: {response.status}")

                data = await response.json()
                self._access_token = data.get("access_token")
                expires_in = data.get("expires_in", 86400)
                self._token_expires = time.time() + expires_in - 300  # 5 min buffer

                return self._access_token

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """Synthesize text using Baidu TTS API."""
        if not all([self.api_key, self.api_secret]):
            raise ValueError("Baidu credentials not configured")

        output_path = request.output_path
        if output_path is None:
            output_path = Path(tempfile.mktemp(suffix=".mp3"))

        token = await self._get_access_token()

        # Build request parameters
        params = {
            "tex": request.text,
            "tok": token,
            "cuid": "scripts-to-audiobook",
            "ctp": 1,  # Client type: web
            "lan": "zh",  # Language
            "spd": self._parse_speed(request.rate),
            "pit": self._parse_pitch(request.pitch),
            "vol": self._parse_volume(request.volume),
            "per": self._parse_voice(request.voice_id),
            "aue": 3,  # MP3 format
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.TTS_URL, data=params) as response:
                content_type = response.headers.get("Content-Type", "")

                if "audio" in content_type:
                    audio_data = await response.read()
                elif "json" in content_type:
                    error = await response.json()
                    raise Exception(f"Baidu TTS error: {error}")
                else:
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
            word_boundaries=[],
            content_type="audio/mpeg"
        )

    def _parse_speed(self, rate: str) -> int:
        """Parse Edge TTS rate to Baidu speed (0-15, default 5)."""
        if not rate or rate == "+0%":
            return 5
        try:
            val = float(rate.replace("+", "").replace("%", ""))
            # Map -50%~+50% to 0-15
            return max(0, min(15, int(5 + val / 10)))
        except:
            return 5

    def _parse_volume(self, volume: str) -> int:
        """Parse Edge TTS volume to Baidu volume (0-15, default 5)."""
        if not volume or volume == "+0%":
            return 5
        try:
            val = float(volume.replace("+", "").replace("%", ""))
            return max(0, min(15, int(5 + val / 10)))
        except:
            return 5

    def _parse_pitch(self, pitch: str) -> int:
        """Parse Edge TTS pitch to Baidu pitch (0-15, default 5)."""
        if not pitch or pitch == "+0Hz":
            return 5
        try:
            val = float(pitch.replace("+", "").replace("Hz", ""))
            return max(0, min(15, int(5 + val / 20)))
        except:
            return 5

    def _parse_voice(self, voice_id: str) -> int:
        """Parse voice_id to Baidu per parameter."""
        # Baidu voice IDs are numbers
        voice_map = {
            "0": 0,   # 普通女声
            "1": 1,   # 普通男声
            "3": 3,   # 情感合成-男声"度逍遥"
            "4": 4,   # 情感合成-女声"度丫丫"
            "5": 5,   # 情感合成-男声"度小宇"
            "103": 103,  # 精品男声
            "106": 106,  # 精品男声
            "110": 110,  # 精品女声
            "111": 111,  # 精品女声
        }
        return voice_map.get(voice_id, int(voice_id) if voice_id.isdigit() else 0)

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
        """List Baidu voices from local catalog."""
        if self._voices_cache is None:
            self._voices_cache = self._load_local_catalog()

        voices = self._voices_cache

        if lang:
            voices = [v for v in voices if v.get("language", "").lower().startswith(lang.lower())]

        return voices

    def _load_local_catalog(self) -> list[dict]:
        """Load voices from local catalog file."""
        import json
        from pathlib import Path

        catalog_path = Path(__file__).parent.parent.parent / "catalog" / "voices_baidu.json"
        if catalog_path.exists():
            with open(catalog_path) as f:
                return json.load(f)

        # Return default voices if catalog doesn't exist
        return self._get_default_voices()

    def _get_default_voices(self) -> list[dict]:
        """Return default Baidu voice list."""
        return [
            # 情感合成声音 - 高质量
            {
                "voice_id": "3",
                "display_name": "度逍遥（情感-磁性男声）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Male",
                "quality_score": 0.88,
                "narrator_fit_score": 0.85,
                "dialogue_fit_score": 0.88,
                "preview_url": None,
                "labels": ["情感", "男声", "磁性", "特色"],
                "provider": "baidu"
            },
            {
                "voice_id": "4",
                "display_name": "度丫丫（情感-甜美女声）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Female",
                "quality_score": 0.86,
                "narrator_fit_score": 0.82,
                "dialogue_fit_score": 0.88,
                "preview_url": None,
                "labels": ["情感", "女声", "甜美", "特色"],
                "provider": "baidu"
            },
            {
                "voice_id": "5",
                "display_name": "度小宇（情感-成熟男声）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Male",
                "quality_score": 0.85,
                "narrator_fit_score": 0.83,
                "dialogue_fit_score": 0.87,
                "preview_url": None,
                "labels": ["情感", "男声", "成熟", "特色"],
                "provider": "baidu"
            },
            # 精品声音 - 高音质
            {
                "voice_id": "103",
                "display_name": "度米朵（精品-温柔女声）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Female",
                "quality_score": 0.87,
                "narrator_fit_score": 0.85,
                "dialogue_fit_score": 0.88,
                "preview_url": None,
                "labels": ["精品", "女声", "温柔"],
                "provider": "baidu"
            },
            {
                "voice_id": "106",
                "display_name": "度博文（精品-磁性男声）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Male",
                "quality_score": 0.88,
                "narrator_fit_score": 0.88,
                "dialogue_fit_score": 0.87,
                "preview_url": None,
                "labels": ["精品", "男声", "磁性", "解说"],
                "provider": "baidu"
            },
            {
                "voice_id": "110",
                "display_name": "度小童（精品-童声）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Female",
                "quality_score": 0.85,
                "narrator_fit_score": 0.7,
                "dialogue_fit_score": 0.88,
                "preview_url": None,
                "labels": ["精品", "童声", "可爱"],
                "provider": "baidu"
            },
            {
                "voice_id": "111",
                "display_name": "度小萌（精品-活泼女声）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Female",
                "quality_score": 0.86,
                "narrator_fit_score": 0.8,
                "dialogue_fit_score": 0.9,
                "preview_url": None,
                "labels": ["精品", "女声", "活泼"],
                "provider": "baidu"
            },
            # 专业声音
            {
                "voice_id": "5003",
                "display_name": "度逍遥（专业版）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Male",
                "quality_score": 0.9,
                "narrator_fit_score": 0.88,
                "dialogue_fit_score": 0.9,
                "preview_url": None,
                "labels": ["专业", "男声", "磁性", "高端"],
                "provider": "baidu"
            },
            {
                "voice_id": "5118",
                "display_name": "度小鹿（专业女声）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Female",
                "quality_score": 0.88,
                "narrator_fit_score": 0.85,
                "dialogue_fit_score": 0.88,
                "preview_url": None,
                "labels": ["专业", "女声", "温柔"],
                "provider": "baidu"
            },
        ]

    async def test_connection(self) -> bool:
        """Test Baidu API connection."""
        if not all([self.api_key, self.api_secret]):
            return False

        try:
            token = await self._get_access_token()
            return token is not None
        except Exception as e:
            logger.error(f"Baidu test failed: {e}")
            return False

    def get_quality_score(self, voice: dict) -> float:
        """Get quality score for Baidu voice."""
        return voice.get("quality_score", 0.75)
