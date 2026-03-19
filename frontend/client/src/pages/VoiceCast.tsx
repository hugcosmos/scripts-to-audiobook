import { useLocation } from "wouter";
import { useState, useEffect, useMemo } from "react";

import { useApp } from "@/App";
import { t } from "@/lib/i18n";
import { useQuery } from "@tanstack/react-query";
import { fetchVoicesByProvider } from "@/lib/api";
import VoiceCard from "@/components/VoiceCard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, ArrowRight, RefreshCw, Users } from "lucide-react";
import type { CharacterData, VoiceData } from "../../../shared/schema";

export default function VoiceCastPage() {
  const [, navigate] = useLocation();
  const { lang, characters, setCharacters, scriptLines } = useApp();

  // Fetch voices from all providers
  const { data: voicesByProvider, isLoading } = useQuery({
    queryKey: ["/api/voices/by-provider"],
    queryFn: () => fetchVoicesByProvider(),
  });

  // Combine voices from all providers
  const allVoices: VoiceData[] = useMemo(() => {
    if (!voicesByProvider) return [];
    
    const voices: VoiceData[] = [];
    Object.entries(voicesByProvider).forEach(([provider, data]: [string, any]) => {
      if (data.voices && Array.isArray(data.voices)) {
        voices.push(...data.voices);
      }
    });
    return voices;
  }, [voicesByProvider]);

  function handleCharacterChange(updated: CharacterData) {
    setCharacters(characters.map(c => c.name === updated.name ? updated : c));
  }

  // Show loading state initially, then check for data
  const [isCheckingData, setIsCheckingData] = useState(true);
  
  useEffect(() => {
    // Small delay to ensure data is loaded from localStorage
    const timer = setTimeout(() => setIsCheckingData(false), 100);
    return () => clearTimeout(timer);
  }, []);

  if (isCheckingData) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!characters.length) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center space-y-3">
          <Users className="w-12 h-12 mx-auto text-muted-foreground" />
          <p className="text-muted-foreground">{t("cast.subtitle", lang)}</p>
          <Button variant="outline" onClick={() => navigate("/")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t("common.back", lang)}
          </Button>
        </div>
      </div>
    );
  }

  const narratorChars = characters.filter(c => c.role_type === "narrator");
  const roleChars = characters.filter(c => c.role_type === "character");

  return (
    <div className="h-full overflow-auto p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold text-foreground">{t("cast.title", lang)}</h1>
            <p className="text-sm text-muted-foreground mt-1">{t("cast.subtitle", lang)}</p>
            <p className="text-xs text-muted-foreground mt-1">
              Voices sorted by quality score (best matches first)
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{characters.length} {t("common.characters", lang)}</Badge>
            <Badge variant="secondary">{scriptLines.length} {t("common.lines", lang)}</Badge>
          </div>
        </div>

        {/* Script stats strip */}
        <div className="flex items-center gap-2 mb-6 p-3 rounded-lg bg-muted/40 border border-border text-xs text-muted-foreground flex-wrap">
          {characters.map(c => (
            <div key={c.name} className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full" style={{ background: c.color }} />
              <span style={{ color: c.color }} className="font-medium">{c.name}</span>
              <span>({c.line_count} {t("common.lines", lang)})</span>
            </div>
          ))}
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[1,2,3].map(i => (
              <div key={i} className="h-28 rounded-lg bg-muted animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {/* Narrator first */}
            {narratorChars.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                  {t("cast.narrator", lang)}
                </p>
                <div className="space-y-3">
                  {narratorChars.map(c => (
                    <VoiceCard
                      key={c.name}
                      character={c}
                      onChange={handleCharacterChange}
                      allVoices={allVoices}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Characters */}
            {roleChars.length > 0 && (
              <div className={narratorChars.length > 0 ? "mt-4" : ""}>
                {narratorChars.length > 0 && (
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                    {t("cast.character_role", lang)}s
                  </p>
                )}
                <div className="space-y-3">
                  {roleChars.map(c => (
                    <VoiceCard
                      key={c.name}
                      character={c}
                      onChange={handleCharacterChange}
                      allVoices={allVoices}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Navigation */}
        <div className="flex justify-between mt-6 pt-6 border-t border-border">
          <Button variant="outline" onClick={() => navigate("/")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t("common.back", lang)}
          </Button>
          <Button onClick={() => navigate("/generate")} data-testid="goto-generate">
            {t("common.next", lang)}
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </div>
    </div>
  );
}
