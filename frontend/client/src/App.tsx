import { useState, createContext, useContext, useEffect } from "react";
import { Switch, Route, Router } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import { Toaster } from "@/components/ui/toaster";
import { type Lang, t } from "@/lib/i18n";
import type { CharacterData, ScriptLine, TimelineData } from "../../shared/schema";

import ScriptInputPage from "@/pages/ScriptInput";
import VoiceCastPage from "@/pages/VoiceCast";
import GeneratePage from "@/pages/Generate";
import PlaybackPage from "@/pages/Playback";
import CatalogPage from "@/pages/Catalog";
import LibraryPage from "@/pages/Library";
import SettingsPage from "@/pages/Settings";
import NotFound from "@/pages/not-found";
import Layout from "@/components/Layout";
import { PerplexityAttribution } from "@/components/PerplexityAttribution";

// ─── App-wide state context ───────────────────────────────────────────────────

interface AppState {
  lang: Lang;
  setLang: (l: Lang) => void;
  scriptText: string;
  setScriptText: (t: string) => void;
  voiceDesc: string;
  setVoiceDesc: (t: string) => void;
  scriptLines: ScriptLine[];
  setScriptLines: (l: ScriptLine[]) => void;
  characters: CharacterData[];
  setCharacters: (c: CharacterData[]) => void;
  projectId: string;
  setProjectId: (id: string) => void;
  timeline: TimelineData | null;
  setTimeline: (t: TimelineData | null) => void;
  audioUrl: string;
  setAudioUrl: (u: string) => void;
  isDark: boolean;
  setIsDark: (d: boolean) => void;
  generationResult: any | null;
  setGenerationResult: (r: any) => void;
}

export const AppContext = createContext<AppState>({} as AppState);
export const useApp = () => useContext(AppContext);

// ─── App Root ─────────────────────────────────────────────────────────────────

const STORAGE_KEY = "scripts-to-audiobook-state";

function loadSavedState() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      return JSON.parse(saved);
    }
  } catch {
    // ignore
  }
  return null;
}

export default function App() {
  const [isHydrated, setIsHydrated] = useState(false);
  const savedState = loadSavedState();
  
  const [lang, setLang] = useState<Lang>(savedState?.lang || "en");
  const [scriptText, setScriptText] = useState("");
  const [voiceDesc, setVoiceDesc] = useState("");
  const [scriptLines, setScriptLines] = useState<ScriptLine[]>([]);
  const [characters, setCharacters] = useState<CharacterData[]>([]);
  const [projectId, setProjectId] = useState("");
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [generationResult, setGenerationResult] = useState<any | null>(null);
  const [isDark, setIsDark] = useState(() => {
    if (savedState?.isDark !== undefined) return savedState.isDark;
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  // Mark as hydrated after initial render
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // Persist state to localStorage
  useEffect(() => {
    const stateToSave = {
      lang, scriptText, voiceDesc, scriptLines, characters, 
      projectId, timeline, audioUrl, generationResult, isDark
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stateToSave));
  }, [lang, scriptText, voiceDesc, scriptLines, characters, projectId, timeline, audioUrl, generationResult, isDark]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
  }, [isDark]);

  const ctx: AppState = {
    lang, setLang,
    scriptText, setScriptText,
    voiceDesc, setVoiceDesc,
    scriptLines, setScriptLines,
    characters, setCharacters,
    projectId, setProjectId,
    timeline, setTimeline,
    audioUrl, setAudioUrl,
    isDark, setIsDark,
    generationResult, setGenerationResult,
  };

  // Show loading spinner during hydration to prevent flash of wrong content
  if (!isHydrated) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-background">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <AppContext.Provider value={ctx}>
        <Router hook={useHashLocation}><Switch>
          <Route path="/" component={() => <Layout><ScriptInputPage /></Layout>} />
          <Route path="/cast" component={() => <Layout><VoiceCastPage /></Layout>} />
          <Route path="/generate" component={() => <Layout><GeneratePage /></Layout>} />
          <Route path="/playback" component={() => <Layout><PlaybackPage /></Layout>} />
          <Route path="/catalog" component={() => <Layout><CatalogPage /></Layout>} />
          <Route path="/library" component={() => <Layout><LibraryPage /></Layout>} />
          <Route path="/settings" component={() => <Layout><SettingsPage /></Layout>} />
          <Route component={NotFound} />
        </Switch></Router>
        <Toaster />
        <PerplexityAttribution />
      </AppContext.Provider>
    </QueryClientProvider>
  );
}
