#!/usr/bin/env python3
"""
Scripts to Audiobook — FastAPI Backend
Uses Edge TTS for synthesis, pydub for merging, and a weighted scoring engine
for voice matching.

Supports multiple TTS providers: Edge TTS, ElevenLabs, iFlytek, Baidu.
"""
import asyncio
import json
import logging
import os
import re
import sys
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
import edge_tts
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

# ─── Logging Configuration ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging to file only (no console output)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log", encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

# Suppress uvicorn logs from console - redirect to file only
uvicorn_access = logging.getLogger("uvicorn.access")
uvicorn_access.handlers = [logging.FileHandler(LOG_DIR / "access.log", encoding='utf-8')]
uvicorn_access.propagate = False

uvicorn_error = logging.getLogger("uvicorn.error")
uvicorn_error.handlers = [logging.FileHandler(LOG_DIR / "error.log", encoding='utf-8')]
uvicorn_error.propagate = False

# Suppress fastapi and other third-party logs from console
for logger_name in ["fastapi", "starlette", "asyncio"]:
    log = logging.getLogger(logger_name)
    log.handlers = [logging.FileHandler(LOG_DIR / "app.log", encoding='utf-8')]
    log.propagate = False

# Import config manager
from config import config_manager


# Import database and TTS providers
from database import (
    init_db, ensure_db_initialized,
    create_album, get_albums, get_album, update_album, delete_album,
    create_audio_file, get_audio_files, get_audio_file, update_audio_file_album, delete_audio_file, update_audio_file
)

# Helper function to get TTS credentials from config_manager
async def get_raw_tts_credentials(provider: str) -> Optional[dict]:
    """Get raw credentials for a specific provider from config_manager."""
    if provider == "elevenlabs":
        api_key = config_manager.get("ELEVENLABS_API_KEY")
        if api_key:
            return {"api_key": api_key}
        return None
    elif provider == "iflytek":
        app_id = config_manager.get("IFLYTEK_APP_ID")
        api_key = config_manager.get("IFLYTEK_API_KEY")
        api_secret = config_manager.get("IFLYTEK_API_SECRET")
        if app_id and api_key and api_secret:
            return {
                "app_id": app_id,
                "api_key": api_key,
                "api_secret": api_secret
            }
        return None
    elif provider == "baidu":
        app_id = config_manager.get("BAIDU_APP_ID")
        api_key = config_manager.get("BAIDU_API_KEY")
        api_secret = config_manager.get("BAIDU_API_SECRET")
        if app_id and api_key and api_secret:
            return {
                "app_id": app_id,
                "api_key": api_key,
                "api_secret": api_secret
            }
        return None
    return None
from tts_providers import (
    TTSProvider, TTSRequest, TTSResult,
    EdgeTTSProvider, ElevenLabsProvider, iFlytekProvider, BaiduProvider
)

# ─── Paths ────────────────────────────────────────────────────────────────────
CATALOG_DIR = BASE_DIR / "catalog"

# Get storage path from config manager
def get_output_dir():
    """Get output directory from config manager"""
    storage_path = config_manager.get("STORAGE_PATH", str(BASE_DIR / "data" / "outputs"))
    output_dir = Path(storage_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

# ─── Load voice catalog ───────────────────────────────────────────────────────
with open(CATALOG_DIR / "voices_all.json") as f:
    ALL_VOICES: list[dict] = json.load(f)

with open(CATALOG_DIR / "voices_priority.json") as f:
    PRIORITY_VOICES: list[dict] = json.load(f)

VOICE_BY_ID: dict[str, dict] = {v["voice_id"]: v for v in ALL_VOICES}


# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await ensure_db_initialized()
    yield


# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Scripts to Audiobook API",
    version="1.0.0",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-memory job store ──────────────────────────────────────────────────────
jobs: dict[str, dict] = {}

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class VoiceDescriptionRequest(BaseModel):
    description: str
    exclude_voices: list[str] = []
    top_n: int = 5

class CharacterVoiceSpec(BaseModel):
    character_name: str
    voice_id: str
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"

class GenerateRequest(BaseModel):
    project_id: str
    lines: list[dict]          # [{character, text, line_index}]
    character_voices: list[CharacterVoiceSpec]
    include_subtitles: bool = True
    album_id: Optional[str] = None  # Album to save the audiobook to
    title: Optional[str] = None     # Title for the audiobook

class ParseScriptRequest(BaseModel):
    script_text: str
    voice_descriptions: Optional[str] = None

# ─────────────────────────────────────────────────────────────────────────────
# Script Parsing
# ─────────────────────────────────────────────────────────────────────────────

NARRATOR_ALIASES = {"narrator", "旁白", "narration", "narr", "voice over", "vo", "host", "主持"}

CHARACTER_COLORS = [
    "#60A5FA",  # blue-400
    "#F472B6",  # pink-400
    "#34D399",  # emerald-400
    "#FBBF24",  # amber-400
    "#A78BFA",  # violet-400
    "#F87171",  # red-400
    "#2DD4BF",  # teal-400
    "#FB923C",  # orange-400
    "#818CF8",  # indigo-400
    "#4ADE80",  # green-400
    "#E879F9",  # fuchsia-400
    "#FCD34D",  # yellow-300
]

NARRATOR_COLOR = "#94A3B8"  # slate-400 - calmer

def detect_language(text: str) -> str:
    """Detect if text is primarily Chinese or English."""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))
    total_alpha = len(re.findall(r'[a-zA-Z\u4e00-\u9fff]', text))
    if total_alpha == 0:
        return "en"
    return "zh" if chinese_chars / total_alpha > 0.4 else "en"

def parse_voice_descriptions(desc_text: str) -> dict[str, dict]:
    """Parse voice description lines into character metadata."""
    result = {}
    for line in desc_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Support both Chinese colon ：and English colon :
        parts = re.split(r'[：:]', line, maxsplit=1)
        if len(parts) != 2:
            continue
        char_name = parts[0].strip()
        desc = parts[1].strip()
        
        meta = parse_single_description(desc)
        result[char_name] = meta
    return result

def parse_single_description(desc: str) -> dict:
    """Parse a voice description string into structured metadata."""
    desc_lower = desc.lower()
    
    # Language detection
    language = "en"
    if any(kw in desc_lower for kw in ["中文", "chinese", "普通话", "mandarin", "cantonese", "粤语"]):
        language = "zh"
    if any(kw in desc_lower for kw in ["英文", "english", "英语"]):
        language = "en"
    
    # Accent detection
    accent = None
    accent_map = {
        "american": "en-US", "美国": "en-US", "us": "en-US",
        "british": "en-GB", "英国": "en-GB", "uk": "en-GB",
        "australian": "en-AU", "澳大利亚": "en-AU",
        "canadian": "en-CA", "加拿大": "en-CA",
        "indian": "en-IN", "印度": "en-IN",
        "irish": "en-IE", "爱尔兰": "en-IE",
        "new zealand": "en-NZ", "新西兰": "en-NZ",
        "singapore": "en-SG", "新加坡": "en-SG",
        "mainland": "zh-CN", "普通话": "zh-CN", "mandarin": "zh-CN",
        "cantonese": "zh-HK", "粤语": "zh-HK", "hong kong": "zh-HK", "香港": "zh-HK",
        "taiwan": "zh-TW", "台湾": "zh-TW",
    }
    for kw, locale in accent_map.items():
        if kw in desc_lower:
            accent = locale
            break
    
    # Gender detection — check female BEFORE male to avoid "fe-male" substring match
    gender = None
    if any(kw in desc_lower for kw in ["female", "woman", "girl", "女", "女性", "女孩", "女人"]):
        gender = "Female"
    elif re.search(r'\bmale\b|\bman\b|\bboy\b|男', desc_lower):
        gender = "Male"
    
    # Age detection
    age_bucket = "adult"
    if any(kw in desc_lower for kw in ["child", "kid", "young", "boy", "girl", "儿童", "小孩", "孩子", "小朋友"]):
        age_bucket = "child"
    elif any(kw in desc_lower for kw in ["senior", "elderly", "old", "mature", "elder", "老年", "老人", "年长", "奶奶", "爷爷"]):
        age_bucket = "senior"
    elif any(kw in desc_lower for kw in ["teen", "teenager", "young adult", "青少年", "青年"]):
        age_bucket = "young_adult"
    
    return {
        "language": language,
        "locale_hint": accent,
        "gender": gender,
        "age_bucket": age_bucket,
    }

