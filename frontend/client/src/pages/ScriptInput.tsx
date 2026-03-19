import { useState, useRef, useMemo } from "react";
import { useLocation } from "wouter";

import { useApp } from "@/App";
import { t } from "@/lib/i18n";
import { parseScript } from "@/lib/api";
import { SAMPLE_SCRIPT_EN, SAMPLE_VOICE_DESC_EN, SAMPLE_SCRIPT_ZH, SAMPLE_VOICE_DESC_ZH } from "@/lib/sampleData";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Upload, Wand2, BookOpen, ArrowRight, AlertCircle, Download, Lightbulb } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export default function ScriptInputPage() {
  const [, navigate] = useLocation();
  const { lang, setLang, scriptText, setScriptText, voiceDesc, setVoiceDesc, setScriptLines, setCharacters, setProjectId } = useApp();
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleParse() {
    if (!scriptText.trim()) {
      setError("Please enter a script first.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await parseScript(scriptText, voiceDesc || undefined);
      setScriptLines(result.lines);
      setCharacters(result.characters.map((c: any) => ({
        ...c,
        rate: "+0%",
        pitch: "+0Hz",
        volume: "+0%",
        locked: false,
      })));
      const pid = `proj_${Date.now().toString(36)}`;
      setProjectId(pid);
      navigate("/cast");
    } catch (e: any) {
      setError(e.message || "Failed to parse script");
      toast({ title: "Parse failed", description: e.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const content = ev.target?.result as string || "";
      // Check for voice descriptions separator
      const separatorIndex = content.indexOf("=== Voice Descriptions ===");
      if (separatorIndex !== -1) {
        // Split content into script text and voice descriptions
        const scriptText = content.substring(0, separatorIndex).trim();
        const voiceDesc = content.substring(separatorIndex + "=== Voice Descriptions ===".length).trim();
        setScriptText(scriptText);
        setVoiceDesc(voiceDesc);
      } else {
        // No voice descriptions found, set only script text
        setScriptText(content);
        setVoiceDesc("");
      }
    };
    reader.readAsText(file);
  }

  function loadSample(zh = false) {
    setScriptText(zh ? SAMPLE_SCRIPT_ZH : SAMPLE_SCRIPT_EN);
    setVoiceDesc(zh ? SAMPLE_VOICE_DESC_ZH : SAMPLE_VOICE_DESC_EN);
    // 加载中文示例时自动切换界面语言为中文
    if (zh) {
      setLang("zh");
    } else {
      setLang("en");
    }
  }

  function downloadSample(zh = false) {
    const script = zh ? SAMPLE_SCRIPT_ZH : SAMPLE_SCRIPT_EN;
    const voiceDesc = zh ? SAMPLE_VOICE_DESC_ZH : SAMPLE_VOICE_DESC_EN;
    const content = `${script}\n\n=== Voice Descriptions ===\n${voiceDesc}`;
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = zh ? 'sample_script_zh.txt' : 'sample_script_en.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  const { lineCount, charCount } = useMemo(() => {
    if (!scriptText.trim()) {
      return { lineCount: 0, charCount: 0 };
    }
    const lines = scriptText.trim().split("\n").filter(l => l.trim());
    const chars = new Set<string>();
    lines.forEach(line => {
      const m = line.match(/^([^：:]+)[：:]/);
      if (m) chars.add(m[1].trim());
    });
    return { lineCount: lines.length, charCount: chars.size };
  }, [scriptText]);

  return (
    <div className="h-full overflow-auto p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">{t("script.title", lang)}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t("app.subtitle", lang)}</p>
        </div>
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground">
              <Lightbulb className="w-4 h-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-96">
            <div className="space-y-4">
              <div>
                <p className="text-sm font-medium mb-2">{t("script.format_hint_title", lang)}</p>
                <p className="text-xs whitespace-pre-line text-muted-foreground">{t("script.format_hint_content", lang)}</p>
              </div>
              <div className="border-t pt-3">
                <p className="text-sm font-medium mb-2">{t("script.voice_desc_hint_title", lang)}</p>
                <p className="text-xs whitespace-pre-line text-muted-foreground">{t("script.voice_desc_hint_content", lang)}</p>
              </div>
            </div>
          </PopoverContent>
        </Popover>
      </div>

      {/* Sample buttons */}
      <div className="flex gap-1 mb-4 flex-wrap">
        <Button variant="outline" size="sm" onClick={() => loadSample(false)} data-testid="load-sample-en" className="text-xs">
          <BookOpen className="w-3 h-3 mr-1" />
          {t("script.load_sample", lang)} (EN)
        </Button>
        <Button variant="outline" size="sm" onClick={() => downloadSample(false)} data-testid="download-sample-en" className="text-xs">
          <Download className="w-3 h-3 mr-1" />
          {t("script.download_sample", lang)} (EN)
        </Button>
        <Button variant="outline" size="sm" onClick={() => loadSample(true)} data-testid="load-sample-zh" className="text-xs">
          <BookOpen className="w-3 h-3 mr-1" />
          {t("script.load_sample", lang)} (中文)
        </Button>
        <Button variant="outline" size="sm" onClick={() => downloadSample(true)} data-testid="download-sample-zh" className="text-xs">
          <Download className="w-3 h-3 mr-1" />
          {t("script.download_sample", lang)} (中文)
        </Button>
        <input ref={fileRef} type="file" accept=".txt,.md" className="hidden" onChange={handleFileUpload} />
        <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} data-testid="upload-file" className="text-xs">
          <Upload className="w-3 h-3 mr-1" />
          {t("script.upload_btn", lang)}
        </Button>
      </div>

      {/* Script input */}
      <div className="space-y-4">
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-sm font-medium text-foreground">{t("script.paste_label", lang)}</label>
            {lineCount > 0 && (
              <div className="flex gap-2">
                <Badge variant="secondary" className="text-xs">{lineCount} {t("common.lines", lang)}</Badge>
                <Badge variant="secondary" className="text-xs">{charCount} {t("common.characters", lang)}</Badge>
              </div>
            )}
          </div>
          <Textarea
            data-testid="script-textarea"
            value={scriptText}
            onChange={e => setScriptText(e.target.value)}
            placeholder={t("script.paste_placeholder", lang)}
            className="min-h-[280px] font-mono text-sm resize-y"
          />
        </div>

        <div>
          <label className="text-sm font-medium text-foreground block mb-1.5">{t("script.voice_desc_label", lang)}</label>
          <Textarea
            data-testid="voice-desc-textarea"
            value={voiceDesc}
            onChange={e => setVoiceDesc(e.target.value)}
            placeholder={t("script.voice_desc_placeholder", lang)}
            className="min-h-[120px] font-mono text-sm resize-y"
          />
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 rounded-md bg-destructive/10 text-destructive text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}

        <div className="flex justify-end">
          <Button
            data-testid="parse-btn"
            onClick={handleParse}
            disabled={loading || !scriptText.trim()}
            size="lg"
          >
            {loading ? (
              <>{t("script.parsing", lang)}</>
            ) : (
              <>
                <Wand2 className="w-4 h-4 mr-2" />
                {t("script.parse_btn", lang)}
                <ArrowRight className="w-4 h-4 ml-2" />
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
