#!/usr/bin/env python3
"""
build_catalog.py - Generates enriched voice catalog files from edge_voices_raw.json.
Focused on English and Chinese voices first, with full metadata enrichment.
"""
import json
import re
from pathlib import Path

RAW_FILE = "/home/user/workspace/edge_voices_raw.json"
OUT_DIR = Path("/home/user/workspace/scripts-to-audiobook-app/catalog")

# ─── Knowledge base for voice enrichment ─────────────────────────────────────

LOCALE_META = {
    # English
    "en-US": {"language": "English", "accent": "American", "region": "United States"},
    "en-GB": {"language": "English", "accent": "British", "region": "United Kingdom"},
    "en-AU": {"language": "English", "accent": "Australian", "region": "Australia"},
    "en-CA": {"language": "English", "accent": "Canadian", "region": "Canada"},
    "en-IE": {"language": "English", "accent": "Irish", "region": "Ireland"},
    "en-IN": {"language": "English", "accent": "Indian", "region": "India"},
    "en-NZ": {"language": "English", "accent": "New Zealand", "region": "New Zealand"},
    "en-SG": {"language": "English", "accent": "Singaporean", "region": "Singapore"},
    "en-ZA": {"language": "English", "accent": "South African", "region": "South Africa"},
    "en-HK": {"language": "English", "accent": "Hong Kong", "region": "Hong Kong"},
    "en-KE": {"language": "English", "accent": "Kenyan", "region": "Kenya"},
    "en-NG": {"language": "English", "accent": "Nigerian", "region": "Nigeria"},
    "en-PH": {"language": "English", "accent": "Filipino", "region": "Philippines"},
    "en-TZ": {"language": "English", "accent": "Tanzanian", "region": "Tanzania"},
    # Chinese
    "zh-CN": {"language": "Chinese", "accent": "Mainland Mandarin", "region": "China"},
    "zh-CN-liaoning": {"language": "Chinese", "accent": "Northeastern Dialect", "region": "Liaoning, China"},
    "zh-CN-shaanxi": {"language": "Chinese", "accent": "Shaanxi Dialect", "region": "Shaanxi, China"},
    "zh-HK": {"language": "Chinese", "accent": "Cantonese", "region": "Hong Kong"},
    "zh-TW": {"language": "Chinese", "accent": "Taiwan Mandarin", "region": "Taiwan"},
}

# Voice name → age bucket, based on name patterns and known Microsoft voice names
NAME_AGE_HINTS = {
    # Explicitly child/young voices
    "Ana": ("child", 0.9),
    "Aria": ("adult", 0.8),
    "Guy": ("adult", 0.8),
    "Jenny": ("adult", 0.85),
    "JennyMultilingual": ("adult", 0.85),
    "Tony": ("adult", 0.75),
    "Emma": ("adult", 0.8),
    "Eric": ("adult", 0.75),
    "Michelle": ("adult", 0.8),
    "Roger": ("adult", 0.7),
    "Steffan": ("adult", 0.7),
    "Davis": ("adult", 0.7),
    "Andrew": ("adult", 0.75),
    "Brian": ("adult", 0.75),
    "Ava": ("adult", 0.8),
    "Emma": ("adult", 0.8),
    "AlloyTurbo": ("adult", 0.8),
    # Generic
}

NARRATOR_VOICES = {
    "en-US": ["en-US-GuyNeural", "en-US-SteffanNeural", "en-US-BrianNeural", "en-US-AriaNeural", "en-US-JennyNeural"],
    "zh-CN": ["zh-CN-YunxiNeural", "zh-CN-XiaoxiaoNeural", "zh-CN-YunjianNeural"],
    "en-GB": ["en-GB-RyanNeural", "en-GB-LibbyNeural"],
    "en-AU": ["en-AU-WilliamMultilingualNeural"],
}

DIALOGUE_VOICES = {
    "en-US": ["en-US-TonyNeural", "en-US-JennyNeural", "en-US-AndrewNeural", "en-US-EmmaNeural"],
    "zh-CN": ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"],
}