def parse_script(script_text: str, voice_descriptions: Optional[str] = None) -> dict:
    """Parse a script into lines and characters."""
    lines = []
    characters = {}
    color_idx = 0
    narrator_color_used = False
    
    voice_desc_map = {}
    if voice_descriptions:
        voice_desc_map = parse_voice_descriptions(voice_descriptions)
    
    for raw_line in script_text.strip().splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        
        # Match "Character: text" with Chinese or English colon
        m = re.match(r'^([^：:]+)[：:](.+)$', raw_line)
        if not m:
            # treat as continuation / narration
            lines.append({
                "character": "Narrator",
                "text": raw_line,
                "line_index": len(lines),
            })
            char_name = "Narrator"
        else:
            char_name = m.group(1).strip()
            text = m.group(2).strip()
            lines.append({
                "character": char_name,
                "text": text,
                "line_index": len(lines),
            })
        
        if char_name not in characters:
            is_narrator = char_name.lower() in NARRATOR_ALIASES
            role_type = "narrator" if is_narrator else "character"
            
            if is_narrator:
                color = NARRATOR_COLOR
            else:
                color = CHARACTER_COLORS[color_idx % len(CHARACTER_COLORS)]
                color_idx += 1
            
            # Detect language from all lines of this character
            characters[char_name] = {
                "name": char_name,
                "role_type": role_type,
                "color": color,
                "language": "en",
                "locale_hint": None,
                "gender": None,
                "age_bucket": "adult",
                "line_count": 0,
            }
            
            # Merge voice descriptions if provided
            if char_name in voice_desc_map:
                desc_meta = voice_desc_map[char_name]
                characters[char_name].update({k: v for k, v in desc_meta.items() if v is not None})
        
        characters[char_name]["line_count"] = characters[char_name].get("line_count", 0) + 1
    
    # Detect language for each character from their lines
    for char_name, char_data in characters.items():
        if char_name not in voice_desc_map:  # only if no explicit description
            char_lines = [l["text"] for l in lines if l["character"] == char_name]
            all_text = " ".join(char_lines)
            characters[char_name]["language"] = detect_language(all_text)
    
    return {
        "lines": lines,
        "characters": list(characters.values()),
    }

# ─────────────────────────────────────────────────────────────────────────────
# Voice Matching Engine
# ─────────────────────────────────────────────────────────────────────────────

def score_voice(voice: dict, req: dict, assigned_voices: set[str]) -> tuple[float, list[str]]:
    """
    Score a voice against requirements.
    Returns (score 0-100, list of reasons).
    req keys: language, locale_hint, gender, age_bucket, role_type
    """
    score = 0.0
    reasons = []
    
    language = req.get("language", "en")
    locale_hint = req.get("locale_hint")
    gender = req.get("gender")
    age_bucket = req.get("age_bucket", "adult")
    role_type = req.get("role_type", "character")
    
    voice_lang = voice.get("base_language", "").lower()
    voice_locale = voice.get("locale", "")
    
    # ── Language match (weight: 30) ──────────────────────────────────────────
    lang_map = {"en": "english", "zh": "chinese"}
    if voice_lang == lang_map.get(language, language):
        score += 30
        reasons.append(f"Language: {voice.get('base_language', 'Unknown')}")
    else:
        return 0.0, ["Language mismatch"]  # hard filter
    
    # ── Locale/accent match (weight: 20) ─────────────────────────────────────
    if locale_hint:
        if voice_locale == locale_hint:
            score += 20
            reasons.append(f"Accent: {voice.get('accent_label', 'Unknown')}")
        elif voice_locale.startswith(locale_hint.split("-")[0]):
            score += 12
            reasons.append(f"Region: {voice.get('accent_label', 'Unknown')}")
        else:
            score += 3
    else:
        # Default locales get small bonus
        if language == "en" and voice_locale == "en-US":
            score += 5
        elif language == "zh" and voice_locale == "zh-CN":
            score += 5
    
    # ── Gender match (weight: 20) ─────────────────────────────────────────────
    if gender:
        voice_gender = voice.get("gender", "Unknown")
        if voice_gender.lower() == gender.lower():
            score += 20
            reasons.append(f"Gender: {gender}")
        # 性别不匹配不扣分，让其他因素决定
    else:
        score += 10  # neutral bonus
    
    # ── Age bucket match (weight: 20) ─────────────────────────────────────────
    voice_age = voice.get("age_bucket", "adult")
    if age_bucket == voice_age:
        score += 20
        reasons.append(f"Age: {age_bucket}")
    elif age_bucket == "young_adult" and voice_age == "adult":
        score += 15
        reasons.append(f"Age: adult (close to young adult)")
    elif age_bucket == "adult" and voice_age == "young_adult":
        score += 15
        reasons.append(f"Age: young adult (close to adult)")
    elif age_bucket in ("adult", "young_adult") and voice_age in ("adult", "young_adult"):
        score += 12
    elif age_bucket == "senior" and voice_age == "adult":
        score += 10  # adult can play senior
    elif age_bucket == "child" and voice_age == "child":
        score += 20
        reasons.append("Child voice")
    # 年龄不匹配只给少量分数
    
    # ── Role suitability (weight: 10) ─────────────────────────────────────────
    if role_type == "narrator":
        ns = voice.get("narrator_fit_score", 0.5)
        score += ns * 10
        if ns >= 0.7:
            reasons.append("Great narrator")
        elif ns >= 0.5:
            reasons.append("Good narrator")
    else:
        ds = voice.get("dialogue_fit_score", 0.5)
        score += ds * 10
        if ds >= 0.7:
            reasons.append("Great dialogue")
        elif ds >= 0.5:
            reasons.append("Good dialogue")
    
    # ── Diversity penalty ─────────────────────────────────────────────────────
    voice_id = voice.get("voice_id", "")
    if voice_id in assigned_voices:
        score -= 25  # 降低惩罚力度
        reasons.append("Already used")
    
    # ── Provider bonus ─────────────────────────────────────────────────────
    # Give bonus based on language and provider
    provider = voice.get("provider", "")
    if language == "en":
        # English: prefer ElevenLabs
        if provider == "elevenlabs":
            if gender:
                # If gender is specified, check for gender match
                voice_gender = voice.get("gender", "Unknown")
                if voice_gender.lower() == gender.lower():
                    score += 10  # Big bonus for ElevenLabs with gender match
                    reasons.append("ElevenLabs voice (gender match)")
                else:
                    score += 5  # Small bonus for ElevenLabs
                    reasons.append("ElevenLabs voice")
            else:
                # No gender specified, still prefer ElevenLabs
                score += 5  # Bonus for ElevenLabs
                reasons.append("ElevenLabs voice")
    elif language == "zh":
        # Chinese: prefer Baidu and iFlytek
        if provider in ["baidu", "iflytek"]:
            score += 10  # Big bonus for Chinese providers
            reasons.append(f"{provider.capitalize()} voice")
    
    # ── Ensure score is within 0-100 ─────────────────────────────────────────
    score = max(0, min(100, score))
    
    return round(score, 1), reasons

def match_voice(requirements: dict, exclude_voices: set[str], top_n: int = 5, all_voices: list[dict] = None) -> dict:
    """Find best matching voices for given requirements."""
    language = requirements.get("language", "en")
    
    # Use provided voices or default to ALL_VOICES
    voices_to_use = all_voices if all_voices is not None else ALL_VOICES
    
    # Filter to relevant language voices first (or all if needed)
    lang_map = {"en": "english", "zh": "chinese"}
    target_lang = lang_map.get(language, language).lower()
    
    candidate_voices = [v for v in voices_to_use if v.get("base_language", "").lower() == target_lang]
    if not candidate_voices:
        candidate_voices = voices_to_use  # fallback
    
    scored = []
    for voice in candidate_voices:
        score, reasons = score_voice(voice, requirements, exclude_voices)
        if score > 0:
            scored.append({
                "voice": voice,
                "score": score,
                "reasons": reasons,
            })
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    
    if not scored:
        # Fallback
        fallback = PRIORITY_VOICES[0] if PRIORITY_VOICES else ALL_VOICES[0]
        return {
            "selected": fallback,
            "score": 0,
            "reasons": ["Fallback selection"],
            "alternatives": [],
        }
    
    best = scored[0]
    return {
        "selected": best["voice"],
        "score": best["score"],
        "reasons": best["reasons"],
        "alternatives": [
            {"voice": s["voice"], "score": s["score"], "reasons": s["reasons"]}
            for s in scored[1:top_n]
        ],
    }

