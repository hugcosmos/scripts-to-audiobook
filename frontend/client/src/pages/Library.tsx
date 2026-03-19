import { useState } from "react";
import { useApp } from "@/App";
import { useLocation } from "wouter";
import { fetchTimeline } from "@/lib/api";
import { t } from "@/lib/i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchAlbums, createAlbum, updateAlbum, deleteAlbum,
  fetchAudioFiles, moveAudioFileToAlbum, deleteAudioFile, updateAudioFile, getAudioUrl,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { Library, Plus, Folder, FolderOpen, Music, MoreVertical, Play, Download, Trash2, Edit2, Move, Clock, FileAudio } from "lucide-react";

interface Album { id: string; name: string; description?: string; cover_image?: string; audio_count: number; created_at: number; updated_at: number; }
interface AudioFile { id: string; album_id?: string; title: string; project_id: string; duration_ms?: number; segment_count?: number; file_path: string; created_at: number; characters?: any[]; }

export default function LibraryPage() {
  const { lang, setTimeline, setAudioUrl, setCharacters } = useApp();
  const [, navigate] = useLocation();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selectedAlbum, setSelectedAlbum] = useState<string | null>(null);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isMoveDialogOpen, setIsMoveDialogOpen] = useState(false);
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
  const [editingAlbum, setEditingAlbum] = useState<Album | null>(null);
  const [albumToDelete, setAlbumToDelete] = useState<Album | null>(null);
  const [audioToMove, setAudioToMove] = useState<AudioFile | null>(null);
  const [audioToRename, setAudioToRename] = useState<AudioFile | null>(null);
  const [newAudioTitle, setNewAudioTitle] = useState("");
  const [newAlbumName, setNewAlbumName] = useState("");
  const [newAlbumDescription, setNewAlbumDescription] = useState("");
  const [targetAlbumId, setTargetAlbumId] = useState<string>("__none__");
  const [playingAudio, setPlayingAudio] = useState<string | null>(null);

  const { data: albumsData, isLoading: isLoadingAlbums } = useQuery({ queryKey: ["/api/library/albums"], queryFn: fetchAlbums });
  const { data: audioData, isLoading: isLoadingAudio } = useQuery({ queryKey: ["/api/library/audio-files", selectedAlbum], queryFn: () => fetchAudioFiles(selectedAlbum || undefined) });

  const albums: Album[] = albumsData?.albums || [];
  const audioFiles: AudioFile[] = audioData?.audio_files || [];

  const createAlbumMutation = useMutation({
    mutationFn: () => createAlbum(newAlbumName, newAlbumDescription),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["/api/library/albums"] }); setIsCreateDialogOpen(false); setNewAlbumName(""); setNewAlbumDescription(""); toast({ title: t("common.success", lang), description: "Album created" }); },
    onError: () => { toast({ title: t("common.error", lang), description: "Failed to create album", variant: "destructive" }); }
  });

  const updateAlbumMutation = useMutation({
    mutationFn: () => updateAlbum(editingAlbum!.id, { name: newAlbumName, description: newAlbumDescription }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["/api/library/albums"] }); setIsEditDialogOpen(false); setEditingAlbum(null); toast({ title: t("common.success", lang), description: "Album updated" }); },
    onError: () => { toast({ title: t("common.error", lang), description: "Failed to update album", variant: "destructive" }); }
  });

  const deleteAlbumMutation = useMutation({
    mutationFn: () => deleteAlbum(albumToDelete!.id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["/api/library/albums"] }); queryClient.invalidateQueries({ queryKey: ["/api/library/audio-files"] }); setIsDeleteDialogOpen(false); setAlbumToDelete(null); if (selectedAlbum === albumToDelete?.id) setSelectedAlbum(null); toast({ title: t("common.success", lang), description: "Album deleted" }); },
    onError: () => { toast({ title: t("common.error", lang), description: "Failed to delete album", variant: "destructive" }); }
  });

  const moveAudioMutation = useMutation({
    mutationFn: () => moveAudioFileToAlbum(audioToMove!.id, targetAlbumId === "__none__" ? null : targetAlbumId),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["/api/library/audio-files"] }); queryClient.invalidateQueries({ queryKey: ["/api/library/albums"] }); setIsMoveDialogOpen(false); setAudioToMove(null); setTargetAlbumId("__none__"); toast({ title: t("common.success", lang), description: "Audio moved" }); },
    onError: () => { toast({ title: t("common.error", lang), description: "Failed to move audio", variant: "destructive" }); }
  });

  const deleteAudioMutation = useMutation({
    mutationFn: (audioId: string) => deleteAudioFile(audioId),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["/api/library/audio-files"] }); queryClient.invalidateQueries({ queryKey: ["/api/library/albums"] }); toast({ title: t("common.success", lang), description: "Audio deleted" }); },
    onError: () => { toast({ title: t("common.error", lang), description: "Failed to delete audio", variant: "destructive" }); }
  });

  const updateAudioMutation = useMutation({
    mutationFn: () => updateAudioFile(audioToRename!.id, { title: newAudioTitle }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["/api/library/audio-files"] }); setIsRenameDialogOpen(false); setAudioToRename(null); setNewAudioTitle(""); toast({ title: t("common.success", lang), description: "Audio renamed" }); },
    onError: () => { toast({ title: t("common.error", lang), description: "Failed to rename audio", variant: "destructive" }); }
  });

  const handleCreateAlbum = () => { if (!newAlbumName.trim()) return; createAlbumMutation.mutate(); };
  const handleUpdateAlbum = () => { if (!newAlbumName.trim() || !editingAlbum) return; updateAlbumMutation.mutate(); };
  const openEditDialog = (album: Album) => { setEditingAlbum(album); setNewAlbumName(album.name); setNewAlbumDescription(album.description || ""); setIsEditDialogOpen(true); };
  const openDeleteDialog = (album: Album) => { setAlbumToDelete(album); setIsDeleteDialogOpen(true); };
  const openMoveDialog = (audio: AudioFile) => { setAudioToMove(audio); setTargetAlbumId(audio.album_id || "__none__"); setIsMoveDialogOpen(true); };
  const openRenameDialog = (audio: AudioFile) => { setAudioToRename(audio); setNewAudioTitle(audio.title); setIsRenameDialogOpen(true); };
  const formatDuration = (ms?: number) => { if (!ms) return "--:--"; const totalSeconds = Math.floor(ms / 1000); const minutes = Math.floor(totalSeconds / 60); const seconds = totalSeconds % 60; return `${minutes}:${seconds.toString().padStart(2, "0")}`; };
  const formatDate = (timestamp: number) => new Date(timestamp * 1000).toLocaleDateString(lang === "zh" ? "zh-CN" : "en-US");

  const handlePlay = async (audio: AudioFile) => {
    if (playingAudio === audio.id) { 
      setPlayingAudio(null); 
      return; 
    }
    // Load timeline and navigate to playback
    try {
      const tl = await fetchTimeline(audio.project_id);
      // Set characters from audio data for color display
      if (audio.characters) {
        const charactersWithColors: import("../../../shared/schema").CharacterData[] = audio.characters.map((c: any) => {
          const isNarrator = c.name.toLowerCase().includes('narrator') || c.name === '旁白';
          // Use stored color or fall back to defaults
          const defaultColor = isNarrator ? "#94A3B8" : "#60A5FA";
          return {
            name: c.name,
            role_type: isNarrator ? 'narrator' as const : 'character' as const,
            color: c.color || defaultColor,  // Use stored color!
            language: "en",
            locale_hint: null,
            gender: null,
            age_bucket: "adult",
            line_count: 0,
            assigned_voice: c.voice_id || "",
            voice_data: {} as any,
            match_score: 0,
            match_reasons: [],
            voice_alternatives: [],
            rate: "+0%",
            pitch: "+0Hz",
            volume: "+0%",
            locked: false,
          };
        });
        setCharacters(charactersWithColors);
      }
      setTimeline(tl);
      setAudioUrl(getAudioUrl(audio.project_id));
      navigate("/playback");
    } catch (e) {
      // Silent fail for audio load errors
    }
  };

  const handleDownload = (audio: AudioFile) => {
    const url = getAudioUrl(audio.project_id);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${audio.title}.mp3`;
    a.click();
  };

  return (
    <div className="h-full overflow-auto p-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold text-foreground">{t("library.title", lang)}</h1>
            <p className="text-sm text-muted-foreground mt-1">{t("library.subtitle", lang)}</p>
          </div>
          <Button onClick={() => setIsCreateDialogOpen(true)}><Plus className="w-4 h-4 mr-2" />{t("library.create_album", lang)}</Button>
        </div>

        <Tabs defaultValue="albums" className="w-full">
          <TabsList className="mb-4">
            <TabsTrigger value="albums">{t("library.albums", lang)}</TabsTrigger>
            <TabsTrigger value="all">{t("library.all_audio", lang)}</TabsTrigger>
          </TabsList>

          <TabsContent value="albums" className="space-y-4">
            {isLoadingAlbums ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[...Array(6)].map((_, i) => (<div key={i} className="h-32 rounded-lg bg-muted animate-pulse" />))}
              </div>
            ) : albums.length === 0 ? (
              <div className="text-center py-12">
                <Folder className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground">{t("library.no_albums", lang)}</p>
                <Button variant="outline" className="mt-4" onClick={() => setIsCreateDialogOpen(true)}><Plus className="w-4 h-4 mr-2" />{t("library.create_album", lang)}</Button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className={`rounded-lg border p-4 cursor-pointer transition-colors ${selectedAlbum === null ? "border-primary bg-primary/5" : "border-border hover:border-primary/40"}`} onClick={() => setSelectedAlbum(null)}>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center"><Library className="w-6 h-6 text-primary" /></div>
                      <div><h3 className="font-medium">{t("library.all_audio", lang)}</h3><p className="text-sm text-muted-foreground">{audioFiles.length} {t("common.voices", lang)}</p></div>
                    </div>
                  </div>
                </div>
                {albums.map((album) => (
                  <div key={album.id} className={`rounded-lg border p-4 cursor-pointer transition-colors ${selectedAlbum === album.id ? "border-primary bg-primary/5" : "border-border hover:border-primary/40"}`} onClick={() => setSelectedAlbum(album.id)}>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">{selectedAlbum === album.id ? <FolderOpen className="w-6 h-6 text-primary" /> : <Folder className="w-6 h-6 text-muted-foreground" />}</div>
                        <div className="min-w-0"><h3 className="font-medium truncate">{album.name}</h3><p className="text-sm text-muted-foreground">{album.audio_count} {t("common.voices", lang)}</p></div>
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="w-8 h-8" onClick={(e) => e.stopPropagation()}><MoreVertical className="w-4 h-4" /></Button></DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => openEditDialog(album)}><Edit2 className="w-4 h-4 mr-2" />{t("library.edit_album", lang)}</DropdownMenuItem>
                          <DropdownMenuItem onClick={() => openDeleteDialog(album)} className="text-destructive"><Trash2 className="w-4 h-4 mr-2" />{t("library.delete_album", lang)}</DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                    {album.description && (<p className="text-sm text-muted-foreground mt-2 line-clamp-2">{album.description}</p>)}
                  </div>
                ))}
              </div>
            )}

            <div className="mt-6">
              <h3 className="text-sm font-medium mb-3">{selectedAlbum === null ? t("library.all_audio", lang) : albums.find((a) => a.id === selectedAlbum)?.name}</h3>
              {isLoadingAudio ? (<div className="space-y-2">{[...Array(5)].map((_, i) => (<div key={i} className="h-16 rounded-lg bg-muted animate-pulse" />))}</div>) : audioFiles.length === 0 ? (
                <div className="text-center py-8 border border-dashed rounded-lg"><Music className="w-8 h-8 mx-auto text-muted-foreground mb-2" /><p className="text-sm text-muted-foreground">{t("library.no_audio", lang)}</p></div>
              ) : (
                <div className="space-y-2">
                  {audioFiles.map((audio) => (
                    <div key={audio.id} className="flex items-center gap-3 p-3 rounded-lg border border-border hover:bg-muted/40 transition-colors">
                      <Button variant="ghost" size="icon" className="w-8 h-8 shrink-0" onClick={() => handlePlay(audio)}>
                        {playingAudio === audio.id ? (<div className="flex items-end gap-0.5 h-3">{[1,2,3].map((i) => (<div key={i} className="w-0.5 bg-primary rounded-full" style={{ height: 6, animation: "wave 0.5s ease-in-out infinite", animationDelay: `${(i-1)*0.1}s` }} />))}</div>) : (<Play className="w-4 h-4" />)}
                      </Button>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">{audio.title}</p>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground"><Clock className="w-3 h-3" /><span>{formatDuration(audio.duration_ms)}</span><span>·</span><span>{audio.segment_count} {t("library.segments", lang)}</span><span>·</span><span>{formatDate(audio.created_at)}</span></div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" className="w-8 h-8" onClick={() => handleDownload(audio)}><Download className="w-4 h-4" /></Button>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="w-8 h-8"><MoreVertical className="w-4 h-4" /></Button></DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => openRenameDialog(audio)}><Edit2 className="w-4 h-4 mr-2" />Rename</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openMoveDialog(audio)}><Move className="w-4 h-4 mr-2" />{t("library.move_to_album", lang)}</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => deleteAudioMutation.mutate(audio.id)} className="text-destructive"><Trash2 className="w-4 h-4 mr-2" />{t("library.delete_audio", lang)}</DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="all">
            {isLoadingAudio ? (<div className="space-y-2">{[...Array(5)].map((_, i) => (<div key={i} className="h-16 rounded-lg bg-muted animate-pulse" />))}</div>) : audioFiles.length === 0 ? (
              <div className="text-center py-12"><FileAudio className="w-12 h-12 mx-auto text-muted-foreground mb-4" /><p className="text-muted-foreground">{t("library.no_audio", lang)}</p></div>
            ) : (
              <div className="space-y-2">
                {audioFiles.map((audio) => (
                  <div key={audio.id} className="flex items-center gap-3 p-3 rounded-lg border border-border hover:bg-muted/40 transition-colors">
                    <Button variant="ghost" size="icon" className="w-8 h-8 shrink-0" onClick={() => handlePlay(audio)}>
                      {playingAudio === audio.id ? (<div className="flex items-end gap-0.5 h-3">{[1,2,3].map((i) => (<div key={i} className="w-0.5 bg-primary rounded-full" style={{ height: 6, animation: "wave 0.5s ease-in-out infinite", animationDelay: `${(i-1)*0.1}s` }} />))}</div>) : (<Play className="w-4 h-4" />)}
                    </Button>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">{audio.title}</p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground"><Clock className="w-3 h-3" /><span>{formatDuration(audio.duration_ms)}</span><span>·</span><span>{audio.segment_count} {t("library.segments", lang)}</span><span>·</span><span>{formatDate(audio.created_at)}</span>{audio.album_id && (<><span>·</span><span className="text-primary">{albums.find((a) => a.id === audio.album_id)?.name}</span></>)}</div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="icon" className="w-8 h-8" onClick={() => handleDownload(audio)}><Download className="w-4 h-4" /></Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="w-8 h-8"><MoreVertical className="w-4 h-4" /></Button></DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => openRenameDialog(audio)}><Edit2 className="w-4 h-4 mr-2" />Rename</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openMoveDialog(audio)}><Move className="w-4 h-4 mr-2" />{t("library.move_to_album", lang)}</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => deleteAudioMutation.mutate(audio.id)} className="text-destructive"><Trash2 className="w-4 h-4 mr-2" />{t("library.delete_audio", lang)}</DropdownMenuItem>
                          </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>

        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogContent>
            <DialogHeader><DialogTitle>{t("library.create_album", lang)}</DialogTitle></DialogHeader>
            <div className="space-y-4 py-4">
              <div><label className="text-sm font-medium">{t("library.album_name", lang)}</label><Input value={newAlbumName} onChange={(e) => setNewAlbumName(e.target.value)} placeholder="My Audiobook Collection" className="mt-1" /></div>
              <div><label className="text-sm font-medium">{t("library.album_description", lang)}</label><Input value={newAlbumDescription} onChange={(e) => setNewAlbumDescription(e.target.value)} placeholder="Optional description" className="mt-1" /></div>
            </div>
            <DialogFooter><Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>{t("library.cancel", lang)}</Button><Button onClick={handleCreateAlbum} disabled={!newAlbumName.trim()}>{t("library.save", lang)}</Button></DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
          <DialogContent>
            <DialogHeader><DialogTitle>{t("library.edit_album", lang)}</DialogTitle></DialogHeader>
            <div className="space-y-4 py-4">
              <div><label className="text-sm font-medium">{t("library.album_name", lang)}</label><Input value={newAlbumName} onChange={(e) => setNewAlbumName(e.target.value)} className="mt-1" /></div>
              <div><label className="text-sm font-medium">{t("library.album_description", lang)}</label><Input value={newAlbumDescription} onChange={(e) => setNewAlbumDescription(e.target.value)} className="mt-1" /></div>
            </div>
            <DialogFooter><Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>{t("library.cancel", lang)}</Button><Button onClick={handleUpdateAlbum} disabled={!newAlbumName.trim()}>{t("library.save", lang)}</Button></DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
          <DialogContent>
            <DialogHeader><DialogTitle>{t("library.delete_album", lang)}</DialogTitle><DialogDescription>{t("library.confirm_delete", lang)}</DialogDescription></DialogHeader>
            <DialogFooter><Button variant="outline" onClick={() => setIsDeleteDialogOpen(false)}>{t("library.cancel", lang)}</Button><Button variant="destructive" onClick={() => deleteAlbumMutation.mutate()}>{t("library.delete_album", lang)}</Button></DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={isMoveDialogOpen} onOpenChange={setIsMoveDialogOpen}>
          <DialogContent>
            <DialogHeader><DialogTitle>{t("library.move_to_album", lang)}</DialogTitle></DialogHeader>
            <div className="py-4">
              <Select value={targetAlbumId} onValueChange={setTargetAlbumId}>
                <SelectTrigger><SelectValue placeholder={t("library.select_album", lang)} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">{t("library.no_albums", lang)} (None)</SelectItem>
                  {albums.map((album) => (<SelectItem key={album.id} value={album.id}>{album.name}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
            <DialogFooter><Button variant="outline" onClick={() => setIsMoveDialogOpen(false)}>{t("library.cancel", lang)}</Button><Button onClick={() => moveAudioMutation.mutate()}>{t("library.save", lang)}</Button></DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={isRenameDialogOpen} onOpenChange={setIsRenameDialogOpen}>
          <DialogContent>
            <DialogHeader><DialogTitle>Rename Audio</DialogTitle></DialogHeader>
            <div className="py-4">
              <div><label className="text-sm font-medium">New Title</label><Input value={newAudioTitle} onChange={(e) => setNewAudioTitle(e.target.value)} placeholder="Enter new title" className="mt-1" /></div>
            </div>
            <DialogFooter><Button variant="outline" onClick={() => setIsRenameDialogOpen(false)}>{t("library.cancel", lang)}</Button><Button onClick={() => updateAudioMutation.mutate()} disabled={!newAudioTitle.trim()}>{t("library.save", lang)}</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