# Personality → tags mapping
PERSONALITY_TAGS = {
    "Friendly": ["warm", "approachable", "conversational"],
    "Positive": ["upbeat", "encouraging"],
    "Cheerful": ["happy", "bright", "child-friendly"],
    "Sad": ["emotional", "dramatic"],
    "Angry": ["intense", "dramatic"],
    "Fear": ["tense", "dramatic"],
    "Newscast": ["authoritative", "news", "professional", "narrator"],
    "Newscast-casual": ["conversational", "news", "professional"],
    "Newscast-formal": ["formal", "news", "authoritative", "narrator"],
    "CustomerService": ["helpful", "professional", "clear"],
    "Calm": ["relaxed", "narrator", "meditation"],
    "Lyrical": ["poetic", "expressive", "storytelling", "narrator"],
    "Narration-professional": ["professional", "narrator", "audiobook"],
    "Narration-relaxed": ["relaxed", "narrator", "storytelling"],
    "Assistant": ["helpful", "professional"],
    "Chat": ["casual", "conversational"],
    "Empathetic": ["warm", "supportive"],
    "Excited": ["energetic", "enthusiastic"],
    "Hopeful": ["optimistic", "warm"],
    "Shouting": ["loud", "dramatic"],
    "Whispering": ["soft", "intimate"],
    "Terrified": ["scared", "dramatic"],
    "Unfriendly": ["cold", "stern"],
    "General": ["versatile", "general-purpose"],
}

def extract_voice_name(short_name):
    """Extract just the voice name from ShortName like 'en-US-GuyNeural'"""
    parts = short_name.split("-")
    if len(parts) >= 3:
        name_part = "-".join(parts[2:])
        # Remove 'Neural' suffix
        name_part = name_part.replace("Neural", "")
        return name_part
    return short_name

def infer_age_bucket(short_name, voice_name, personalities, content_categories):
    """Infer age bucket from voice name and metadata."""
    vn_lower = voice_name.lower()
    personalities_lower = [p.lower() for p in personalities]
    categories_lower = [c.lower() for c in content_categories]
    
    # Child indicators
    child_keywords = ["kid", "child", "boy", "girl", "junior", "young", "teen"]
    for kw in child_keywords:
        if kw in vn_lower:
            return "child", 0.9, True
    
    if "cheerful" in personalities_lower and any(c in categories_lower for c in ["cartoon", "children"]):
        return "child", 0.7, True
    
    # Senior/elderly indicators
    senior_keywords = ["elder", "senior", "old", "mature", "wise", "grand"]
    for kw in senior_keywords:
        if kw in vn_lower:
            return "senior", 0.85, False
    
    # Multilingual voices tend to be more mature/adult
    if "multilingual" in vn_lower:
        return "adult", 0.85, False
    
    # Check hint table
    for name_hint, (age, conf) in NAME_AGE_HINTS.items():
        if name_hint.lower() == vn_lower:
            return age, conf, age == "child"
    
    # Default to adult with moderate confidence
    return "adult", 0.6, False

def calc_narrator_score(short_name, personalities, content_categories):
    """Score how suitable a voice is for narrator role (0-1)."""
    score = 0.4  # base
    narrator_keywords = ["narration", "newscast", "lyrical", "calm", "professional"]
    for p in [x.lower() for x in personalities]:
        if any(kw in p for kw in narrator_keywords):
            score += 0.2
    # Known narrator voices boost
    for locale_voices in NARRATOR_VOICES.values():
        if short_name in locale_voices:
            score += 0.25
    return min(1.0, round(score, 2))

def calc_dialogue_score(short_name, personalities, content_categories):
    """Score how suitable a voice is for dialogue."""
    score = 0.5  # base
    dialogue_keywords = ["chat", "conversational", "friendly", "assistant", "customerservice"]
    for p in [x.lower() for x in personalities]:
        if any(kw in p for kw in dialogue_keywords):
            score += 0.15
    for locale_voices in DIALOGUE_VOICES.values():
        if short_name in locale_voices:
            score += 0.2
    return min(1.0, round(score, 2))

def get_recommended_tags(voice_name, personalities, content_categories, gender, age_bucket, locale):
    """Generate recommended use-case tags for a voice."""
    tags = []
    pl = [p.lower() for p in personalities]
    cl = [c.lower() for c in content_categories]
    
    if age_bucket == "child":
        tags.extend(["children", "kids-content"])
    if any(x in pl for x in ["newscast", "narration", "lyrical"]):
        tags.extend(["narrator", "audiobook"])
    if any(x in pl for x in ["chat", "conversational", "friendly"]):
        tags.extend(["dialogue", "character"])
    if "professional" in pl or "customerservice" in pl:
        tags.extend(["professional", "corporate"])
    if "general" in cl:
        tags.append("versatile")
    if locale.startswith("zh-"):
        tags.append("chinese")
    elif locale.startswith("en-"):
        tags.append("english")
    
    if gender == "Female":
        tags.append("female")
    else:
        tags.append("male")
    
    return list(set(tags))