# ─────────────────────────────────────────────────────────────────────────────
# Audio Generation
# ─────────────────────────────────────────────────────────────────────────────

async def synthesize_segment(
    text: str,
    voice_id: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+0%",
    output_path: Path = None,
) -> tuple[Path, list[dict]]:
    """Synthesize a single text segment using the appropriate TTS provider. Returns (audio_path, word_boundaries)."""
    if output_path is None:
        output_path = get_output_dir() / f"seg_{uuid.uuid4().hex[:8]}.mp3"
    
    word_boundaries = []
    
    # Get all voices by provider to find the voice
    all_provider_voices = await get_voices_by_provider()
    
    # Find which provider has this voice
    provider_name = None
    voice_data = None
    for pname, pdata in all_provider_voices.items():
        for v in pdata.get("voices", []):
            if v.get("voice_id") == voice_id:
                provider_name = pname
                voice_data = v
                break
        if provider_name:
            break
    
    # If voice not found, default to Edge TTS
    if not provider_name:
        logger.warning(f"Voice {voice_id} not found, using Edge TTS as fallback")
        provider_name = "edge"
    
    logger.info(f"[SYNTHESIZE] Using provider: {provider_name} for voice: {voice_id}")
    
    # Use the appropriate provider for synthesis
    if provider_name == "edge":
        # Use Edge TTS
        communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch, volume=volume)
        
        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_boundaries.append({
                    "text": chunk.get("text", ""),
                    "offset": chunk.get("offset", 0),  # in 100ns units
                    "duration": chunk.get("duration", 0),
                })
        
        with open(output_path, "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)
    
    elif provider_name == "elevenlabs":
        # Use ElevenLabs
        from tts_providers import ElevenLabsProvider
        from tts_providers.base import TTSRequest
        
        # Get ElevenLabs credentials from config manager
        api_key = config_manager.get("ELEVENLABS_API_KEY")
        
        if not api_key:
            logger.warning("[SYNTHESIZE] ElevenLabs credentials not found, falling back to Edge TTS")
            # Fallback to Edge TTS
            communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch, volume=volume)
            
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    word_boundaries.append({
                        "text": chunk.get("text", ""),
                        "offset": chunk.get("offset", 0),
                        "duration": chunk.get("duration", 0),
                    })
            
            with open(output_path, "wb") as f:
                for chunk in audio_chunks:
                    f.write(chunk)
            # Set file permissions to allow reading
            output_path.chmod(0o644)
        else:
            logger.info(f"[SYNTHESIZE] ElevenLabs API key found, synthesizing with voice: {voice_id}")
            logger.debug(f"[SYNTHESIZE] API key (first 10 chars): {api_key[:10]}...")
            provider = ElevenLabsProvider(
                api_key=api_key
            )
            
            try:
                result = await provider.synthesize(TTSRequest(
                    text=text,
                    voice_id=voice_id,
                    rate=rate,
                    pitch=pitch,
                    volume=volume,
                    output_path=output_path
                ))
                logger.info(f"[SYNTHESIZE] ElevenLabs synthesis completed, duration: {result.duration_ms}ms, file size: {output_path.stat().st_size} bytes")
            except Exception as e:
                logger.error(f"[SYNTHESIZE] ElevenLabs synthesis failed: {e}")
                raise
            
            # ElevenLabs doesn't return word boundaries
            word_boundaries = []
            
            # Set file permissions to allow reading
            output_path.chmod(0o644)
    
    elif provider_name == "iflytek":
        # Use iFlytek
        from tts_providers import iFlytekProvider
        from tts_providers.base import TTSRequest
        
        # Get iFlytek credentials
        iflytek_creds = await get_raw_tts_credentials("iflytek")
        if not iflytek_creds:
            logger.warning("[SYNTHESIZE] iFlytek credentials not found, falling back to Edge TTS")
            # Fallback to Edge TTS
            communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch, volume=volume)
            
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    word_boundaries.append({
                        "text": chunk.get("text", ""),
                        "offset": chunk.get("offset", 0),
                        "duration": chunk.get("duration", 0),
                    })
            
            with open(output_path, "wb") as f:
                for chunk in audio_chunks:
                    f.write(chunk)
        else:
            provider = iFlytekProvider(
                app_id=iflytek_creds.get("app_id"),
                api_key=iflytek_creds.get("api_key"),
                api_secret=iflytek_creds.get("api_secret")
            )
            
            result = await provider.synthesize(TTSRequest(
                text=text,
                voice_id=voice_id,
                rate=rate,
                pitch=pitch,
                volume=volume,
                output_path=output_path
            ))
            
            # iFlytek doesn't return word boundaries
            word_boundaries = []
            
            # Set file permissions to allow reading
            output_path.chmod(0o644)
    
    elif provider_name == "baidu":
        # Use Baidu
        from tts_providers import BaiduProvider
        from tts_providers.base import TTSRequest
        
        # Get Baidu credentials
        baidu_creds = await get_raw_tts_credentials("baidu")
        if not baidu_creds:
            logger.warning("[SYNTHESIZE] Baidu credentials not found, falling back to Edge TTS")
            # Fallback to Edge TTS
            communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch, volume=volume)
            
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    word_boundaries.append({
                        "text": chunk.get("text", ""),
                        "offset": chunk.get("offset", 0),
                        "duration": chunk.get("duration", 0),
                    })
            
            with open(output_path, "wb") as f:
                for chunk in audio_chunks:
                    f.write(chunk)
        else:
            provider = BaiduProvider(
                app_id=baidu_creds.get("app_id"),
                api_key=baidu_creds.get("api_key"),
                api_secret=baidu_creds.get("api_secret")
            )
            
            result = await provider.synthesize(TTSRequest(
                text=text,
                voice_id=voice_id,
                rate=rate,
                pitch=pitch,
                volume=volume,
                output_path=output_path
            ))
            
            # Baidu doesn't return word boundaries
            word_boundaries = []
            
            # Set file permissions to allow reading
            output_path.chmod(0o644)
    
    else:
        # Fallback to Edge TTS
        logger.warning(f"Provider {provider_name} not supported, using Edge TTS as fallback")
        communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch, volume=volume)
        
        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_boundaries.append({
                    "text": chunk.get("text", ""),
                    "offset": chunk.get("offset", 0),  # in 100ns units
                    "duration": chunk.get("duration", 0),
                })
        
        with open(output_path, "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)
    
    return output_path, word_boundaries

def merge_audio_files(segment_paths: list[Path], output_path: Path) -> Path:
    """Merge multiple mp3 files into one using ffmpeg."""
    if not segment_paths:
        raise ValueError("No segments to merge")
    
    if len(segment_paths) == 1:
        import shutil
        shutil.copy(segment_paths[0], output_path)
        return output_path
    
    # Create a concat list file
    list_file = get_output_dir() / f"concat_{uuid.uuid4().hex[:8]}.txt"
    with open(list_file, "w") as f:
        for p in segment_paths:
            f.write(f"file '{p.absolute()}'\n")
    
    import subprocess
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c:a", "libmp3lame", "-q:a", "2", str(output_path)],
        capture_output=True, text=True
    )
    list_file.unlink(missing_ok=True)
    
    if result.returncode != 0:
        logger.error(f"[MERGE] ffmpeg error: {result.stderr}")
        raise RuntimeError(f"ffmpeg merge failed: {result.stderr}")
    
    return output_path

def get_mp3_duration_ms(path: Path) -> float:
    """Get MP3 duration in milliseconds using ffprobe."""
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", str(path)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                dur = float(stream.get("duration", 0))
                return dur * 1000
    return 0.0

