"""
iFlytek (科大讯飞) TTS Provider
Integration with iFlytek Voice API for Chinese TTS.
"""
import aiohttp
import hashlib
import hmac
import base64
import json
import logging
import time
import websocket
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime
import tempfile

from .base import TTSProvider, TTSRequest, TTSResult

logger = logging.getLogger(__name__)


class iFlytekProvider(TTSProvider):
    """iFlytek TTS provider (paid, excellent Chinese voices)."""

    name = "iflytek"
    display_name = "科大讯飞"
    requires_auth = True
    supported_languages = ["zh", "en"]

    # API endpoints
    TTS_URL = "wss://tts-api.xfyun.cn/v2/tts"
    AUTH_URL = "https://tts-api.xfyun.cn/v2/tts"

    def __init__(
        self,
        app_id: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None
    ):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self._voices_cache = None

    def set_credentials(self, app_id: str, api_key: str, api_secret: str):
        """Set API credentials."""
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self._voices_cache = None

    def clear_cache(self):
        """Clear voice cache to force reloading from catalog."""
        self._voices_cache = None

    def _generate_auth_url(self) -> str:
        """Generate authenticated WebSocket URL."""
        # Generate RFC 1123 format date (required by iFlytek)
        # Format: Wed, 10 Jul 2024 10:30:00 GMT
        from wsgiref.handlers import format_date_time
        date_str = format_date_time(time.time())

        # Generate signature
        signature_origin = f"host: tts-api.xfyun.cn\n" \
                          f"date: {date_str}\n" \
                          f"GET /v2/tts HTTP/1.1"

        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()

        signature = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = f'api_key="{self.api_key}", ' \
                              f'algorithm="hmac-sha256", ' \
                              f'headers="host date request-line", ' \
                              f'signature="{signature}"'

        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        # Build URL
        params = {
            "authorization": authorization,
            "date": date_str,
            "host": "tts-api.xfyun.cn"
        }

        from urllib.parse import urlencode
        url = f"{self.TTS_URL}?{urlencode(params)}"
        return url

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """Synthesize text using iFlytek WebSocket API."""
        logger.info(f"[iFlytek] Synthesize: voice_id={request.voice_id}, text={request.text[:30]}...")
        if not all([self.app_id, self.api_key, self.api_secret]):
            raise ValueError("iFlytek credentials not configured")

        output_path = request.output_path
        if output_path is None:
            output_path = Path(tempfile.mktemp(suffix=".mp3"))

        # Build request body
        business_params = {
            "aue": "lame",  # MP3 format
            "sfl": 1,  # Enable streaming
            "tte": "UTF8",
            "ent": "intp65",
            "vcn": request.voice_id,
            "speed": self._parse_speed(request.rate),
            "volume": self._parse_volume(request.volume),
            "pitch": self._parse_pitch(request.pitch),
            "bgs": 0,
            "reg": "0",
            "rdn": "0"
        }

        # Split text into chunks if too long (iFlytek has 8KB limit per request)
        text = request.text
        audio_chunks = []

        # Use synchronous websocket in thread pool for compatibility
        import concurrent.futures

        def _synthesize_sync():
            import websocket as ws

            ws_url = self._generate_auth_url()
            chunks = []

            def on_message(ws, message):
                try:
                    data = json.loads(message)
                    if data.get("code") != 0:
                        logger.error(f"[iFlytek] API error: {data}")
                        ws.close()
                    else:
                        audio = data.get("data", {}).get("audio", "")
                        if audio:
                            chunks.append(base64.b64decode(audio))
                        if data.get("data", {}).get("status") == 2:
                            logger.info(f"[iFlytek] Synthesis complete, chunks={len(chunks)}")
                            ws.close()
                except Exception as e:
                    logger.error(f"[iFlytek] Parse error: {e}")
                    ws.close()

            def on_error(ws, error):
                logger.error(f"WebSocket error: {error}")

            def on_close(ws, close_status_code, close_msg):
                pass

            def on_open(ws):
                # Send request
                # Split text into chunks if too long (iFlytek has 8KB limit per request)
                # Each chunk should be around 1000 characters to be safe
                text_chunks = []
                current_chunk = ""
                for char in text:
                    current_chunk += char
                    if len(current_chunk) >= 1000:
                        text_chunks.append(current_chunk)
                        current_chunk = ""
                if current_chunk:
                    text_chunks.append(current_chunk)
                
                # Send first chunk with status 1
                for i, chunk in enumerate(text_chunks):
                    frame = {
                        "common": {
                            "app_id": self.app_id
                        },
                        "business": business_params,
                        "data": {
                            "status": 1 if i < len(text_chunks) - 1 else 2,  # 1 for intermediate, 2 for final
                            "text": base64.b64encode(chunk.encode('utf-8')).decode('utf-8')
                        }
                    }
                    logger.debug(f"[iFlytek] WebSocket request: chunk {i+1}/{len(text_chunks)}, vcn={business_params['vcn']}, app_id={self.app_id[:8]}...")
                    ws.send(json.dumps(frame))
                    # Add small delay between chunks to avoid rate limiting
                    if i < len(text_chunks) - 1:
                        import time
                        time.sleep(0.1)

            ws_client = ws.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            ws_client.run_forever()
            return chunks

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            audio_chunks = await loop.run_in_executor(pool, _synthesize_sync)

        # Write audio to file
        with open(output_path, "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)

        # Get duration
        duration_ms = self._get_duration_ms(output_path)

        return TTSResult(
            audio_path=output_path,
            duration_ms=duration_ms,
            word_boundaries=[],
            content_type="audio/mpeg"
        )

    def _parse_speed(self, rate: str) -> int:
        """Parse Edge TTS rate to iFlytek speed (0-100, default 50)."""
        if not rate or rate == "+0%":
            return 50
        try:
            val = float(rate.replace("+", "").replace("%", ""))
            return int(50 + val / 2)  # Map -50%~+50% to 25~75
        except:
            return 50

    def _parse_volume(self, volume: str) -> int:
        """Parse Edge TTS volume to iFlytek volume (0-100, default 50)."""
        if not volume or volume == "+0%":
            return 50
        try:
            val = float(volume.replace("+", "").replace("%", ""))
            return int(50 + val / 2)
        except:
            return 50

    def _parse_pitch(self, pitch: str) -> int:
        """Parse Edge TTS pitch to iFlytek pitch (0-100, default 50)."""
        if not pitch or pitch == "+0Hz":
            return 50
        try:
            val = float(pitch.replace("+", "").replace("Hz", ""))
            return int(50 + val / 10)  # Map roughly
        except:
            return 50

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
        """List iFlytek voices - try API first, fallback to local catalog."""
        if self._voices_cache is not None:
            voices = self._voices_cache
        else:
            # Try to fetch from API if credentials are configured
            if all([self.app_id, self.api_key, self.api_secret]):
                try:
                    api_voices = await self._fetch_voices_from_api()
                    if api_voices:
                        # Merge API voices with local defaults
                        local_voices = self._load_local_catalog()
                        voices = self._merge_voices(local_voices, api_voices)
                    else:
                        voices = self._load_local_catalog()
                except Exception as e:
                    logger.error(f"Failed to fetch iFlytek voices from API: {e}")
                    voices = self._load_local_catalog()
            else:
                voices = self._load_local_catalog()
            
            self._voices_cache = voices

        if lang:
            voices = [v for v in voices if v.get("language", "").lower().startswith(lang.lower())]

        return voices

    async def _fetch_voices_from_api(self) -> list[dict]:
        """Fetch available voices from iFlytek API.
        
        Note: iFlytek doesn't have a direct voice list API, but we can try
        to validate voices by testing them or use a predefined list that
        includes user's custom voices if they provide them.
        """
        # iFlytek doesn't provide a voice list API directly
        # Return empty list to use local catalog
        # If user has custom voices, they should be added to the local catalog
        return []

    def _merge_voices(self, local_voices: list[dict], api_voices: list[dict]) -> list[dict]:
        """Merge local and API voices, avoiding duplicates."""
        voice_map = {v["voice_id"]: v for v in local_voices}
        
        for v in api_voices:
            vid = v.get("voice_id")
            if vid and vid not in voice_map:
                # Ensure provider is set
                v["provider"] = "iflytek"
                voice_map[vid] = v
        
        return list(voice_map.values())

    def _load_local_catalog(self) -> list[dict]:
        """Load voices from local catalog file."""
        import json
        from pathlib import Path

        catalog_path = Path(__file__).parent.parent.parent / "catalog" / "voices_iflytek.json"
        if catalog_path.exists():
            with open(catalog_path, encoding='utf-8') as f:
                data = json.load(f)
                # Support both direct array and {voices: [...]} format
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "voices" in data:
                    return data["voices"]

        # Return default voices if catalog doesn't exist
        return self._get_default_voices()

    def _get_default_voices(self) -> list[dict]:
        """Return default iFlytek voice list."""
        return [
            # 用户提供的特色发音人
            {
                "voice_id": "x4_yezi",
                "display_name": "讯飞小露（普通话，女）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Female",
                "quality_score": 0.9,
                "narrator_fit_score": 0.85,
                "dialogue_fit_score": 0.9,
                "preview_url": None,
                "labels": ["普通话", "女声", "标准"],
                "provider": "iflytek"
            },
            {
                "voice_id": "x3_linlin",
                "display_name": "林林（闽南语，女）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Female",
                "quality_score": 0.88,
                "narrator_fit_score": 0.8,
                "dialogue_fit_score": 0.85,
                "preview_url": None,
                "labels": ["闽南语", "女声", "方言"],
                "provider": "iflytek"
            },
            {
                "voice_id": "x3_xiaoyue",
                "display_name": "小月（香港粤语，女）",
                "language": "zh",
                "locale": "zh-HK",
                "base_language": "Chinese",
                "gender": "Female",
                "quality_score": 0.88,
                "narrator_fit_score": 0.8,
                "dialogue_fit_score": 0.85,
                "preview_url": None,
                "labels": ["粤语", "女声", "香港"],
                "provider": "iflytek"
            },
            {
                "voice_id": "x4_lingxiaowan_en",
                "display_name": "聆小婉（普通话，女）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Female",
                "quality_score": 0.9,
                "narrator_fit_score": 0.85,
                "dialogue_fit_score": 0.9,
                "preview_url": None,
                "labels": ["普通话", "女声", "特色"],
                "provider": "iflytek"
            },
            {
                "voice_id": "x2_xiaorong",
                "display_name": "讯飞小蓉（四川话，女）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Female",
                "quality_score": 0.88,
                "narrator_fit_score": 0.8,
                "dialogue_fit_score": 0.85,
                "preview_url": None,
                "labels": ["四川话", "女声", "方言"],
                "provider": "iflytek"
            },
            {
                "voice_id": "x4_xiaobei",
                "display_name": "小北（东北话，女）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Female",
                "quality_score": 0.88,
                "narrator_fit_score": 0.8,
                "dialogue_fit_score": 0.85,
                "preview_url": None,
                "labels": ["东北话", "女声", "方言"],
                "provider": "iflytek"
            },
            {
                "voice_id": "x4_lingxiaoying_em_v2",
                "display_name": "聆小璎（普通话，女，情感增强）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Female",
                "quality_score": 0.92,
                "narrator_fit_score": 0.88,
                "dialogue_fit_score": 0.92,
                "preview_url": None,
                "labels": ["普通话", "女声", "情感增强"],
                "provider": "iflytek"
            },
            {
                "voice_id": "x4_lingbosong_bad_talk",
                "display_name": "聆伯松（反派老人，普通话，男）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Male",
                "quality_score": 0.9,
                "narrator_fit_score": 0.85,
                "dialogue_fit_score": 0.9,
                "preview_url": None,
                "labels": ["普通话", "男声", "反派", "老人"],
                "provider": "iflytek"
            },
            {
                "voice_id": "x4_lingbosong",
                "display_name": "聆伯松（普通话，男）",
                "language": "zh",
                "locale": "zh-CN",
                "base_language": "Chinese",
                "gender": "Male",
                "quality_score": 0.9,
                "narrator_fit_score": 0.88,
                "dialogue_fit_score": 0.85,
                "preview_url": None,
                "labels": ["普通话", "男声", "成熟"],
                "provider": "iflytek"
            },
        ]

    async def test_connection(self) -> bool:
        """Test iFlytek API connection."""
        if not all([self.app_id, self.api_key, self.api_secret]):
            return False

        try:
            # Try a minimal synthesis
            result = await self.synthesize(TTSRequest(
                text="测试",
                voice_id="x4_yezi"
            ))
            return result.audio_path is not None and result.audio_path.exists()
        except Exception as e:
            logger.error(f"iFlytek test failed: {e}")
            return False

    def get_quality_score(self, voice: dict) -> float:
        """Get quality score for iFlytek voice."""
        return voice.get("quality_score", 0.8)
