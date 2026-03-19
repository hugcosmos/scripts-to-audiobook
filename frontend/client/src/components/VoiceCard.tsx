import { useState } from "react";
import { Play, Lock, LockOpen, ChevronDown, ChevronUp, User, Mic, BarChart3, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { useApp } from "@/App";
import { t } from "@/lib/i18n";
import { previewVoice } from "@/lib/api";
import type { CharacterData, VoiceData } from "../../../shared/schema";
import { useToast } from "@/hooks/use-toast";

interface VoiceCardProps {
  character: CharacterData;
  onChange: (updated: CharacterData) => void;
  allVoices: VoiceData[];
}

function parseRateNumber(rate: string): number {
  const m = rate.match(/([+-]?\d+)/);
  return m ? parseInt(m[1]) : 0;
}
function rateToStr(n: number): string {
  return n >= 0 ? `+${n}%` : `${n}%`;
}

function parsePitchNumber(pitch: string): number {
  const m = pitch.match(/([+-]?\d+)/);
  return m ? parseInt(m[1]) : 0;
}
function pitchToStr(n: number): string {
  return n >= 0 ? `+${n}Hz` : `${n}Hz`;
}

export default function VoiceCard({ character, onChange, allVoices }: VoiceCardProps) {
  const { lang } = useApp();
  const { toast } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [audioEl, setAudioEl] = useState<HTMLAudioElement | null>(null);

  const rate = character.rate ?? "+0%";
  const pitch = character.pitch ?? "+0Hz";
  const volume = character.volume ?? "+0%";
  const rateNum = parseRateNumber(rate);
  const pitchNum = parsePitchNumber(pitch);

  // Filter voices to same language and gender, then sort by quality score
  const langVoices = allVoices
    .filter(v => {
      const charLang = character.language === "zh" ? "chinese" : "english";
      const sameLanguage = v.base_language.toLowerCase() === charLang;
      const sameGender = !character.gender || !v.gender || character.gender.toLowerCase() === v.gender.toLowerCase();
      return sameLanguage && sameGender;
    })
    .sort((a, b) => {
      // Sort by combined quality score (narrator + dialogue) / 2
      const scoreA = ((a.narrator_fit_score || 0.5) + (a.dialogue_fit_score || 0.5)) / 2;
      const scoreB = ((b.narrator_fit_score || 0.5) + (b.dialogue_fit_score || 0.5)) / 2;
      return scoreB - scoreA; // Descending order
    });

  async function handlePreview() {
    if (previewing) {
      audioEl?.pause();
      setPreviewing(false);
      return;
    }
    
    // 根据角色语言选择预览文本
    const isChinese = character.language === "zh";
    const text = character.role_type === "narrator"
      ? isChinese
        ? "这是一段声音预览。适合朗读旁白内容。"
        : "This is a voice preview. Suitable for narrating content."
      : isChinese
        ? `${character.name}：你好，这是一段声音预览，测试语音效果。`
        : `${character.name}: Hello, this is a voice preview, testing the speech effect.`;

    setPreviewing(true);
    try {
      const url = await previewVoice(character.assigned_voice, text, rate, pitch, volume);
      const audio = new Audio(url);
      setAudioEl(audio);
      audio.play();
      audio.onended = () => setPreviewing(false);
    } catch (e) {
      toast({ title: "Preview failed", description: String(e), variant: "destructive" });
      setPreviewing(false);
    }
  }

  const scorePercent = Math.min(100, Math.round(character.match_score));

  return (
    <div
      data-testid={`voice-card-${character.name}`}
      className="rounded-lg border border-border bg-card overflow-hidden transition-all"
      style={{ borderLeftWidth: 3, borderLeftColor: character.color }}
    >
      {/* Card header */}
      <div className="p-4">
        <div className="flex items-start gap-3">
          {/* Avatar */}
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold shrink-0 text-white"
            style={{ background: character.color }}
          >
            {character.name.charAt(0)}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-semibold text-foreground truncate">{character.name}</h3>
              <Badge variant="outline" className="text-xs shrink-0" style={{ borderColor: character.color + "60", color: character.color }}>
                {character.role_type === "narrator" ? t("cast.narrator", lang) : t("cast.character_role", lang)}
              </Badge>
              {character.locked && (
                <Lock className="w-3 h-3 text-muted-foreground shrink-0" />
              )}
            </div>
            
            {/* Meta tags */}
            <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
              <span className="text-xs text-muted-foreground">{character.language === "zh" ? "Chinese" : "English"}</span>
              <span className="text-muted-foreground text-xs">·</span>
              <span className="text-xs text-muted-foreground">{character.voice_data?.accent_label || ""}</span>
              {character.gender && (
                <>
                  <span className="text-muted-foreground text-xs">·</span>
                  <span className="text-xs text-muted-foreground">{t(`common.${character.gender.toLowerCase()}`, lang)}</span>
                </>
              )}
              <span className="text-muted-foreground text-xs">·</span>
              <span className="text-xs text-muted-foreground">{t(`common.${character.age_bucket}`, lang)}</span>
              <span className="text-muted-foreground text-xs">·</span>
              <span className="text-xs text-muted-foreground">{character.line_count} {t("common.lines", lang)}</span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1 shrink-0">
            <Button
              data-testid={`preview-${character.name}`}
              size="icon"
              variant="ghost"
              className="w-8 h-8"
              onClick={handlePreview}
            >
              {previewing ? (
                <div className="flex items-end gap-0.5 h-4">
                  {[1,2,3,4,5].map(i => (
                    <div key={i} className="w-0.5 bg-primary rounded-full waveform-bar" style={{ height: 4, animationDelay: `${(i-1)*0.1}s` }} />
                  ))}
                </div>
              ) : (
                <Play className="w-3.5 h-3.5" />
              )}
            </Button>

            <Button
              data-testid={`lock-${character.name}`}
              size="icon"
              variant="ghost"
              className="w-8 h-8"
              onClick={() => onChange({ ...character, locked: !character.locked })}
            >
              {character.locked ? <Lock className="w-3.5 h-3.5 text-primary" /> : <LockOpen className="w-3.5 h-3.5" />}
            </Button>

            <Button
              size="icon"
              variant="ghost"
              className="w-8 h-8"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </Button>
          </div>
        </div>

        {/* Voice + score row */}
        <div className="mt-3 flex items-center gap-3">
          <div className="flex-1 min-w-0">
            <Select
              value={character.assigned_voice}
              onValueChange={(v) => onChange({ ...character, assigned_voice: v, voice_data: allVoices.find(x => x.voice_id === v) || character.voice_data })}
              disabled={character.locked}
            >
              <SelectTrigger className="h-8 text-xs" data-testid={`voice-select-${character.name}`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {langVoices.map(v => {
                  // Determine provider display name
                  const providerMap: Record<string, string> = {
                    edge: "Edge",
                    elevenlabs: "ElevenLabs",
                    iflytek: "讯飞",
                    baidu: "百度"
                  };
                  const provider = v.provider || "edge";
                  const providerLabel = providerMap[provider] || provider;
                  const isPaid = provider !== "edge";
                  
                  return (
                    <SelectItem key={v.voice_id} value={v.voice_id} className="text-xs">
                      <span className="font-medium">{v.display_name}</span>
                      <span className="ml-1 text-muted-foreground">{v.accent_label} · {v.gender}</span>
                      <span className={`ml-1.5 px-1 py-0.5 rounded text-[10px] ${isPaid ? 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-200' : 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-200'}`}>
                        {providerLabel}
                        {isPaid && " 💰"}
                      </span>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>

          <div className="shrink-0 text-right">
            <div className="text-xs text-muted-foreground">{t("cast.match_score", lang)}</div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <div className="w-16 h-1.5 rounded-full bg-muted overflow-hidden">
                <div className="h-full score-bar rounded-full" style={{ width: `${scorePercent}%` }} />
              </div>
              <span className="text-xs font-medium text-foreground">{scorePercent}</span>
            </div>
          </div>
        </div>

        {/* Match reasons */}
        {character.match_reasons && character.match_reasons.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {character.match_reasons.slice(0, 3).map((reason, i) => (
              <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                {reason}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Expanded controls */}
      {expanded && (
        <div className="border-t border-border px-4 py-3 space-y-4 bg-muted/20">
          {/* Rate */}
          <div>
            <div className="flex justify-between mb-1.5">
              <label className="text-xs font-medium text-foreground">{t("cast.rate", lang)}</label>
              <span className="text-xs text-muted-foreground">{rate}</span>
            </div>
            <Slider
              min={-50} max={50} step={5}
              value={[rateNum]}
              onValueChange={([v]) => onChange({ ...character, rate: rateToStr(v) })}
              disabled={character.locked}
            />
          </div>

          {/* Pitch */}
          <div>
            <div className="flex justify-between mb-1.5">
              <label className="text-xs font-medium text-foreground">{t("cast.pitch", lang)}</label>
              <span className="text-xs text-muted-foreground">{pitch}</span>
            </div>
            <Slider
              min={-50} max={50} step={5}
              value={[pitchNum]}
              onValueChange={([v]) => onChange({ ...character, pitch: pitchToStr(v) })}
              disabled={character.locked}
            />
          </div>

          {/* Alternatives */}
          {character.voice_alternatives && character.voice_alternatives.length > 0 && (
            <div>
              <p className="text-xs font-medium text-foreground mb-2">{t("cast.alternatives", lang)}</p>
              <div className="space-y-1">
                {character.voice_alternatives.slice(0, 3).map(({ voice, score }) => (
                  <button
                    key={voice.voice_id}
                    className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left hover:bg-accent transition-colors"
                    onClick={() => onChange({ ...character, assigned_voice: voice.voice_id, voice_data: voice, match_score: score, locked: false })}
                  >
                    <div className="flex-1 min-w-0">
                      <span className="text-xs font-medium truncate block">{voice.display_name}</span>
                      <span className="text-[10px] text-muted-foreground">{voice.accent_label} · {voice.gender}</span>
                    </div>
                    <span className="text-xs text-muted-foreground shrink-0">{Math.round(score)}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
