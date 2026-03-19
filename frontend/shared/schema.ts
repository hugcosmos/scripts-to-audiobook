import { pgTable, text, integer, real, boolean, jsonb } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

// Shared types for the Scripts to Audiobook app
// The app is mostly frontend-driven; schema is used for type sharing only.

export interface VoiceData {
  voice_id: string;
  short_name: string;
  display_name: string;
  full_name: string;
  locale: string;
  base_language: string;
  accent_label: string;
  region: string;
  gender: string;
  age_bucket: string;
  age_confidence: number;
  child_like: boolean;
  content_categories: string[];
  personalities: string[];
  personality_tags: string[];
  narrator_fit_score: number;
  dialogue_fit_score: number;
  recommended_tags: string[];
  suggested_codec: string;
  status: string;
  provider?: string;  // TTS provider: edge, elevenlabs, iflytek, baidu
}

export interface CharacterData {
  name: string;
  role_type: "narrator" | "character";
  color: string;
  language: string;
  locale_hint: string | null;
  gender: string | null;
  age_bucket: string;
  line_count: number;
  assigned_voice: string;
  voice_data: VoiceData;
  match_score: number;
  match_reasons: string[];
  voice_alternatives: Array<{voice: VoiceData; score: number; reasons: string[]}>;
  // editable overrides
  rate: string;
  pitch: string;
  volume: string;
  locked: boolean;
}

export interface ScriptLine {
  character: string;
  text: string;
  line_index: number;
}

export interface TimelineSegment {
  line_index: number;
  character: string;
  text: string;
  voice_id: string;
  audio_file: string;
  start_ms: number;
  end_ms: number;
  duration_ms: number;
  word_boundaries: Array<{text: string; offset: number; duration: number}>;
}

export interface TimelineData {
  project_id: string;
  total_duration_ms: number;
  segments: TimelineSegment[];
  generated_at: number;
}

export interface GenerationJob {
  job_id: string;
  status: "queued" | "processing" | "merging" | "done" | "error";
  progress: number;
  project_id: string;
  result?: {
    project_id: string;
    audio_url: string;
    timeline_url: string;
    srt_url: string;
    total_duration_ms: number;
    segment_count: number;
  };
  error?: string;
}
