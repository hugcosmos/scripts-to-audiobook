import { useState } from "react";
import { useApp } from "@/App";
import { t } from "@/lib/i18n";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchVoicesByProvider, fetchFeaturedVoices, previewVoice, addCustomVoice, deleteCustomVoice, reorderCustomVoices } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Play, Loader2, Star, Mic2, Plus, Trash2, GripVertical, Check, X } from "lucide-react";

interface VoiceData {
  voice_id: string;
  display_name: string;
  full_name?: string;
  language?: string;
  locale?: string;
  base_language?: string;
  gender?: string;
  quality_score?: number;
  narrator_fit_score?: number;
  dialogue_fit_score?: number;
  personalities?: string[];
  accent_label?: string;
  provider?: string;
  provider_display?: string;
}

interface ProviderData {
  name: string;
  display_name: string;
  voices: VoiceData[];
  is_available: boolean;
}

export default function CatalogPage() {
  const { lang } = useApp();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [filterLang, setFilterLang] = useState("all");
  const [filterGender, setFilterGender] = useState("all");
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("featured");
  
  // Voice management state
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [newVoice, setNewVoice] = useState({
    voice_id: "",
    display_name: "",
    language: "en",
    gender: "Female"
  });
  const [isReordering, setIsReordering] = useState(false);
  const [draggedVoice, setDraggedVoice] = useState<VoiceData | null>(null);
  const [voicesOrder, setVoicesOrder] = useState<VoiceData[]>([]);

  const { data: providersData, isLoading: isLoadingProviders } = useQuery({
    queryKey: ["/api/voices/by-provider", filterLang],
    queryFn: () => fetchVoicesByProvider(undefined, filterLang !== "all" ? filterLang : undefined),
  });

  const { data: featuredData, isLoading: isLoadingFeatured } = useQuery({
    queryKey: ["/api/voices/featured"],
    queryFn: fetchFeaturedVoices,
  });

  const providers: Record<string, ProviderData> = providersData || {};
  const featuredVoices: VoiceData[] = featuredData?.voices || [];

  // Voice management mutations
  const addVoiceMutation = useMutation({
    mutationFn: ({ provider, voice }: { provider: string; voice: any }) => addCustomVoice(provider, voice),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/voices/by-provider"] });
      setIsAddDialogOpen(false);
      setNewVoice({ voice_id: "", display_name: "", language: "en", gender: "Female" });
    },
  });

  const deleteVoiceMutation = useMutation({
    mutationFn: ({ provider, voiceId }: { provider: string; voiceId: string }) => deleteCustomVoice(provider, voiceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/voices/by-provider"] });
    },
  });

  const reorderVoiceMutation = useMutation({
    mutationFn: ({ provider, voices }: { provider: string; voices: VoiceData[] }) => reorderCustomVoices(provider, voices),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/voices/by-provider"] });
      setIsReordering(false);
    },
  });

  const filterVoices = (voices: VoiceData[]) => {
    return voices.filter((v: VoiceData) => {
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        (v.display_name?.toLowerCase() || "").includes(q) ||
        (v.locale?.toLowerCase() || "").includes(q) ||
        (v.accent_label?.toLowerCase() || "").includes(q) ||
        (v.personalities?.some(p => p.toLowerCase().includes(q)))
      );
    }).filter((v: VoiceData) => {
      if (filterGender === "all") return true;
      return v.gender === filterGender;
    });
  };

  async function handlePreview(voice: VoiceData) {
    if (previewingId === voice.voice_id) {
      setPreviewingId(null);
      return;
    }
    setPreviewingId(voice.voice_id || null);
    try {
      const isChineseVoice = voice.base_language?.toLowerCase() === "chinese" || voice.locale?.startsWith("zh-");
      const text = isChineseVoice
        ? `你好，我是${voice.display_name}。这是一段声音预览，展示我的语音效果。`
        : `Hello, I'm ${voice.display_name}. This is a preview of my voice.`;
      const url = await previewVoice(voice.voice_id || "", text);
      const audio = new Audio(url);
      audio.play();
      audio.onended = () => setPreviewingId(null);
    } catch (e) {
      setPreviewingId(null);
    }
  }

  // Voice management functions
  function handleAddVoice(provider: string) {
    setIsAddDialogOpen(true);
  }

  function handleDeleteVoice(provider: string, voiceId: string) {
    if (confirm("Are you sure you want to delete this voice?")) {
      deleteVoiceMutation.mutate({ provider, voiceId });
    }
  }

  function startReordering(voices: VoiceData[]) {
    setVoicesOrder(voices);
    setIsReordering(true);
  }

  function cancelReordering() {
    setIsReordering(false);
    setVoicesOrder([]);
  }

  function saveReordering(provider: string) {
    reorderVoiceMutation.mutate({ provider, voices: voicesOrder });
  }

  // Drag and drop functions
  function handleDragStart(e: React.DragEvent, voice: VoiceData) {
    e.dataTransfer.setData("voiceId", voice.voice_id);
    setDraggedVoice(voice);
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
  }

  function handleDrop(e: React.DragEvent, targetVoice: VoiceData) {
    e.preventDefault();
    if (!draggedVoice || draggedVoice.voice_id === targetVoice.voice_id) return;

    const newOrder = [...voicesOrder];
    const draggedIndex = newOrder.findIndex(v => v.voice_id === draggedVoice.voice_id);
    const targetIndex = newOrder.findIndex(v => v.voice_id === targetVoice.voice_id);

    if (draggedIndex !== -1 && targetIndex !== -1) {
      newOrder.splice(draggedIndex, 1);
      newOrder.splice(targetIndex, 0, draggedVoice);
      setVoicesOrder(newOrder);
    }
  }

  const renderVoiceCard = (voice: VoiceData, provider: string) => (
    <div
      key={`${provider}-${voice.voice_id}`}
      className={`rounded-lg border border-border bg-card p-3 hover:border-primary/40 transition-colors ${isReordering ? 'cursor-move' : ''}`}
      draggable={isReordering}
      onDragStart={(e) => isReordering && handleDragStart(e, voice)}
      onDragOver={isReordering ? handleDragOver : undefined}
      onDrop={(e) => isReordering && handleDrop(e, voice)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            {isReordering && (
              <GripVertical className="w-3.5 h-3.5 text-muted-foreground" />
            )}
            <span className="font-medium text-sm text-foreground">{voice.display_name}</span>
            <Badge variant="outline" className="text-[10px] h-4 px-1">
              {voice.gender === "Female" ? t("catalog.female", lang) : t("catalog.male", lang)}
            </Badge>
            {voice.provider && voice.provider !== "edge" && (
              <Badge variant="secondary" className="text-[10px] h-4 px-1">
                {voice.provider_display || voice.provider}
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            {voice.accent_label || voice.locale} · {voice.locale}
          </p>
        </div>
        <div className="flex gap-1">
          {!isReordering && voice.provider && (
            <Button
              size="icon"
              variant="ghost"
              className="w-7 h-7 shrink-0 text-red-500 hover:bg-red-500/10"
              onClick={() => handleDeleteVoice(provider, voice.voice_id)}
            >
              <Trash2 className="w-3.5 h-3.5" />
            </Button>
          )}
          <Button
            size="icon"
            variant="ghost"
            className="w-7 h-7 shrink-0"
            onClick={() => handlePreview(voice)}
          >
            {previewingId === voice.voice_id ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5" />
            )}
          </Button>
        </div>
      </div>

      {voice.personalities && voice.personalities.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {voice.personalities.slice(0, 3).map(p => (
            <span key={p} className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{p}</span>
          ))}
        </div>
      )}

      <div className="flex gap-3 mt-2">
        <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
          <span>{t("catalog.narrator_score", lang)}</span>
          <div className="w-8 h-1 rounded-full bg-muted overflow-hidden">
            <div className="h-full score-bar" style={{ width: `${(voice.narrator_fit_score || 0.5) * 100}%` }} />
          </div>
        </div>
        <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
          <span>{t("catalog.dialogue_score", lang)}</span>
          <div className="w-8 h-1 rounded-full bg-muted overflow-hidden">
            <div className="h-full score-bar" style={{ width: `${(voice.dialogue_fit_score || 0.5) * 100}%` }} />
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="h-full overflow-auto p-6">
      <div className="max-w-5xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-foreground">{t("catalog.title", lang)}</h1>
          <p className="text-sm text-muted-foreground mt-1">Browse all available voices from multiple providers</p>
        </div>

        {/* Filters */}
        <div className="flex gap-3 mb-6 flex-wrap">
          <Input
            placeholder={t("catalog.search", lang)}
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-64"
          />
          <Select value={filterLang} onValueChange={setFilterLang}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("catalog.all", lang)}</SelectItem>
              <SelectItem value="en">{t("catalog.english", lang)}</SelectItem>
              <SelectItem value="zh">{t("catalog.chinese", lang)}</SelectItem>
            </SelectContent>
          </Select>
          <Select value={filterGender} onValueChange={setFilterGender}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("catalog.all", lang)}</SelectItem>
              <SelectItem value="Female">{t("catalog.female", lang)}</SelectItem>
              <SelectItem value="Male">{t("catalog.male", lang)}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Provider Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="mb-4 flex-wrap h-auto">
            <TabsTrigger value="featured" className="flex items-center gap-1.5">
              <Star className="w-3.5 h-3.5" />
              {t("catalog.featured", lang)}
            </TabsTrigger>
            <TabsTrigger value="edge">{t("catalog.edge", lang)}</TabsTrigger>
            <TabsTrigger value="iflytek">{t("catalog.iflytek", lang)}</TabsTrigger>
            <TabsTrigger value="baidu">{t("catalog.baidu", lang)}</TabsTrigger>
            <TabsTrigger value="elevenlabs">{t("catalog.elevenlabs", lang)}</TabsTrigger>
          </TabsList>

          {/* Featured Voices */}
          <TabsContent value="featured">
            {isLoadingFeatured ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {[...Array(9)].map((_, i) => (<div key={i} className="h-28 rounded-lg bg-muted animate-pulse" />))}
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm text-muted-foreground">
                    Top quality voices from all providers, sorted by quality score
                  </p>
                  <Badge variant="secondary">{filterVoices(featuredVoices).length} voices</Badge>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {filterVoices(featuredVoices).map(voice => renderVoiceCard(voice, voice.provider || "edge"))}
                </div>
              </>
            )}
          </TabsContent>

          {/* Edge TTS */}
          <TabsContent value="edge">
            {isLoadingProviders ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {[...Array(9)].map((_, i) => (<div key={i} className="h-28 rounded-lg bg-muted animate-pulse" />))}
              </div>
            ) : providers.edge ? (
              <>
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm text-muted-foreground">
                    Microsoft Edge TTS - Free, high-quality voices
                  </p>
                  <div className="flex gap-2">
                    {isReordering ? (
                      <>
                        <Button variant="secondary" size="sm" onClick={() => saveReordering("edge")}>
                          <Check className="w-3.5 h-3.5 mr-1" />
                          Save
                        </Button>
                        <Button variant="ghost" size="sm" onClick={cancelReordering}>
                          <X className="w-3.5 h-3.5 mr-1" />
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => startReordering(providers.edge.voices || [])}>
                          <GripVertical className="w-3.5 h-3.5 mr-1" />
                          Reorder
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleAddVoice("edge")}>
                          <Plus className="w-3.5 h-3.5 mr-1" />
                          Add Voice
                        </Button>
                      </>
                    )}
                    <Badge variant="secondary">{filterVoices(providers.edge.voices).length} voices</Badge>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {filterVoices(isReordering ? voicesOrder : providers.edge.voices || []).map(voice => renderVoiceCard(voice, "edge"))}
                </div>
              </>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <Mic2 className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Edge TTS voices not available</p>
              </div>
            )}
          </TabsContent>

          {/* iFlytek */}
          <TabsContent value="iflytek">
            {isLoadingProviders ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {[...Array(6)].map((_, i) => (<div key={i} className="h-28 rounded-lg bg-muted animate-pulse" />))}
              </div>
            ) : (
              <>
                {!providers.iflytek?.is_available && (
                  <div className="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-sm text-amber-600">
                    <p>iFlytek (科大讯飞) credentials not configured. Voices shown below are available, but you need to add API credentials in Settings to use them.</p>
                  </div>
                )}
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm text-muted-foreground">
                    科大讯飞 - Premium Chinese voices
                  </p>
                  <div className="flex gap-2">
                    {isReordering ? (
                      <>
                        <Button variant="secondary" size="sm" onClick={() => saveReordering("iflytek")}>
                          <Check className="w-3.5 h-3.5 mr-1" />
                          Save
                        </Button>
                        <Button variant="ghost" size="sm" onClick={cancelReordering}>
                          <X className="w-3.5 h-3.5 mr-1" />
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => startReordering(providers.iflytek?.voices || [])}>
                          <GripVertical className="w-3.5 h-3.5 mr-1" />
                          Reorder
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleAddVoice("iflytek")}>
                          <Plus className="w-3.5 h-3.5 mr-1" />
                          Add Voice
                        </Button>
                      </>
                    )}
                    <Badge variant="secondary">{filterVoices(providers.iflytek?.voices || []).length} voices</Badge>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {filterVoices(isReordering ? voicesOrder : providers.iflytek?.voices || []).map(voice => renderVoiceCard(voice, "iflytek"))}
                </div>
              </>
            )}
          </TabsContent>

          {/* Baidu */}
          <TabsContent value="baidu">
            {isLoadingProviders ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {[...Array(6)].map((_, i) => (<div key={i} className="h-28 rounded-lg bg-muted animate-pulse" />))}
              </div>
            ) : (
              <>
                {!providers.baidu?.is_available && (
                  <div className="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-sm text-amber-600">
                    <p>Baidu (百度语音) credentials not configured. Voices shown below are available, but you need to add API credentials in Settings to use them.</p>
                  </div>
                )}
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm text-muted-foreground">
                    百度语音 - Chinese TTS voices
                  </p>
                  <div className="flex gap-2">
                    {isReordering ? (
                      <>
                        <Button variant="secondary" size="sm" onClick={() => saveReordering("baidu")}>
                          <Check className="w-3.5 h-3.5 mr-1" />
                          Save
                        </Button>
                        <Button variant="ghost" size="sm" onClick={cancelReordering}>
                          <X className="w-3.5 h-3.5 mr-1" />
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => startReordering(providers.baidu?.voices || [])}>
                          <GripVertical className="w-3.5 h-3.5 mr-1" />
                          Reorder
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleAddVoice("baidu")}>
                          <Plus className="w-3.5 h-3.5 mr-1" />
                          Add Voice
                        </Button>
                      </>
                    )}
                    <Badge variant="secondary">{filterVoices(providers.baidu?.voices || []).length} voices</Badge>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {filterVoices(isReordering ? voicesOrder : providers.baidu?.voices || []).map(voice => renderVoiceCard(voice, "baidu"))}
                </div>
              </>
            )}
          </TabsContent>

          {/* ElevenLabs */}
          <TabsContent value="elevenlabs">
            {isLoadingProviders ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {[...Array(6)].map((_, i) => (<div key={i} className="h-28 rounded-lg bg-muted animate-pulse" />))}
              </div>
            ) : (
              <>
                {!providers.elevenlabs?.is_available && (
                  <div className="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-sm text-amber-600">
                    <p>ElevenLabs API key not configured. Add your API key in Settings to fetch available voices from your account.</p>
                  </div>
                )}
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm text-muted-foreground">
                    ElevenLabs - High-quality AI voices
                  </p>
                  <div className="flex gap-2">
                    {isReordering ? (
                      <>
                        <Button variant="secondary" size="sm" onClick={() => saveReordering("elevenlabs")}>
                          <Check className="w-3.5 h-3.5 mr-1" />
                          Save
                        </Button>
                        <Button variant="ghost" size="sm" onClick={cancelReordering}>
                          <X className="w-3.5 h-3.5 mr-1" />
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => startReordering(providers.elevenlabs?.voices || [])}>
                          <GripVertical className="w-3.5 h-3.5 mr-1" />
                          Reorder
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleAddVoice("elevenlabs")}>
                          <Plus className="w-3.5 h-3.5 mr-1" />
                          Add Voice
                        </Button>
                      </>
                    )}
                    <Badge variant="secondary">{filterVoices(providers.elevenlabs?.voices || []).length} voices</Badge>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {filterVoices(isReordering ? voicesOrder : providers.elevenlabs?.voices || []).map(voice => renderVoiceCard(voice, "elevenlabs"))}
                </div>
              </>
            )}
          </TabsContent>
        </Tabs>

        {/* Add Voice Dialog */}
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Add Custom Voice</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="voice_id">Voice ID</Label>
                <Input
                  id="voice_id"
                  value={newVoice.voice_id}
                  onChange={(e) => setNewVoice({ ...newVoice, voice_id: e.target.value })}
                  placeholder="Enter voice ID"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="display_name">Display Name</Label>
                <Input
                  id="display_name"
                  value={newVoice.display_name}
                  onChange={(e) => setNewVoice({ ...newVoice, display_name: e.target.value })}
                  placeholder="Enter display name"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="language">Language</Label>
                <Select value={newVoice.language} onValueChange={(value) => setNewVoice({ ...newVoice, language: value })}>
                  <SelectTrigger id="language">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="zh">Chinese</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="gender">Gender</Label>
                <Select value={newVoice.gender} onValueChange={(value) => setNewVoice({ ...newVoice, gender: value })}>
                  <SelectTrigger id="gender">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Female">Female</SelectItem>
                    <SelectItem value="Male">Male</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setIsAddDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => addVoiceMutation.mutate({ provider: activeTab, voice: newVoice })}
                disabled={addVoiceMutation.isPending}
              >
                {addVoiceMutation.isPending ? "Adding..." : "Add Voice"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
