import { useLocation } from "wouter";
import { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useApp } from "@/App";
import { t } from "@/lib/i18n";
import { startGeneration, getJobStatus, fetchTimeline, getAudioUrl, fetchAlbums } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { ArrowLeft, Play, Download, CheckCircle, AlertCircle, Loader2, Wand2, FileAudio, FileText, Library, Users, Plus, RotateCcw } from "lucide-react";
import { API_BASE } from "@/lib/api";
import type { GenerationJob } from "../../../shared/schema";
import { createAlbum } from "@/lib/api";

function formatDuration(ms: number) {
  const totalSec = Math.round(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return min > 0 ? `${min}m ${sec}s` : `${sec}s`;
}

export default function GeneratePage() {
  const [, navigate] = useLocation();
  const { lang, characters, scriptLines, projectId, scriptText, setTimeline, setAudioUrl, generationResult, setGenerationResult } = useApp();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [polling, setPolling] = useState(false);
  const [starting, setStarting] = useState(false);
  const [selectedAlbumId, setSelectedAlbumId] = useState<string>("__none__");
  const [albums, setAlbums] = useState<Array<{id: string; name: string}>>([]);
  const [hasCheckedData, setHasCheckedData] = useState(false);
  
  // Create album dialog state
  const [isCreateAlbumOpen, setIsCreateAlbumOpen] = useState(false);
  const [newAlbumName, setNewAlbumName] = useState("");
  const [isCreatingAlbum, setIsCreatingAlbum] = useState(false);
  const [audiobookTitle, setAudiobookTitle] = useState("");
  
  // Extract title from script if available
  useEffect(() => {
    if (scriptText) {
      // Try to extract title from first line (not starting with character:)
      const firstLine = scriptText.split('\n')[0]?.trim();
      if (firstLine && !firstLine.includes(':') && !firstLine.includes('：')) {
        setAudiobookTitle(firstLine.substring(0, 100));
      } else {
        // Default title
        setAudiobookTitle(`Audiobook ${projectId?.slice(0, 8) || 'unknown'}`);
      }
    }
  }, [scriptText, projectId]);
  
  // Reset generation result when component mounts (for re-generation)
  useEffect(() => {
    if (generationResult) {
      setGenerationResult(null);
    }
  }, []);

  // Load albums for selection
  const loadAlbums = () => {
    fetchAlbums().then((data) => {
      setAlbums(data.albums || []);
    }).catch(() => {
      setAlbums([]);
    });
  };
  
  useEffect(() => {
    loadAlbums();
  }, []);
  
  const handleCreateAlbum = async () => {
    if (!newAlbumName.trim()) return;
    setIsCreatingAlbum(true);
    try {
      const album = await createAlbum(newAlbumName.trim());
      setIsCreateAlbumOpen(false);
      setNewAlbumName("");
      // Refresh albums list in this component
      await loadAlbums();
      // Invalidate Library page cache so it shows the new album
      queryClient.invalidateQueries({ queryKey: ["/api/library/albums"] });
      setSelectedAlbumId(album.id);
      toast({ title: t("common.success", lang), description: "Album created" });
    } catch (e) {
      toast({ title: t("common.error", lang), description: "Failed to create album", variant: "destructive" });
    } finally {
      setIsCreatingAlbum(false);
    }
  };

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (polling && job && job.status !== "done" && job.status !== "error") {
      interval = setInterval(async () => {
        try {
          const updated = await getJobStatus(job.job_id);
          setJob(updated);
          if (updated.status === "done") {
            setPolling(false);
            // Load timeline and store result in app context
            const tl = await fetchTimeline(projectId);
            setTimeline(tl);
            setAudioUrl(getAudioUrl(projectId));
            setGenerationResult(updated.result);
            // Refresh library data so new audio appears
            queryClient.invalidateQueries({ queryKey: ["/api/library/audio-files"] });
            queryClient.invalidateQueries({ queryKey: ["/api/library/albums"] });
            // Auto-navigate to playback page
            navigate("/playback");
          } else if (updated.status === "error") {
            setPolling(false);
          }
        } catch (e) {
          // Silent fail for poll errors
        }
      }, 1500);
    }
    return () => clearInterval(interval);
  }, [polling, job, projectId, setTimeline, setAudioUrl, setGenerationResult, navigate, queryClient]);

  // Check data availability after initial render with delay for localStorage hydration
  useEffect(() => {
    const timer = setTimeout(() => setHasCheckedData(true), 150);
    return () => clearTimeout(timer);
  }, []);

  // Show loading state while checking
  if (!hasCheckedData) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Check if we have required data
  const hasCharacters = characters && characters.length > 0;
  const hasScriptLines = scriptLines && scriptLines.length > 0;

  if (!hasCharacters || !hasScriptLines) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3">
          <Users className="w-12 h-12 mx-auto text-muted-foreground" />
          <p className="text-muted-foreground">{t("cast.subtitle", lang)}</p>
          <p className="text-sm text-muted-foreground">Please parse a script and configure voice cast first</p>
          <Button variant="outline" onClick={() => navigate("/")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t("common.back", lang)}
          </Button>
        </div>
      </div>
    );
  }

  async function handleGenerate() {
    setStarting(true);
    // Clear previous result to show generate UI
    setGenerationResult(null);
    try {
      const characterVoices = characters.map(c => ({
        character_name: c.name,
        voice_id: c.assigned_voice,
        rate: c.rate || "+0%",
        pitch: c.pitch || "+0Hz",
        volume: c.volume || "+0%",
      }));
      
      const title = audiobookTitle.trim() || `Audiobook ${projectId?.slice(0, 8) || 'unknown'}`;
      const res = await startGeneration(
        projectId, 
        scriptLines, 
        characterVoices, 
        selectedAlbumId === "__none__" ? undefined : selectedAlbumId, 
        title,
        scriptText
      );
      setJob({ job_id: res.job_id, status: "queued", progress: 0, project_id: projectId });
      setPolling(true);
    } catch (e: any) {
      setJob({ job_id: "", status: "error", progress: 0, project_id: projectId, error: e.message });
    } finally {
      setStarting(false);
    }
  }
  
  function handleReset() {
    // Reset to allow generating a new audiobook
    setJob(null);
    setGenerationResult(null);
    setPolling(false);
  }

  const isDone = job?.status === "done" || !!generationResult;
  const isError = job?.status === "error";
  const isRunning = job && !isDone && !isError;
  const activeResult = job?.result || generationResult;

  return (
    <div className="h-full overflow-auto p-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">{t("gen.title", lang)}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t("gen.subtitle", lang)}</p>
      </div>

      {/* Summary card */}
      <div className="rounded-lg border border-border bg-card p-4 mb-6">
        <h3 className="text-sm font-medium text-foreground mb-3">Generation Summary</h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="text-center p-3 rounded-md bg-muted/40">
            <div className="text-2xl font-bold text-primary">{scriptLines.length}</div>
            <div className="text-xs text-muted-foreground mt-0.5">{t("common.lines", lang)}</div>
          </div>
          <div className="text-center p-3 rounded-md bg-muted/40">
            <div className="text-2xl font-bold text-primary">{characters.length}</div>
            <div className="text-xs text-muted-foreground mt-0.5">{t("common.characters", lang)}</div>
          </div>
        </div>
        
        {/* Audiobook Title */}
        <div className="mt-4">
          <label className="text-xs text-muted-foreground mb-1.5 flex items-center gap-1.5">
            <FileAudio className="w-3 h-3" />
            Audiobook Title
          </label>
          <Input
            value={audiobookTitle}
            onChange={(e) => setAudiobookTitle(e.target.value)}
            placeholder="Enter audiobook title"
            className="h-8 text-sm"
            maxLength={100}
          />
          <p className="text-xs text-muted-foreground mt-1">
            {t("gen.title_hint", lang)}
          </p>
        </div>
        
        {/* Album selection */}
        <div className="mt-4">
          <label className="text-xs text-muted-foreground mb-1.5 flex items-center gap-1.5">
            <Library className="w-3 h-3" />
            {t("library.save_to_library", lang)} ({t("library.select_album", lang)})
          </label>
          <Select 
            value={selectedAlbumId} 
            onValueChange={(value) => {
              if (value === "__create__") {
                setIsCreateAlbumOpen(true);
              } else {
                setSelectedAlbumId(value);
              }
            }}
          >
            <SelectTrigger className="h-8 text-xs">
              <SelectValue placeholder={t("library.no_albums", lang) + " - " + t("library.save_to_library", lang)} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">{t("library.no_albums", lang)} (None)</SelectItem>
              {albums.map((album) => (
                <SelectItem key={album.id} value={album.id} className="text-xs">{album.name}</SelectItem>
              ))}
              <div className="border-t border-border my-1" />
              <SelectItem value="__create__" className="text-xs text-primary font-medium">
                <span className="flex items-center gap-1">
                  <Plus className="w-3 h-3" />
                  Create new album...
                </span>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        
        {/* Create Album Dialog */}
        <Dialog open={isCreateAlbumOpen} onOpenChange={setIsCreateAlbumOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Album</DialogTitle>
            </DialogHeader>
            <div className="py-4">
              <label className="text-sm font-medium mb-1.5 block">Album Name</label>
              <Input
                value={newAlbumName}
                onChange={(e) => setNewAlbumName(e.target.value)}
                placeholder="My Audiobook Collection"
                onKeyDown={(e) => e.key === "Enter" && handleCreateAlbum()}
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsCreateAlbumOpen(false)}>Cancel</Button>
              <Button onClick={handleCreateAlbum} disabled={!newAlbumName.trim() || isCreatingAlbum}>
                {isCreatingAlbum ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                Create
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Character voices summary */}
        <div className="mt-3 space-y-1.5">
          {characters.map(c => {
            // Get provider from assigned_voice first (format: provider-voiceId), fallback to voice_data
            let provider;
            if (c.assigned_voice) {
              // Extract provider from voice_id format (e.g., 'iflytek-xiaoxiao', 'elevenlabs-voiceId')
              const parts = c.assigned_voice.split('-');
              if (parts.length > 1) {
                provider = parts[0];
              }
            }
            // Fallback to voice_data provider if extraction fails
            provider = provider || c.voice_data?.provider || "edge";
            
            // Fix: Map language codes like 'en', 'zh' to 'edge' provider
            if (['en', 'zh', 'zh-CN', 'en-US', 'en-GB'].includes(provider)) {
              provider = "edge";
            }
            
            const providerMap: Record<string, {name: string, color: string}> = {
              edge: { name: "Edge", color: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-200" },
              elevenlabs: { name: "ElevenLabs", color: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-200" },
              iflytek: { name: "讯飞", color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200" },
              baidu: { name: "百度", color: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-200" }
            };
            const p = providerMap[provider] || { name: provider, color: "bg-gray-100 text-gray-700" };
            
            return (
              <div key={c.name} className="flex items-center gap-2 text-xs">
                <div className="w-2 h-2 rounded-full shrink-0" style={{ background: c.color }} />
                <span className="font-medium text-foreground truncate">{c.name}</span>
                <span className="text-muted-foreground truncate flex-1">{c.voice_data?.display_name || c.assigned_voice}</span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] ${p.color}`}>{p.name}</span>
                {c.rate !== "+0%" && <Badge variant="outline" className="text-xs h-4 px-1">{c.rate}</Badge>}
              </div>
            );
          })}
        </div>
      </div>

      {/* Progress */}
      {job && (
        <div className="rounded-lg border border-border bg-card p-4 mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-foreground capitalize">
              {job.status === "queued" && "Queued..."}
              {job.status === "processing" && t("gen.generating", lang)}
              {job.status === "merging" && t("gen.merging", lang)}
              {job.status === "done" && t("gen.done", lang)}
              {job.status === "error" && t("gen.error", lang)}
            </span>
            <span className="text-sm text-muted-foreground">{job.progress}%</span>
          </div>
          <Progress value={job.progress} className="h-2" />
          
          {isRunning && (
            <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1.5">
              <Loader2 className="w-3 h-3 animate-spin" />
              {(() => {
                // Get unique providers used by characters
                const providers = new Set(characters.map(c => {
                  // Extract provider from assigned_voice first
                  let provider;
                  if (c.assigned_voice) {
                    const parts = c.assigned_voice.split('-');
                    if (parts.length > 1) {
                      provider = parts[0];
                    }
                  }
                  provider = provider || c.voice_data?.provider || "edge";
                  
                  // Fix: Map language codes like 'en', 'zh' to 'edge' provider
                  if (['en', 'zh', 'zh-CN', 'en-US', 'en-GB'].includes(provider)) {
                    provider = "edge";
                  }
                  
                  return provider;
                }));
                const providerNames: Record<string, string> = {
                  edge: "Edge TTS",
                  elevenlabs: "ElevenLabs",
                  iflytek: "讯飞",
                  baidu: "百度"
                };
                const names = Array.from(providers).map(p => providerNames[p] || p);
                return `Synthesizing ${job.status === "processing" ? "segments" : "final audio"} with ${names.join(", ")}...`;
              })()}
            </p>
          )}
          
          {isError && (
            <div className="mt-2 flex items-center gap-2 text-destructive text-xs">
              <AlertCircle className="w-3.5 h-3.5" />
              {job.error}
            </div>
          )}
        </div>
      )}

      {/* Done state */}
      {isDone && activeResult && (
        <div className="rounded-lg border border-border bg-card p-4 mb-6 space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-foreground">
            <CheckCircle className="w-4 h-4 text-green-500" />
            Audiobook generated successfully!
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            <div>{t("gen.segments", lang)}: <span className="text-foreground font-medium">{activeResult.segment_count}</span></div>
            <div>{t("gen.duration", lang)}: <span className="text-foreground font-medium">{formatDuration(activeResult.total_duration_ms)}</span></div>
          </div>
          <div className="flex gap-2 flex-wrap">
            <a
              href={`${API_BASE}${activeResult.audio_url}`}
              download={activeResult.audio_url.split('/').pop() || "audiobook.mp3"}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <FileAudio className="w-3.5 h-3.5" />
              {t("gen.download_audio", lang)}
            </a>
            <a
              href={`${API_BASE}${activeResult.srt_url}`}
              download="subtitles.srt"
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors"
            >
              <FileText className="w-3.5 h-3.5" />
              {t("gen.download_srt", lang)}
            </a>
          </div>
          <Button className="w-full" onClick={() => navigate("/playback")}>
            <Play className="w-4 h-4 mr-2" />
            {t("gen.play_btn", lang)}
          </Button>
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-between">
        <Button variant="outline" onClick={() => navigate("/cast")}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t("common.back", lang)}
        </Button>
        {!isDone ? (
          <Button
            data-testid="generate-btn"
            onClick={handleGenerate}
            disabled={starting || !!isRunning}
          >
            {starting || isRunning ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Wand2 className="w-4 h-4 mr-2" />
            )}
            {t("gen.start_btn", lang)}
          </Button>
        ) : (
          <Button
            variant="outline"
            onClick={handleReset}
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            Generate New
          </Button>
        )}
      </div>
    </div>
  );
}