def build_enriched_voice(raw_voice):
    """Enrich a single raw voice entry with computed metadata."""
    short_name = raw_voice["ShortName"]
    locale = raw_voice["Locale"]
    gender = raw_voice["Gender"]
    friendly_name = raw_voice["FriendlyName"]
    voice_tag = raw_voice.get("VoiceTag", {})
    personalities = voice_tag.get("VoicePersonalities", [])
    content_categories = voice_tag.get("ContentCategories", [])
    
    locale_info = LOCALE_META.get(locale, {
        "language": locale.split("-")[0].upper(),
        "accent": locale,
        "region": locale,
    })
    
    voice_name = extract_voice_name(short_name)
    age_bucket, age_confidence, child_like = infer_age_bucket(short_name, voice_name, personalities, content_categories)
    narrator_score = calc_narrator_score(short_name, personalities, content_categories)
    dialogue_score = calc_dialogue_score(short_name, personalities, content_categories)
    recommended_tags = get_recommended_tags(voice_name, personalities, content_categories, gender, age_bucket, locale)
    
    all_personality_tags = []
    for p in personalities:
        all_personality_tags.extend(PERSONALITY_TAGS.get(p, [p.lower()]))
    
    # Extract display name (person name only)
    display_name = voice_name
    
    return {
        "voice_id": short_name,
        "short_name": short_name,
        "display_name": display_name,
        "full_name": friendly_name,
        "locale": locale,
        "base_language": locale_info["language"],
        "accent_label": locale_info["accent"],
        "region": locale_info["region"],
        "gender": gender,
        "age_bucket": age_bucket,
        "age_confidence": age_confidence,
        "child_like": child_like,
        "content_categories": content_categories,
        "personalities": personalities,
        "personality_tags": list(set(all_personality_tags)),
        "narrator_fit_score": narrator_score,
        "dialogue_fit_score": dialogue_score,
        "recommended_tags": recommended_tags,
        "suggested_codec": raw_voice.get("SuggestedCodec", "audio-24khz-48kbitrate-mono-mp3"),
        "status": raw_voice.get("Status", "GA"),
    }

def main():
    with open(RAW_FILE) as f:
        raw_voices = json.load(f)
    
    all_enriched = [build_enriched_voice(v) for v in raw_voices]
    
    # Full catalog
    out_all = OUT_DIR / "voices_all.json"
    with open(out_all, "w", encoding="utf-8") as f:
        json.dump(all_enriched, f, indent=2, ensure_ascii=False)
    print(f"Full catalog: {len(all_enriched)} voices → {out_all}")
    
    # English-only catalog
    en_voices = [v for v in all_enriched if v["base_language"] == "English"]
    out_en = OUT_DIR / "voices_english.json"
    with open(out_en, "w", encoding="utf-8") as f:
        json.dump(en_voices, f, indent=2, ensure_ascii=False)
    print(f"English catalog: {len(en_voices)} voices → {out_en}")
    
    # Chinese-only catalog
    zh_voices = [v for v in all_enriched if v["base_language"] == "Chinese"]
    out_zh = OUT_DIR / "voices_chinese.json"
    with open(out_zh, "w", encoding="utf-8") as f:
        json.dump(zh_voices, f, indent=2, ensure_ascii=False)
    print(f"Chinese catalog: {len(zh_voices)} voices → {out_zh}")
    
    # Priority catalog (EN + ZH only)
    priority_voices = en_voices + zh_voices
    out_priority = OUT_DIR / "voices_priority.json"
    with open(out_priority, "w", encoding="utf-8") as f:
        json.dump(priority_voices, f, indent=2, ensure_ascii=False)
    print(f"Priority catalog (EN+ZH): {len(priority_voices)} voices → {out_priority}")
    
    # Stats summary
    stats = {
        "total": len(all_enriched),
        "english": len(en_voices),
        "chinese": len(zh_voices),
        "by_gender": {
            "Female": sum(1 for v in all_enriched if v["gender"] == "Female"),
            "Male": sum(1 for v in all_enriched if v["gender"] == "Male"),
        },
        "by_age_bucket": {
            "child": sum(1 for v in all_enriched if v["age_bucket"] == "child"),
            "adult": sum(1 for v in all_enriched if v["age_bucket"] == "adult"),
            "senior": sum(1 for v in all_enriched if v["age_bucket"] == "senior"),
        },
        "en_locales": sorted(set(v["locale"] for v in en_voices)),
        "zh_locales": sorted(set(v["locale"] for v in zh_voices)),
    }
    out_stats = OUT_DIR / "catalog_stats.json"
    with open(out_stats, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"Stats → {out_stats}")
    print(json.dumps(stats, indent=2))

if __name__ == "__main__":
    main()
