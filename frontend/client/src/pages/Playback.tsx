import { useLocation } from "wouter";
import { useState, useEffect, useRef, useCallback } from "react";

import { useApp } from "@/App";
import { t } from "@/lib/i18n";
import { Play, Pause, SkipBack, SkipForward, Volume2, Users, AlignLeft, ArrowLeft, Gauge } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { API_BASE } from "@/lib/api";
import type { TimelineSegment } from "../../../shared/schema";

function formatTime(ms: number) {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

export default function PlaybackPage() {
  const [, navigate] = useLocation();
  const { lang, timeline, audioUrl, characters, projectId, generationResult } = useApp();
  const audioRef = useRef<HTMLAudioElement>(null);
  
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(80);
  const [activeSegmentIdx, setActiveSegmentIdx] = useState(-1);
  const [filterChar, setFilterChar] = useState<string | null>(null);
  const [syncScroll, setSyncScroll] = useState(true);
  const [viewMode, setViewMode] = useState<"full" | "cast">("full");
  const [playbackRate, setPlaybackRate] = useState(1);
  
  const transcriptRef = useRef<HTMLDivElement>(null);
  const activeLinesRef = useRef<Map<number, HTMLElement>>(new Map());

  const segments = timeline?.segments || [];
  const totalDuration = timeline?.total_duration_ms || 0;
  
  // Real audio URL
  const realAudioUrl = generationResult?.audio_url ? `${API_BASE}${generationResult.audio_url}` : (audioUrl || (projectId ? `${API_BASE}/api/audio/${projectId}/audiobook.mp3` : ""));

  // Reload audio when src changes (handles navigation from library)
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !realAudioUrl) return;
    
    // Only reload if src actually changed
    if (audio.src !== realAudioUrl) {
      audio.src = realAudioUrl;
      audio.load();
      // Reset state
      setCurrentTime(0);
      setPlaying(false);
      setDuration(0);
      setActiveSegmentIdx(-1);
    }
  }, [realAudioUrl]);

  // Find active segment based on current time
  useEffect(() => {
    if (!segments.length) return;
    const currentMs = currentTime * 1000;
    let idx = -1;
    for (let i = 0; i < segments.length; i++) {
      if (currentMs >= segments[i].start_ms && currentMs < segments[i].end_ms) {
        idx = i;
        break;
      }
    }
    if (idx !== activeSegmentIdx) {
      setActiveSegmentIdx(idx);
      // Auto-scroll to active line
      if (syncScroll && idx >= 0) {
        const el = activeLinesRef.current.get(idx);
        el?.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [currentTime, segments, syncScroll]);

  // Audio event handlers - re-bind when audio source changes
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
    };
    const onLoadedMeta = () => {
      setDuration(audio.duration);
    };
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onEnded = () => { 
      setPlaying(false); 
      setCurrentTime(0); 
    };
    const onCanPlay = () => {
      // Ensure duration is set when audio is ready
      if (audio.duration && isFinite(audio.duration)) {
        setDuration(audio.duration);
      }
      // Apply any pending seek now that audio is ready
      if (pendingSeekRef.current !== null) {
        try {
          audio.currentTime = pendingSeekRef.current;
          pendingSeekRef.current = null;
        } catch (e) {
          // Silent fail for pending seek
        }
      }
    };

    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("loadedmetadata", onLoadedMeta);
    audio.addEventListener("canplay", onCanPlay);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onEnded);
    audio.volume = volume / 100;

    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("loadedmetadata", onLoadedMeta);
      audio.removeEventListener("canplay", onCanPlay);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onEnded);
    };
  }, [realAudioUrl]); // Re-bind when URL changes

  useEffect(() => {
    if (audioRef.current) audioRef.current.volume = volume / 100;
  }, [volume]);

  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = playbackRate;
  }, [playbackRate]);

  function togglePlay() {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) audio.pause();
    else audio.play().catch(() => {});
  }

  // Store pending seek when audio isn't ready
  const pendingSeekRef = useRef<number | null>(null);
  
  function seekToTime(newTime: number) {
    const audio = audioRef.current;
    if (!audio || !isFinite(newTime)) return;
    
    // Clamp time to valid range
    const maxTime = duration || audio.duration || 0;
    const clampedTime = Math.max(0, Math.min(newTime, maxTime));
    
    // Always update UI immediately for responsiveness
    setCurrentTime(clampedTime);
    
    // If audio is ready, seek immediately
    if (audio.readyState >= 2) {
      try {
        audio.currentTime = clampedTime;
        pendingSeekRef.current = null;
      } catch (e) {
        pendingSeekRef.current = clampedTime;
      }
    } else {
      // Store for later when audio is ready
      pendingSeekRef.current = clampedTime;
      // Try to load the audio if not already loading
      if (audio.readyState < 2) {
        audio.load();
      }
    }
  }
  
  // Apply pending seek when audio becomes ready
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || pendingSeekRef.current === null) return;
    
    if (audio.readyState >= 2) {
      try {
        audio.currentTime = pendingSeekRef.current;
        pendingSeekRef.current = null;
      } catch (e) {
        // Silent fail
      }
    }
  }, [duration]); // Run when duration becomes available

  function seekToSegment(seg: TimelineSegment) {
    const audio = audioRef.current;
    if (!audio || !seg) return;
    const targetTime = seg.start_ms / 1000;
    if (!isFinite(targetTime)) return;
    audio.currentTime = targetTime;
    setCurrentTime(targetTime);
    // Auto-play when clicking a segment
    if (audio.paused) {
      audio.play().catch(() => {});
    }
  }

  const filteredSegments = filterChar
    ? segments.filter(s => s.character === filterChar)
    : segments;

  const charMap = Object.fromEntries(characters.map(c => [c.name, c]));

  if (!audioUrl && !realAudioUrl) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-muted-foreground">No audiobook generated yet.</p>
          <Button variant="outline" onClick={() => navigate("/generate")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Go to Generate
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <audio ref={audioRef} preload="metadata" />
      
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-border bg-card shrink-0">
        <h1 className="text-sm font-semibold text-foreground">{t("play.title", lang)}</h1>
        <div className="flex items-center gap-2">
          <Button
            variant={viewMode === "full" ? "secondary" : "ghost"}
            size="sm"
            className="text-xs h-7"
            onClick={() => setViewMode("full")}
          >
            {t("play.mode_full", lang)}
          </Button>
          <Button
            variant={viewMode === "cast" ? "secondary" : "ghost"}
            size="sm"
            className="text-xs h-7"
            onClick={() => setViewMode("cast")}
          >
            {t("play.mode_cast", lang)}
          </Button>
          <Button
            variant={syncScroll ? "secondary" : "ghost"}
            size="sm"
            className="text-xs h-7"
            onClick={() => setSyncScroll(!syncScroll)}
            data-testid="sync-toggle"
          >
            {t("play.sync", lang)}
          </Button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Cast sidebar */}
        <div className="w-48 shrink-0 border-r border-border bg-sidebar p-3 overflow-y-auto hidden lg:block">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">{t("play.cast", lang)}</p>
          <div className="space-y-1">
            <button
              className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs text-left transition-colors ${!filterChar ? "bg-accent text-accent-foreground" : "hover:bg-accent/60"}`}
              onClick={() => setFilterChar(null)}
            >
              <AlignLeft className="w-3 h-3 shrink-0" />
              {t("play.filter_all", lang)}
            </button>
            {characters.map(c => (
              <button
                key={c.name}
                data-testid={`filter-${c.name}`}
                className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs text-left transition-colors ${filterChar === c.name ? "bg-accent text-accent-foreground" : "hover:bg-accent/60"}`}
                onClick={() => setFilterChar(filterChar === c.name ? null : c.name)}
                style={{ borderLeft: `2px solid ${filterChar === c.name ? c.color : "transparent"}` }}
              >
                <div className="w-2 h-2 rounded-full shrink-0" style={{ background: c.color }} />
                <span className="truncate">{c.name}</span>
              </button>
            ))}
          </div>
          
          {/* Timeline marker strip */}
          {totalDuration > 0 && (
            <div className="mt-4">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Timeline</p>
              <div className="relative h-24 bg-muted rounded overflow-hidden">
                {segments.map((seg, i) => {
                  const char = charMap[seg.character];
                  const left = (seg.start_ms / totalDuration) * 100;
                  const width = (seg.duration_ms / totalDuration) * 100;
                  return (
                    <div
                      key={i}
                      className="absolute top-0 bottom-0 cursor-pointer hover:opacity-80 transition-opacity"
                      style={{
                        left: `${left}%`,
                        width: `${Math.max(width, 0.5)}%`,
                        background: char?.color || "#888",
                        opacity: i === activeSegmentIdx ? 1 : 0.5,
                      }}
                      onClick={() => seekToSegment(seg)}
                      title={`${seg.character}: ${seg.text.substring(0, 40)}`}
                    />
                  );
                })}
                {/* Playhead */}
                {duration > 0 && (
                  <div
                    className="absolute top-0 bottom-0 w-0.5 bg-white z-10 pointer-events-none"
                    style={{ left: `${(currentTime / duration) * 100}%` }}
                  />
                )}
              </div>
            </div>
          )}
        </div>

        {/* Transcript */}
        <div ref={transcriptRef} className="flex-1 overflow-y-auto p-4 space-y-1">
          {filteredSegments.map((seg, i) => {
            const char = charMap[seg.character];
            const isActive = segments.indexOf(seg) === activeSegmentIdx;
            const hasError = (seg as any).error;
            
            return (
              <div
                key={seg.line_index}
                ref={el => { if (el) activeLinesRef.current.set(segments.indexOf(seg), el); }}
                data-testid={`line-${seg.line_index}`}
                className={`flex gap-3 px-3 py-2 rounded cursor-pointer transition-all ${isActive ? "line-active" : "line-inactive hover:bg-muted/30"} ${hasError ? "border border-destructive/30 bg-destructive/5" : ""}`}
                style={isActive ? { borderLeftColor: char?.color } : {}}
                onClick={() => seekToSegment(seg)}
              >
                <div
                  className="shrink-0 text-xs font-semibold px-1.5 py-0.5 rounded h-fit mt-0.5 text-white"
                  style={{ background: char?.color || "#888" }}
                >
                  {seg.character.charAt(0)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span
                      className="text-xs font-semibold"
                      style={{ color: char?.color || "inherit" }}
                    >
                      {seg.character}
                    </span>
                    <span className="text-[10px] text-muted-foreground">{formatTime(seg.start_ms)}</span>
                    {hasError && (
                      <span className="text-[10px] text-destructive font-medium">
                        ❌ Generation failed
                      </span>
                    )}
                  </div>
                  <p className={`text-sm mt-0.5 leading-relaxed ${isActive ? "text-foreground font-medium" : "text-muted-foreground"}`}>
                    {seg.text}
                  </p>
                  {hasError && (
                    <p className="text-xs text-destructive mt-1">
                      Error: {(seg as any).error}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Player controls */}
      <div className="border-t border-border bg-card px-6 py-4 shrink-0">
        {/* Progress bar */}
        <div className="flex items-center gap-3 mb-3">
          <span className="text-xs text-muted-foreground tabular-nums w-10 shrink-0">{formatTime(currentTime * 1000)}</span>
          <input
            type="range"
            min={0}
            max={duration || 1}
            step={0.1}
            value={currentTime}
            onChange={(e) => {
              // Jump to selected time when user releases
              const newTime = parseFloat(e.target.value);
              seekToTime(newTime);
            }}
            className="flex-1 h-1.5 bg-muted rounded-full appearance-none cursor-pointer accent-primary"
            style={{
              background: `linear-gradient(to right, hsl(var(--primary)) 0%, hsl(var(--primary)) ${(currentTime / (duration || 1)) * 100}%, hsl(var(--muted)) ${(currentTime / (duration || 1)) * 100}%, hsl(var(--muted)) 100%)`
            }}
          />
          <span className="text-xs text-muted-foreground tabular-nums w-10 shrink-0 text-right">{formatTime((duration || 0) * 1000)}</span>
        </div>
        
        {/* Controls row */}
        <div className="flex items-center justify-between">
          {/* Active character display */}
          <div className="w-32 shrink-0">
            {activeSegmentIdx >= 0 && segments[activeSegmentIdx] && (
              <div className="flex items-center gap-1.5">
                <div
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ background: charMap[segments[activeSegmentIdx].character]?.color || "#888" }}
                />
                <span className="text-xs text-muted-foreground truncate">
                  {segments[activeSegmentIdx].character}
                </span>
              </div>
            )}
          </div>

          {/* Main controls */}
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" className="w-8 h-8" onClick={() => seekToTime(Math.max(0, currentTime - 10))}>
              <SkipBack className="w-4 h-4" />
            </Button>
            <Button
              data-testid="play-pause-btn"
              size="icon"
              className="w-10 h-10"
              onClick={togglePlay}
            >
              {playing ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
            </Button>
            <Button variant="ghost" size="icon" className="w-8 h-8" onClick={() => seekToTime(Math.min(duration, currentTime + 10))}>
              <SkipForward className="w-4 h-4" />
            </Button>
          </div>

          {/* Playback speed */}
          <div className="flex items-center gap-2 w-24">
            <Gauge className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
            <Select value={playbackRate.toString()} onValueChange={(v) => setPlaybackRate(parseFloat(v))}>
              <SelectTrigger className="h-7 text-xs w-16">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="0.5" className="text-xs">0.5x</SelectItem>
                <SelectItem value="0.75" className="text-xs">0.75x</SelectItem>
                <SelectItem value="1" className="text-xs">1x</SelectItem>
                <SelectItem value="1.25" className="text-xs">1.25x</SelectItem>
                <SelectItem value="1.5" className="text-xs">1.5x</SelectItem>
                <SelectItem value="2" className="text-xs">2x</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Volume */}
          <div className="flex items-center gap-2 w-32">
            <Volume2 className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
            <input
              type="range"
              min={0} 
              max={100} 
              step={1}
              value={volume}
              onChange={(e) => setVolume(parseInt(e.target.value))}
              className="w-20 h-1.5 bg-muted rounded-full appearance-none cursor-pointer"
              style={{
                background: `linear-gradient(to right, hsl(var(--primary)) 0%, hsl(var(--primary)) ${volume}%, hsl(var(--muted)) ${volume}%, hsl(var(--muted)) 100%)`
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