async def generate_audiobook(job_id: str, request_data: dict):
    """Background task: generate full audiobook from script lines."""
    job = jobs[job_id]
    job["status"] = "processing"
    job["progress"] = 0
    
    lines = request_data["lines"]
    char_voices = {cv["character_name"]: cv for cv in request_data["character_voices"]}
    project_id = request_data["project_id"]
    album_id = request_data.get("album_id")
    title = request_data.get("title", f"Audiobook {project_id[:8]}")
    script_text = request_data.get("script_text", "")
    
    out_dir = get_output_dir() / project_id
    out_dir.mkdir(parents=True, exist_ok=True)
    
    segments = []
    current_time_ms = 0.0
    total_lines = len(lines)
    
    try:
        for i, line in enumerate(lines):
            char_name = line["character"]
            text = line["text"]
            line_idx = line["line_index"]
            
            if not text.strip():
                continue
            
            cv = char_voices.get(char_name)
            if not cv:
                # Find any assigned voice or default
                voice_id = "en-US-GuyNeural"
                rate, pitch, volume = "+0%", "+0Hz", "+0%"
            else:
                voice_id = cv["voice_id"]
                rate = cv.get("rate", "+0%")
                pitch = cv.get("pitch", "+0Hz")
                volume = cv.get("volume", "+0%")
            
            seg_path = out_dir / f"seg_{line_idx:04d}.mp3"
            
            try:
                seg_path, word_boundaries = await synthesize_segment(
                    text, voice_id, rate, pitch, volume, seg_path
                )
                duration_ms = get_mp3_duration_ms(seg_path)
                # Set file permissions to allow reading
                seg_path.chmod(0o644)
                
                # Check if audio file was successfully generated
                if duration_ms == 0 or seg_path.stat().st_size == 0:
                    raise Exception(f"Audio file is empty or duration is 0")
                
                # Success - mark segment as valid
                error_msg = None
                    
            except Exception as e:
                logger.error(f"[GENERATE] Error generating segment {line_idx}: {e}")
                job["errors"] = job.get("errors", []) + [f"Line {line_idx}: {str(e)}"]
                duration_ms = 0
                word_boundaries = []
                error_msg = str(e)
                # Create empty audio
                seg_path.write_bytes(b"")
            
            segments.append({
                "line_index": line_idx,
                "character": char_name,
                "text": text,
                "voice_id": voice_id,
                "audio_file": str(seg_path.absolute()),
                "start_ms": current_time_ms,
                "end_ms": current_time_ms + duration_ms,
                "duration_ms": duration_ms,
                "word_boundaries": word_boundaries,
                "error": error_msg,  # Add error status
            })
            
            current_time_ms += duration_ms
            job["progress"] = int((i + 1) / total_lines * 70)
        
        # Merge segments
        job["status"] = "merging"
        job["progress"] = 70
        
        valid_segs = [Path(s["audio_file"]) for s in segments if Path(s["audio_file"]).exists() and Path(s["audio_file"]).stat().st_size > 0]
        
        # Generate meaningful filename from title
        import re
        safe_title = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff\s-]', '_', title)
        safe_title = safe_title.strip().replace(' ', '_')[:50]
        merged_path = out_dir / f"{safe_title}.mp3"
        if valid_segs:
            merge_audio_files(valid_segs, merged_path)
            # Copy file for backward compatibility with frontend
            audiobook_mp3_path = out_dir / "audiobook.mp3"
            import shutil
            shutil.copy(merged_path, audiobook_mp3_path)
        else:
            # No valid segments, set job status to error
            job["status"] = "error"
            job["error"] = "All audio segments failed to generate. Please check your voice configurations and try again."
            raise RuntimeError("All audio segments failed to generate. Please check your voice configurations and try again.")
        
        # Generate subtitle / timeline data - include all segments with error status
        timeline = {
            "project_id": project_id,
            "total_duration_ms": current_time_ms,
            "segments": segments,
            "generated_at": time.time(),
        }
        
        timeline_path = out_dir / "timeline.json"
        with open(timeline_path, "w", encoding="utf-8") as f:
            json.dump(timeline, f, indent=2, ensure_ascii=False)
        
        # Generate SRT - include all segments
        srt_lines = []
        for idx, seg in enumerate(segments, 1):
            start = ms_to_srt_time(seg["start_ms"])
            end = ms_to_srt_time(seg["end_ms"])
            srt_lines.append(f"{idx}\n{start} --> {end}\n[{seg['character']}] {seg['text']}\n")
        
        srt_path = out_dir / "subtitles.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
        
        # Save to library (album_id can be null for "All Audio")
        try:
            # Build character data with colors from the generation request
            char_voices_map = {cv["character_name"]: cv for cv in request_data["character_voices"]}
            # Get character colors from segments (each segment has character and voice)
            char_colors = {}
            for seg in segments:
                char_name = seg["character"]
                if char_name not in char_colors:
                    char_colors[char_name] = seg.get("character_color")  # Store color if available
            
            # Build characters data with colors
            characters_data = []
            for cv in request_data["character_voices"]:
                char_name = cv["character_name"]
                # Find color from segment or use default
                color = char_colors.get(char_name)
                if not color:
                    # Assign default color based on character index
                    is_narrator = char_name.lower() in NARRATOR_ALIASES or char_name == "旁白"
                    if is_narrator:
                        color = NARRATOR_COLOR
                    else:
                        idx = len([c for c in characters_data if not (c["name"].lower() in NARRATOR_ALIASES or c["name"] == "旁白")])
                        color = CHARACTER_COLORS[idx % len(CHARACTER_COLORS)]
                characters_data.append({
                    "name": char_name,
                    "voice_id": cv["voice_id"],
                    "color": color
                })
            
            await create_audio_file(
                id=str(uuid.uuid4()),
                title=title,
                project_id=project_id,
                file_path=str(merged_path),
                duration_ms=int(current_time_ms),
                segment_count=len(segments),
                timeline_path=str(timeline_path),
                srt_path=str(srt_path),
                album_id=album_id if album_id else None,
                script_text=script_text,
                characters=characters_data
            )
        except Exception as e:
            logger.error(f"Failed to save to library: {e}")
        
        job["status"] = "done"
        job["progress"] = 100
        job["result"] = {
            "project_id": project_id,
            "audio_url": f"/api/audio/{project_id}/{safe_title}.mp3",
            "timeline_url": f"/api/audio/{project_id}/timeline.json",
            "srt_url": f"/api/audio/{project_id}/subtitles.srt",
            "total_duration_ms": current_time_ms,
            "segment_count": len(segments),
        }
    
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        raise

def ms_to_srt_time(ms: float) -> str:
    """Convert milliseconds to SRT time format HH:MM:SS,mmm."""
    total_s = int(ms // 1000)
    ms_part = int(ms % 1000)
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms_part:03d}"

# ─────────────────────────────────────────────────────────────────────────────
# API Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}

@app.get("/api/voices")
def get_voices(lang: Optional[str] = None, gender: Optional[str] = None, locale: Optional[str] = None):
    """Return voices, optionally filtered."""
    voices = ALL_VOICES
    if lang:
        lang_map = {"en": "English", "zh": "Chinese"}
        target = lang_map.get(lang.lower(), lang)
        voices = [v for v in voices if v["base_language"].lower() == target.lower()]
    if gender:
        voices = [v for v in voices if v["gender"].lower() == gender.lower()]
    if locale:
        voices = [v for v in voices if v["locale"] == locale]
    return {"voices": voices, "count": len(voices)}

@app.get("/api/voices/priority")
def get_priority_voices():
    """Return English + Chinese priority voices."""
    return {"voices": PRIORITY_VOICES, "count": len(PRIORITY_VOICES)}

@app.post("/api/voices/match")
def match_voice_endpoint(req: VoiceDescriptionRequest):
    """Match a voice description to best candidates."""
    meta = parse_single_description(req.description)
    result = match_voice(meta, set(req.exclude_voices), req.top_n)
    return result

@app.post("/api/script/parse")
async def parse_script_endpoint(req: ParseScriptRequest):
    """Parse a script and auto-match voices for each character."""
    parsed = parse_script(req.script_text, req.voice_descriptions)
    
    # Get all voices from all providers
    all_provider_voices = await get_voices_by_provider()
    
    # Combine all voices into a single list
    all_voices_combined = ALL_VOICES.copy()
    for provider_data in all_provider_voices.values():
        all_voices_combined.extend(provider_data.get("voices", []))
    
    # Auto-match voices for each character
    assigned_voices: set[str] = set()
    for char in parsed["characters"]:
        requirements = {
            "language": char["language"],
            "locale_hint": char.get("locale_hint"),
            "gender": char.get("gender"),
            "age_bucket": char.get("age_bucket", "adult"),
            "role_type": char["role_type"],
        }
        match_result = match_voice(requirements, assigned_voices, top_n=5, all_voices=all_voices_combined)
        selected = match_result["selected"]
        char["assigned_voice"] = selected["voice_id"]
        char["voice_data"] = selected
        char["match_score"] = match_result["score"]
        char["match_reasons"] = match_result["reasons"]
        char["voice_alternatives"] = match_result["alternatives"]
        assigned_voices.add(selected["voice_id"])
    
    return parsed

@app.post("/api/generate")
async def generate_endpoint(req: GenerateRequest, background_tasks: BackgroundTasks):
    """Start audiobook generation job."""
    job_id = uuid.uuid4().hex
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "project_id": req.project_id,
        "created_at": time.time(),
    }
    
    request_data = req.model_dump()
    background_tasks.add_task(generate_audiobook, job_id, request_data)
    
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    """Poll generation job status."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/api/audio/{project_id}/{filename}")
def serve_audio(project_id: str, filename: str):
    """Serve generated audio / timeline files."""
    file_path = get_output_dir() / project_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    media_type = "audio/mpeg" if filename.endswith(".mp3") else "application/json"
    if filename.endswith(".srt"):
        media_type = "text/plain"
    
    return FileResponse(str(file_path), media_type=media_type)

@app.post("/api/preview")
async def preview_voice(voice_id: str, text: str, rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%"):
    """Generate a short audio preview for a voice (supports all providers)."""
    logger.info(f"[PREVIEW] voice_id={voice_id}, text={text[:30]}...")
    if len(text) > 500:
        text = text[:500]
    
    preview_path = get_output_dir() / f"preview_{uuid.uuid4().hex[:8]}.mp3"
    
    try:
        # Check if it's an Edge TTS voice
        # Get all voices by provider to find the voice
        all_provider_voices = await get_voices_by_provider()
        
        # Find which provider has this voice
        provider_name = None
        for pname, pdata in all_provider_voices.items():
            for v in pdata.get("voices", []):
                if v.get("voice_id") == voice_id:
                    provider_name = pname
                    break
            if provider_name:
                break
        
        logger.info(f"[PREVIEW] Found provider: {provider_name} for voice: {voice_id}")

        if provider_name == "edge":
            logger.info(f"[PREVIEW] Using Edge TTS")
            await synthesize_segment(text, voice_id, rate, pitch, volume, preview_path)
        else:
            if not provider_name:
                logger.warning(f"[PREVIEW] Voice not found: {voice_id}")
                raise HTTPException(status_code=404, detail=f"Voice {voice_id} not found")

            # Use the appropriate provider for preview
            from tts_providers import ElevenLabsProvider, iFlytekProvider, BaiduProvider

            if provider_name == "elevenlabs":
                logger.info(f"[PREVIEW] Using ElevenLabs")
                creds = await get_raw_tts_credentials("elevenlabs")
                logger.debug(f"[PREVIEW] ElevenLabs creds: {creds}")
                if not creds:
                    raise HTTPException(status_code=400, detail="ElevenLabs credentials not configured")
                provider = ElevenLabsProvider(api_key=creds.get("api_key"))
            elif provider_name == "iflytek":
                creds = await get_raw_tts_credentials("iflytek")
                if not creds:
                    raise HTTPException(status_code=400, detail="iFlytek credentials not configured")
                provider = iFlytekProvider(
                    app_id=creds.get("app_id"),
                    api_key=creds.get("api_key"),
                    api_secret=creds.get("api_secret")
                )
            elif provider_name == "baidu":
                creds = await get_raw_tts_credentials("baidu")
                if not creds:
                    raise HTTPException(status_code=400, detail="Baidu credentials not configured")
                provider = BaiduProvider(
                    app_id=creds.get("app_id"),
                    api_key=creds.get("api_key"),
                    api_secret=creds.get("api_secret")
                )
            else:
                raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_name}")
            
            # Generate preview using the provider
            from tts_providers import TTSRequest
            logger.info(f"[PREVIEW] Synthesizing with {provider_name}")
            result = await provider.synthesize(TTSRequest(
                text=text,
                voice_id=voice_id,
                rate=rate,
                pitch=pitch,
                volume=volume,
                output_path=preview_path
            ))
            logger.info(f"[PREVIEW] Synthesis result: {result}")
            logger.info(f"[PREVIEW] Preview saved to: {preview_path}")
            # Audio is already saved to preview_path by the provider
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PREVIEW] Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    
    return FileResponse(str(preview_path), media_type="audio/mpeg",
                       headers={"Cache-Control": "no-cache"})

@app.get("/api/catalog/stats")
def catalog_stats():
    with open(CATALOG_DIR / "catalog_stats.json") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════════════
# Library / Album API Routes
# ═══════════════════════════════════════════════════════════════════════════════

from pydantic import Field
import uuid

class AlbumCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    cover_image: Optional[str] = None

class AlbumUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None

class AudioFileMoveRequest(BaseModel):
    album_id: Optional[str] = None

class SettingsUpdateRequest(BaseModel):
    key: str
    value: Any


# ─── Album Routes ─────────────────────────────────────────────────────────────

@app.get("/api/library/albums")
async def list_albums():
    """Get all albums with audio file counts."""
    albums = await get_albums()
    return {"albums": albums}


@app.post("/api/library/albums")
async def create_album_endpoint(req: AlbumCreateRequest):
    """Create a new album."""
    album_id = str(uuid.uuid4())
    album = await create_album(
        id=album_id,
        name=req.name,
        description=req.description,
        cover_image=req.cover_image
    )
    return album


@app.get("/api/library/albums/{album_id}")
async def get_album_endpoint(album_id: str):
    """Get a single album by ID."""
    album = await get_album(album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    return album


@app.put("/api/library/albums/{album_id}")
async def update_album_endpoint(album_id: str, req: AlbumUpdateRequest):
    """Update an album."""
    album = await update_album(
        album_id=album_id,
        name=req.name,
        description=req.description,
        cover_image=req.cover_image
    )
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    return album


@app.delete("/api/library/albums/{album_id}")
async def delete_album_endpoint(album_id: str):
    """Delete an album."""
    success = await delete_album(album_id)
    if not success:
        raise HTTPException(status_code=404, detail="Album not found")
    return {"success": True}


# ─── Audio File Routes ────────────────────────────────────────────────────────

@app.get("/api/library/audio-files")
async def list_audio_files(album_id: Optional[str] = None):
    """Get all audio files, optionally filtered by album."""
    files = await get_audio_files(album_id)
    return {"audio_files": files}


@app.get("/api/library/audio-files/{audio_id}")
async def get_audio_file_endpoint(audio_id: str):
    """Get a single audio file by ID."""
    audio = await get_audio_file(audio_id)
    if not audio:
        raise HTTPException(status_code=404, detail="Audio file not found")
    return audio


@app.delete("/api/library/audio-files/{audio_id}")
async def delete_audio_file_endpoint(audio_id: str):
    """Delete an audio file record and its associated files."""
    audio = await get_audio_file(audio_id)
    if not audio:
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    # Delete associated files
    try:
        file_path = Path(audio["file_path"])
        if file_path.exists():
            file_path.unlink()
        
        if audio.get("timeline_path"):
            timeline_path = Path(audio["timeline_path"])
            if timeline_path.exists():
                timeline_path.unlink()
        
        if audio.get("srt_path"):
            srt_path = Path(audio["srt_path"])
            if srt_path.exists():
                srt_path.unlink()
    except Exception as e:
        logger.error(f"Error deleting files: {e}")
    
    success = await delete_audio_file(audio_id)
    return {"success": success}


@app.put("/api/library/audio-files/{audio_id}/album")
async def move_audio_file_endpoint(audio_id: str, req: AudioFileMoveRequest):
    """Move an audio file to a different album."""
    audio = await update_audio_file_album(audio_id, req.album_id)
    if not audio:
        raise HTTPException(status_code=404, detail="Audio file not found")
    return audio


class AudioFileUpdateRequest(BaseModel):
    title: Optional[str] = None


@app.put("/api/library/audio-files/{audio_id}")
async def update_audio_file_endpoint(audio_id: str, req: AudioFileUpdateRequest):
    """Update an audio file record."""
    audio = await update_audio_file(audio_id, req.title)
    if not audio:
        raise HTTPException(status_code=404, detail="Audio file not found")
    return audio


# ─── Settings Routes ──────────────────────────────────────────────────────────

@app.get("/api/library/settings")
async def get_settings():
    """Get all library settings."""
    # Get storage path from config manager, fallback to OUTPUT_DIR
    storage_path = config_manager.get("STORAGE_PATH") or str(OUTPUT_DIR)
    settings = {
        "storage_path": storage_path
    }
    return {"settings": settings}


@app.get("/api/library/settings/{key}")
async def get_setting_endpoint(key: str):
    """Get a specific setting."""
    if key == "storage_path":
        # Get storage path from config manager, fallback to OUTPUT_DIR
        storage_path = config_manager.get("STORAGE_PATH") or str(OUTPUT_DIR)
        return {"key": key, "value": storage_path}
    # For other settings, return None as they are not supported anymore
    return {"key": key, "value": None}


@app.put("/api/library/settings/{key}")
async def update_setting_endpoint(key: str, req: SettingsUpdateRequest):
    """Update a setting."""
    if key == "storage_path":
        # Update storage path using config manager
        config_manager.set("STORAGE_PATH", req.value)
        return {"key": key, "value": req.value, "message": "Setting updated successfully"}
    # For other settings, return error
    raise HTTPException(
        status_code=400, 
        detail="Only storage_path setting is supported for update"
    )


class StorageMigrateRequest(BaseModel):
    new_path: str


@app.post("/api/library/storage/migrate")
async def migrate_storage_endpoint(req: StorageMigrateRequest):
    """Migrate all audio files from old storage to new storage path."""
    import shutil
    
    old_path = get_output_dir()
    new_path = Path(req.new_path)
    
    try:
        # Ensure new path exists
        new_path.mkdir(parents=True, exist_ok=True)
        
        # Get all audio files from database
        audio_files = await get_audio_files()
        
        migrated = 0
        failed = 0
        errors = []
        
        for audio in audio_files:
            try:
                # Get the old file path
                old_file_path = Path(audio["file_path"])
                
                # Skip if file doesn't exist in old location
                if not old_file_path.exists():
                    continue
                
                # Calculate relative path from old output dir
                try:
                    rel_path = old_file_path.relative_to(old_path)
                except ValueError:
                    # File is not under old_path, use just the filename
                    rel_path = Path(old_file_path.name)
                
                # New file path
                new_file_path = new_path / rel_path
                new_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy the main audio file
                shutil.copy2(old_file_path, new_file_path)
                
                # Copy timeline file if exists
                if audio.get("timeline_path"):
                    old_timeline = Path(audio["timeline_path"])
                    if old_timeline.exists():
                        try:
                            rel_timeline = old_timeline.relative_to(old_path)
                        except ValueError:
                            rel_timeline = Path(old_timeline.name)
                        new_timeline = new_path / rel_timeline
                        new_timeline.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(old_timeline, new_timeline)
                
                # Copy SRT file if exists
                if audio.get("srt_path"):
                    old_srt = Path(audio["srt_path"])
                    if old_srt.exists():
                        try:
                            rel_srt = old_srt.relative_to(old_path)
                        except ValueError:
                            rel_srt = Path(old_srt.name)
                        new_srt = new_path / rel_srt
                        new_srt.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(old_srt, new_srt)
                
                # Update database record with new paths
                from database import aiosqlite, DB_PATH
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        """UPDATE audio_files 
                           SET file_path = ?, timeline_path = ?, srt_path = ?
                           WHERE id = ?""",
                        (
                            str(new_file_path),
                            str(new_path / rel_path.parent / "timeline.json") if audio.get("timeline_path") else None,
                            str(new_path / rel_path.parent / "subtitles.srt") if audio.get("srt_path") else None,
                            audio["id"]
                        )
                    )
                    await db.commit()
                
                migrated += 1
            except Exception as e:
                failed += 1
                errors.append(f"{audio.get('title', 'Unknown')}: {str(e)}")
        
        # Update storage path in config
        config_manager.set("STORAGE_PATH", str(new_path))
        
        return {
            "success": True,
            "migrated": migrated,
            "failed": failed,
            "errors": errors,
            "new_path": str(new_path),
            "message": "Storage path updated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


@app.post("/api/library/storage/cleanup-old")
async def cleanup_old_storage_endpoint(req: StorageMigrateRequest):
    """Remove files from old storage after migration (use with caution)."""
    import shutil
    
    old_path = get_output_dir()
    new_path = Path(req.new_path)
    
    try:
        # Verify new path exists and has files
        if not new_path.exists():
            raise HTTPException(status_code=400, detail="New path does not exist")
        
        # Get all audio files from database to verify they're in new location
        audio_files = await get_audio_files()
        
        # Check if files exist in new location
        all_migrated = True
        for audio in audio_files:
            new_file_path = Path(audio["file_path"])
            if not new_file_path.exists():
                all_migrated = False
                break
        
        if not all_migrated:
            raise HTTPException(status_code=400, detail="Not all files are migrated to new location")
        
        # Remove old directory
        if old_path.exists() and old_path != new_path:
            shutil.rmtree(old_path, ignore_errors=True)
        
        return {"success": True, "message": "Old storage cleaned up"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


# ─── TTS Provider Credentials Routes ──────────────────────────────────────────

class TTSCredentialsRequest(BaseModel):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    app_id: Optional[str] = None


@app.get("/api/tts-providers")
async def list_tts_providers():
    """List all TTS providers with their status."""
    from tts_providers import EdgeTTSProvider, ElevenLabsProvider, iFlytekProvider, BaiduProvider
    
    # Check credentials from config manager
    elevenlabs_configured = bool(config_manager.get("ELEVENLABS_API_KEY"))
    iflytek_configured = bool(config_manager.get("IFLYTEK_APP_ID") and config_manager.get("IFLYTEK_API_KEY") and config_manager.get("IFLYTEK_API_SECRET"))
    baidu_configured = bool(config_manager.get("BAIDU_APP_ID") and config_manager.get("BAIDU_API_KEY") and config_manager.get("BAIDU_API_SECRET"))
    
    providers = [
        {"name": "edge", "display_name": "Edge TTS", "requires_auth": False, "is_configured": True},
        {"name": "elevenlabs", "display_name": "ElevenLabs", "requires_auth": True, "is_configured": elevenlabs_configured},
        {"name": "iflytek", "display_name": "科大讯飞", "requires_auth": True, "is_configured": iflytek_configured},
        {"name": "baidu", "display_name": "百度语音", "requires_auth": True, "is_configured": baidu_configured},
    ]
    
    return {"providers": providers}


@app.get("/api/tts-providers/{provider}/credentials")
async def get_tts_provider_credentials(provider: str):
    """Get credentials for a specific TTS provider (masked)."""
    # Edge TTS doesn't require authentication, return empty object
    if provider == "edge":
        return {"api_key_masked": None, "api_secret_masked": None, "app_id": None}
    
    # Get credentials from config manager
    if provider == "elevenlabs":
        api_key = config_manager.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise HTTPException(status_code=404, detail="Credentials not found")
        return {
            "api_key_masked": api_key[:4] + "****" + api_key[-4:],
            "api_secret_masked": None,
            "app_id": None
        }
    elif provider == "iflytek":
        app_id = config_manager.get("IFLYTEK_APP_ID")
        api_key = config_manager.get("IFLYTEK_API_KEY")
        api_secret = config_manager.get("IFLYTEK_API_SECRET")
        if not (app_id and api_key and api_secret):
            raise HTTPException(status_code=404, detail="Credentials not found")
        return {
            "api_key_masked": api_key[:4] + "****" + api_key[-4:],
            "api_secret_masked": api_secret[:4] + "****" + api_secret[-4:],
            "app_id": app_id
        }
    elif provider == "baidu":
        app_id = config_manager.get("BAIDU_APP_ID")
        api_key = config_manager.get("BAIDU_API_KEY")
        api_secret = config_manager.get("BAIDU_API_SECRET")
        if not (app_id and api_key and api_secret):
            raise HTTPException(status_code=404, detail="Credentials not found")
        return {
            "api_key_masked": api_key[:4] + "****" + api_key[-4:],
            "api_secret_masked": api_secret[:4] + "****" + api_secret[-4:],
            "app_id": app_id
        }
    else:
        raise HTTPException(status_code=404, detail="Provider not found")


@app.put("/api/tts-providers/{provider}/credentials")
async def save_tts_provider_credentials(provider: str, req: TTSCredentialsRequest):
    """Save credentials for a TTS provider."""
    # Save credentials using config manager
    if provider == "elevenlabs":
        if req.api_key:
            config_manager.set("ELEVENLABS_API_KEY", req.api_key)
    elif provider == "iflytek":
        if req.app_id:
            config_manager.set("IFLYTEK_APP_ID", req.app_id)
        if req.api_key:
            config_manager.set("IFLYTEK_API_KEY", req.api_key)
        if req.api_secret:
            config_manager.set("IFLYTEK_API_SECRET", req.api_secret)
    elif provider == "baidu":
        if req.app_id:
            config_manager.set("BAIDU_APP_ID", req.app_id)
        if req.api_key:
            config_manager.set("BAIDU_API_KEY", req.api_key)
        if req.api_secret:
            config_manager.set("BAIDU_API_SECRET", req.api_secret)
    else:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    return {"message": "Credentials saved successfully"}


@app.delete("/api/tts-providers/{provider}/credentials")
async def delete_tts_provider_credentials(provider: str):
    """Delete credentials for a TTS provider."""
    # Delete credentials using config manager
    if provider == "elevenlabs":
        config_manager.delete("ELEVENLABS_API_KEY")
    elif provider == "iflytek":
        config_manager.delete("IFLYTEK_APP_ID")
        config_manager.delete("IFLYTEK_API_KEY")
        config_manager.delete("IFLYTEK_API_SECRET")
    elif provider == "baidu":
        config_manager.delete("BAIDU_APP_ID")
        config_manager.delete("BAIDU_API_KEY")
        config_manager.delete("BAIDU_API_SECRET")
    else:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    return {"message": "Credentials deleted successfully"}


# ─── Enhanced Voice Catalog Routes ────────────────────────────────────────────

@app.get("/api/voices/by-provider")
async def get_voices_by_provider(provider: Optional[str] = None, lang: Optional[str] = None):
    """Get voices organized by provider."""
    from tts_providers import EdgeTTSProvider, ElevenLabsProvider, iFlytekProvider, BaiduProvider
    
    result = {}
    
    # Edge TTS voices (always available)
    edge_provider = EdgeTTSProvider()
    edge_voices = await edge_provider.list_voices(lang)
    result["edge"] = {
        "name": "edge",
        "display_name": "Edge TTS",
        "voices": edge_voices,
        "is_available": True
    }
    
    # iFlytek voices (if configured)
    try:
        # Get credentials from config manager
        app_id = config_manager.get("IFLYTEK_APP_ID")
        api_key = config_manager.get("IFLYTEK_API_KEY")
        api_secret = config_manager.get("IFLYTEK_API_SECRET")
        
        iflytek_provider = iFlytekProvider(
            app_id=app_id,
            api_key=api_key,
            api_secret=api_secret
        )
        iflytek_voices = await iflytek_provider.list_voices(lang)
        result["iflytek"] = {
            "name": "iflytek",
            "display_name": "科大讯飞",
            "voices": iflytek_voices,
            "is_available": app_id and api_key and api_secret
        }
    except Exception as e:
        result["iflytek"] = {"name": "iflytek", "display_name": "科大讯飞", "voices": [], "is_available": False, "error": str(e)}
    
    # Baidu voices (if configured)
    try:
        # Get credentials from config manager
        app_id = config_manager.get("BAIDU_APP_ID")
        api_key = config_manager.get("BAIDU_API_KEY")
        api_secret = config_manager.get("BAIDU_API_SECRET")
        
        baidu_provider = BaiduProvider(
            app_id=app_id,
            api_key=api_key,
            api_secret=api_secret
        )
        baidu_voices = await baidu_provider.list_voices(lang)
        result["baidu"] = {
            "name": "baidu",
            "display_name": "百度语音",
            "voices": baidu_voices,
            "is_available": app_id and api_key and api_secret
        }
    except Exception as e:
        result["baidu"] = {"name": "baidu", "display_name": "百度语音", "voices": [], "is_available": False, "error": str(e)}
    
    # ElevenLabs voices (if configured)
    try:
        # Get credentials from config manager
        api_key = config_manager.get("ELEVENLABS_API_KEY")
        
        elevenlabs_provider = ElevenLabsProvider(
            api_key=api_key
        )
        elevenlabs_voices = await elevenlabs_provider.list_voices(lang)
        result["elevenlabs"] = {
            "name": "elevenlabs",
            "display_name": "ElevenLabs",
            "voices": elevenlabs_voices,
            "is_available": api_key is not None
        }
    except Exception as e:
        result["elevenlabs"] = {"name": "elevenlabs", "display_name": "ElevenLabs", "voices": [], "is_available": False, "error": str(e)}
    
    # Filter by provider if specified
    if provider:
        return {provider: result.get(provider, {"voices": [], "is_available": False})}
    
    return result


@app.get("/api/voices/featured")
async def get_featured_voices():
    """Get featured/premium voices from each provider.
    
    Featured voices are selected based on:
    1. Priority voices first (for Edge TTS)
    2. High quality scores (narrator_fit_score + dialogue_fit_score)
    3. Provider availability
    """
    from tts_providers import EdgeTTSProvider, ElevenLabsProvider, iFlytekProvider, BaiduProvider
    
    featured = []
    
    def calc_quality(v):
        """Calculate quality score from narrator and dialogue fit scores."""
        narrator = v.get("narrator_fit_score", 0.5)
        dialogue = v.get("dialogue_fit_score", 0.5)
        return (narrator + dialogue) / 2
    
    # Edge TTS featured voices - use priority voices first, then top quality
    edge_provider = EdgeTTSProvider()
    edge_voices = await edge_provider.list_voices()
    
    # Get priority voices (Chinese and English)
    priority_voice_ids = {v["voice_id"] for v in PRIORITY_VOICES}
    priority_edge = [v for v in edge_voices if v["voice_id"] in priority_voice_ids]
    other_edge = [v for v in edge_voices if v["voice_id"] not in priority_voice_ids]
    
    # Sort by quality score
    priority_edge_sorted = sorted(priority_edge, key=calc_quality, reverse=True)
    other_edge_sorted = sorted(other_edge, key=calc_quality, reverse=True)
    
    # Take top 3 priority voices + top 2 other voices
    selected_edge = priority_edge_sorted[:3] + other_edge_sorted[:2]
    featured.extend([
        {**v, "provider": "edge", "provider_display": "Edge TTS"} 
        for v in selected_edge
    ])
    
    # iFlytek featured voices - top quality voices
    try:
        iflytek_creds = await get_raw_tts_credentials("iflytek")
        if iflytek_creds:
            iflytek_provider = iFlytekProvider(
                app_id=iflytek_creds.get("app_id"),
                api_key=iflytek_creds.get("api_key"),
                api_secret=iflytek_creds.get("api_secret")
            )
            iflytek_voices = await iflytek_provider.list_voices()
            # Filter for Chinese voices only, sort by quality
            iflytek_zh = [v for v in iflytek_voices if v.get("language") == "zh" or v.get("locale", "").startswith("zh")]
            iflytek_sorted = sorted(iflytek_zh, key=calc_quality, reverse=True)
            featured.extend([
                {**v, "provider": "iflytek", "provider_display": "科大讯飞"} 
                for v in iflytek_sorted[:3]
            ])
    except Exception as e:
        logger.error(f"[Featured] iFlytek error: {e}")
    
    # Baidu featured voices - top quality voices
    try:
        baidu_creds = await get_raw_tts_credentials("baidu")
        if baidu_creds:
            baidu_provider = BaiduProvider(
                app_id=baidu_creds.get("app_id"),
                api_key=baidu_creds.get("api_key"),
                api_secret=baidu_creds.get("api_secret")
            )
            baidu_voices = await baidu_provider.list_voices()
            baidu_sorted = sorted(baidu_voices, key=calc_quality, reverse=True)
            featured.extend([
                {**v, "provider": "baidu", "provider_display": "百度语音"} 
                for v in baidu_sorted[:3]
            ])
    except Exception as e:
        logger.error(f"[Featured] Baidu error: {e}")
    
    # ElevenLabs featured voices
    try:
        # Get credentials from environment variables
        api_key = os.getenv("ELEVENLABS_API_KEY")
        
        if api_key:
            elevenlabs_provider = ElevenLabsProvider(api_key=api_key)
            elevenlabs_voices = await elevenlabs_provider.list_voices()
            # Sort by quality and take top 3
            elevenlabs_sorted = sorted(elevenlabs_voices, key=calc_quality, reverse=True)
            featured.extend([
                {**v, "provider": "elevenlabs", "provider_display": "ElevenLabs"} 
                for v in elevenlabs_sorted[:3]
            ])
    except Exception as e:
        logger.error(f"[Featured] ElevenLabs error: {e}")
    
    # Sort all featured voices by quality score (using calc_quality)
    featured.sort(key=calc_quality, reverse=True)
    
    return {"voices": featured}


# ─────────────────────────────────────────────────────────────────────────────
# Voice Management API
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/voices/{provider}/custom")
async def get_custom_voices(provider: str):
    """Get custom voices for a specific provider."""
    from pathlib import Path
    import json
    
    # Validate provider
    valid_providers = ["elevenlabs", "iflytek", "baidu", "edge"]
    if provider not in valid_providers:
        return {"error": f"Invalid provider. Valid providers: {valid_providers}"}
    
    # Load custom voices from catalog file
    catalog_path = Path(__file__).parent.parent / "catalog" / f"voices_{provider}.json"
    
    if not catalog_path.exists():
        return {"voices": []}
    
    try:
        with open(catalog_path, encoding='utf-8') as f:
            data = json.load(f)
            # Support both direct array and {voices: [...]} format
            if isinstance(data, list):
                return {"voices": data}
            elif isinstance(data, dict) and "voices" in data:
                return {"voices": data["voices"]}
            else:
                return {"voices": []}
    except Exception as e:
        return {"error": f"Failed to load custom voices: {str(e)}"}


@app.post("/api/voices/{provider}/custom")
async def add_custom_voice(provider: str, voice: dict):
    """Add a custom voice for a specific provider."""
    from pathlib import Path
    import json
    
    # Validate provider
    valid_providers = ["elevenlabs", "iflytek", "baidu", "edge"]
    if provider not in valid_providers:
        return {"error": f"Invalid provider. Valid providers: {valid_providers}"}
    
    # Validate voice data
    required_fields = ["voice_id", "display_name", "language"]
    for field in required_fields:
        if field not in voice:
            return {"error": f"Missing required field: {field}"}
    
    # Add provider field
    voice["provider"] = provider
    
    # Set base_language based on language
    if voice.get("language") == "zh":
        voice["base_language"] = "Chinese"
    elif voice.get("language") == "en":
        voice["base_language"] = "English"
    
    # Load existing voices
    catalog_path = Path(__file__).parent.parent / "catalog" / f"voices_{provider}.json"
    
    existing_voices = []
    if catalog_path.exists():
        try:
            with open(catalog_path, encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    existing_voices = data
                elif isinstance(data, dict) and "voices" in data:
                    existing_voices = data["voices"]
        except Exception as e:
            return {"error": f"Failed to load existing voices: {str(e)}"}
    
    # Check if voice already exists
    for existing_voice in existing_voices:
        if existing_voice.get("voice_id") == voice["voice_id"]:
            return {"error": f"Voice with ID {voice['voice_id']} already exists"}
    
    # Add new voice
    existing_voices.append(voice)
    
    # Save back to file
    try:
        # Create directory if it doesn't exist
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(catalog_path, 'w', encoding='utf-8') as f:
            json.dump(existing_voices, f, ensure_ascii=False, indent=2)
        
        # Clear provider cache
        if provider == "elevenlabs":
            from tts_providers import ElevenLabsProvider
            provider_instance = ElevenLabsProvider()
            provider_instance._voices_cache = None
        elif provider == "iflytek":
            from tts_providers import iFlytekProvider
            provider_instance = iFlytekProvider()
            provider_instance.clear_cache()
        elif provider == "baidu":
            from tts_providers import BaiduProvider
            provider_instance = BaiduProvider()
            provider_instance.clear_cache()
        elif provider == "edge":
            from tts_providers import EdgeTTSProvider
            provider_instance = EdgeTTSProvider()
            provider_instance._voices_cache = None
        
        return {"success": True, "voice": voice}
    except Exception as e:
        return {"error": f"Failed to save voice: {str(e)}"}


@app.delete("/api/voices/{provider}/custom/{voice_id}")
async def delete_custom_voice(provider: str, voice_id: str):
    """Delete a custom voice for a specific provider."""
    from pathlib import Path
    import json
    
    # Validate provider
    valid_providers = ["elevenlabs", "iflytek", "baidu", "edge"]
    if provider not in valid_providers:
        return {"error": f"Invalid provider. Valid providers: {valid_providers}"}
    
    # Load existing voices
    catalog_path = Path(__file__).parent.parent / "catalog" / f"voices_{provider}.json"
    
    if not catalog_path.exists():
        return {"error": "No custom voices found"}
    
    try:
        with open(catalog_path, encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                existing_voices = data
            elif isinstance(data, dict) and "voices" in data:
                existing_voices = data["voices"]
            else:
                return {"error": "Invalid catalog format"}
    except Exception as e:
        return {"error": f"Failed to load existing voices: {str(e)}"}
    
    # Find and remove voice
    voice_found = False
    updated_voices = []
    for voice in existing_voices:
        if voice.get("voice_id") != voice_id:
            updated_voices.append(voice)
        else:
            voice_found = True
    
    if not voice_found:
        return {"error": f"Voice with ID {voice_id} not found"}
    
    # Save back to file
    try:
        with open(catalog_path, 'w', encoding='utf-8') as f:
            json.dump(updated_voices, f, ensure_ascii=False, indent=2)
        
        # Clear provider cache
        if provider == "elevenlabs":
            from tts_providers import ElevenLabsProvider
            provider_instance = ElevenLabsProvider()
            provider_instance._voices_cache = None
        elif provider == "iflytek":
            from tts_providers import iFlytekProvider
            provider_instance = iFlytekProvider()
            provider_instance.clear_cache()
        elif provider == "baidu":
            from tts_providers import BaiduProvider
            provider_instance = BaiduProvider()
            provider_instance.clear_cache()
        elif provider == "edge":
            from tts_providers import EdgeTTSProvider
            provider_instance = EdgeTTSProvider()
            provider_instance._voices_cache = None
        
        return {"success": True}
    except Exception as e:
        return {"error": f"Failed to save voices: {str(e)}"}


@app.put("/api/voices/{provider}/custom")
async def reorder_custom_voices(provider: str, voices: list[dict]):
    """Reorder custom voices for a specific provider."""
    from pathlib import Path
    import json
    
    # Validate provider
    valid_providers = ["elevenlabs", "iflytek", "baidu", "edge"]
    if provider not in valid_providers:
        return {"error": f"Invalid provider. Valid providers: {valid_providers}"}
    
    # Validate voices
    if not isinstance(voices, list):
        return {"error": "Voices must be a list"}
    
    # Save voices to file
    catalog_path = Path(__file__).parent.parent / "catalog" / f"voices_{provider}.json"
    
    try:
        # Create directory if it doesn't exist
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(catalog_path, 'w', encoding='utf-8') as f:
            json.dump(voices, f, ensure_ascii=False, indent=2)
        
        # Clear provider cache
        if provider == "elevenlabs":
            from tts_providers import ElevenLabsProvider
            provider_instance = ElevenLabsProvider()
            provider_instance._voices_cache = None
        elif provider == "iflytek":
            from tts_providers import iFlytekProvider
            provider_instance = iFlytekProvider()
            provider_instance.clear_cache()
        elif provider == "baidu":
            from tts_providers import BaiduProvider
            provider_instance = BaiduProvider()
            provider_instance.clear_cache()
        elif provider == "edge":
            from tts_providers import EdgeTTSProvider
            provider_instance = EdgeTTSProvider()
            provider_instance._voices_cache = None
        
        return {"success": True}
    except Exception as e:
        return {"error": f"Failed to save voices: {str(e)}"}


if __name__ == "__main__":
    import uvicorn
    # Configure uvicorn to log to file only, no console output
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_config=None,  # Disable default logging config
        access_log=False  # Disable access log
    )
