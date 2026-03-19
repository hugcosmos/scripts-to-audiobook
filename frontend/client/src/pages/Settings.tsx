import { useState, useEffect } from "react";
import { useApp } from "@/App";
import { t } from "@/lib/i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchTTSProviders, fetchTTSCredentials, saveTTSCredentials, deleteTTSCredentials } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { Check, X, Key, Eye, EyeOff, Trash2, Save, ExternalLink, Folder, FolderOpen } from "lucide-react";
import { fetchSettings, updateSetting, migrateStorage, cleanupOldStorage } from "@/lib/api";

interface ProviderConfig {
  name: string;
  display_name: string;
  requires_auth: boolean;
  is_configured: boolean;
  fields: Array<{key: string; label: string; type: string; placeholder: string}>;
}

export default function SettingsPage() {
  const { lang } = useApp();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("tts");
  const [storagePath, setStoragePath] = useState("");
  const [newStoragePath, setNewStoragePath] = useState("");
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [formData, setFormData] = useState<Record<string, Record<string, string>>>({});
  const [migrationResult, setMigrationResult] = useState<{migrated: number; failed: number} | null>(null);
  const [isMigrating, setIsMigrating] = useState(false);

  const { data: providersData, isLoading } = useQuery({
    queryKey: ["/api/tts-providers"],
    queryFn: fetchTTSProviders,
  });

  const providers: ProviderConfig[] = providersData?.providers || [];

  // Load settings
  const { data: settingsData } = useQuery({
    queryKey: ["/api/library/settings"],
    queryFn: fetchSettings,
  });

  useEffect(() => {
    if (settingsData?.settings?.storage_path) {
      setStoragePath(settingsData.settings.storage_path);
      setNewStoragePath(settingsData.settings.storage_path);
    }
  }, [settingsData]);

  // Load credentials when provider is selected
  useEffect(() => {
    providers.forEach(async (provider) => {
      // Only fetch credentials for providers that require authentication
      if (provider.requires_auth && provider.is_configured) {
        try {
          const creds = await fetchTTSCredentials(provider.name);
          setFormData(prev => ({
            ...prev,
            [provider.name]: {
              api_key: creds.api_key_masked ? "••••••" : "",
              api_secret: creds.api_secret_masked ? "••••••" : "",
              app_id: creds.app_id || "",
            }
          }));
        } catch (e) {
          // Ignore error
        }
      }
    });
  }, [providers]);

  const saveMutation = useMutation({
    mutationFn: ({ provider, data }: { provider: string; data: any }) => 
      saveTTSCredentials(provider, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/tts-providers"] });
      toast({ title: t("common.success", lang), description: "Credentials saved successfully" });
    },
    onError: () => {
      toast({ title: t("common.error", lang), description: "Failed to save credentials", variant: "destructive" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (provider: string) => deleteTTSCredentials(provider),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/tts-providers"] });
      toast({ title: t("common.success", lang), description: "Credentials removed" });
    },
  });

  const updateStoragePathMutation = useMutation({
    mutationFn: (path: string) => updateSetting("storage_path", path),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/library/settings"] });
      toast({ title: t("common.success", lang), description: "Storage path updated. Restart server to apply changes." });
    },
    onError: (error: any) => {
      toast({ title: t("common.error", lang), description: error.message || "Failed to update storage path", variant: "destructive" });
    },
  });

  const migrateMutation = useMutation({
    mutationFn: (newPath: string) => migrateStorage(newPath),
    onSuccess: (data) => {
      setMigrationResult({ migrated: data.migrated, failed: data.failed });
      // Update local state to reflect new path
      setStoragePath(data.new_path);
      setNewStoragePath(data.new_path);
      queryClient.invalidateQueries({ queryKey: ["/api/library/settings"] });
      queryClient.invalidateQueries({ queryKey: ["/api/library/audio-files"] });
      toast({ 
        title: t("common.success", lang), 
        description: `Migrated ${data.migrated} files${data.failed > 0 ? `, ${data.failed} failed` : ''}` 
      });
      setIsMigrating(false);
    },
    onError: (error: any) => {
      toast({ 
        title: t("common.error", lang), 
        description: error.message || "Migration failed", 
        variant: "destructive" 
      });
      setIsMigrating(false);
    },
  });

  const cleanupMutation = useMutation({
    mutationFn: (newPath: string) => cleanupOldStorage(newPath),
    onSuccess: () => {
      toast({ title: t("common.success", lang), description: "Old storage cleaned up" });
    },
    onError: (error: any) => {
      toast({ title: t("common.error", lang), description: error.message || "Cleanup failed", variant: "destructive" });
    },
  });

  const handleSave = (provider: string) => {
    const data = formData[provider] || {};
    // Don't save if values are masked (user didn't change)
    const cleanData: Record<string, string> = {};
    Object.entries(data).forEach(([key, value]) => {
      if (value && !value.includes("•")) {
        cleanData[key] = value;
      }
    });
    saveMutation.mutate({ provider, data: cleanData });
  };

  const handleInputChange = (provider: string, field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [provider]: {
        ...prev[provider],
        [field]: value
      }
    }));
  };

  const toggleShowSecret = (key: string) => {
    setShowSecrets(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const getProviderFields = (provider: string) => {
    switch (provider) {
      case "iflytek":
        return [
          { key: "app_id", label: "App ID", type: "text", placeholder: "Your iFlytek App ID" },
          { key: "api_key", label: "API Key", type: "password", placeholder: "Your iFlytek API Key" },
          { key: "api_secret", label: "API Secret", type: "password", placeholder: "Your iFlytek API Secret" },
        ];
      case "baidu":
        return [
          { key: "app_id", label: "App ID", type: "text", placeholder: "Your Baidu App ID" },
          { key: "api_key", label: "API Key", type: "password", placeholder: "Your Baidu API Key" },
          { key: "api_secret", label: "Secret Key", type: "password", placeholder: "Your Baidu Secret Key" },
        ];
      case "elevenlabs":
        return [
          { key: "api_key", label: "API Key", type: "password", placeholder: "Your ElevenLabs API Key" },
        ];
      default:
        return [];
    }
  };

  const getProviderDocs = (provider: string) => {
    switch (provider) {
      case "iflytek":
        return "https://www.xfyun.cn/services/online_tts";
      case "baidu":
        return "https://ai.baidu.com/tech/speech/tts";
      case "elevenlabs":
        return "https://elevenlabs.io/api";
      default:
        return null;
    }
  };

  return (
    <div className="h-full overflow-auto p-6">
      <div className="max-w-3xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-foreground">Settings</h1>
          <p className="text-sm text-muted-foreground mt-1">Configure TTS providers and application settings</p>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-4">
            <TabsTrigger value="tts">TTS Providers</TabsTrigger>
            <TabsTrigger value="storage">Storage</TabsTrigger>
            <TabsTrigger value="about">About</TabsTrigger>
          </TabsList>

          <TabsContent value="tts" className="space-y-4">
            {isLoading ? (
              <div className="space-y-4">
                {[1, 2, 3].map(i => (<div key={i} className="h-48 rounded-lg bg-muted animate-pulse" />))}
              </div>
            ) : (
              providers.filter(p => p.requires_auth).map(provider => {
                const fields = getProviderFields(provider.name);
                const docsUrl = getProviderDocs(provider.name);
                return (
                  <Card key={provider.name}>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div>
                          <CardTitle className="text-base">{provider.display_name}</CardTitle>
                          <CardDescription>
                            {provider.is_configured ? (
                              <span className="flex items-center gap-1 text-green-500">
                                <Check className="w-3 h-3" /> Configured
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 text-muted-foreground">
                                <X className="w-3 h-3" /> Not configured
                              </span>
                            )}
                          </CardDescription>
                        </div>
                        <Badge variant={provider.is_configured ? "default" : "secondary"}>
                          {provider.is_configured ? "Active" : "Inactive"}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {docsUrl && (
                        <a 
                          href={docsUrl} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-xs text-primary flex items-center gap-1 hover:underline"
                        >
                          <ExternalLink className="w-3 h-3" />
                          Get API credentials from {provider.display_name}
                        </a>
                      )}
                      
                      <div className="space-y-3">
                        {fields.map(field => (
                          <div key={field.key}>
                            <label className="text-xs font-medium mb-1.5 block">{field.label}</label>
                            <div className="relative">
                              <Input
                                type={showSecrets[`${provider.name}_${field.key}`] ? "text" : field.type}
                                placeholder={field.placeholder}
                                value={formData[provider.name]?.[field.key] || ""}
                                onChange={(e) => handleInputChange(provider.name, field.key, e.target.value)}
                                className="pr-10"
                              />
                              {field.type === "password" && (
                                <button
                                  type="button"
                                  onClick={() => toggleShowSecret(`${provider.name}_${field.key}`)}
                                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                >
                                  {showSecrets[`${provider.name}_${field.key}`] ? (
                                    <EyeOff className="w-4 h-4" />
                                  ) : (
                                    <Eye className="w-4 h-4" />
                                  )}
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>

                      <div className="flex gap-2">
                        <Button 
                          size="sm" 
                          onClick={() => handleSave(provider.name)}
                          disabled={saveMutation.isPending}
                        >
                          <Save className="w-4 h-4 mr-1.5" />
                          Save
                        </Button>
                        {provider.is_configured && (
                          <Button 
                            size="sm" 
                            variant="destructive"
                            onClick={() => deleteMutation.mutate(provider.name)}
                            disabled={deleteMutation.isPending}
                          >
                            <Trash2 className="w-4 h-4 mr-1.5" />
                            Remove
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })
            )}
          </TabsContent>

          <TabsContent value="storage" className="space-y-4">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Folder className="w-5 h-5 text-primary" />
                  <CardTitle className="text-base">Storage Path</CardTitle>
                </div>
                <CardDescription>
                  Configure where generated audiobooks and audio files are stored
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-xs font-medium mb-1.5 block">Current Storage Path</label>
                  <div className="flex items-center gap-2 p-3 rounded-md bg-muted text-sm font-mono break-all">
                    <FolderOpen className="w-4 h-4 shrink-0 text-muted-foreground" />
                    {storagePath || "Loading..."}
                  </div>
                </div>

                <div>
                  <label className="text-xs font-medium mb-1.5 block">New Storage Path</label>
                  <div className="flex gap-2">
                    <Input
                      value={newStoragePath}
                      onChange={(e) => setNewStoragePath(e.target.value)}
                      placeholder="/path/to/storage"
                      className="font-mono text-sm"
                    />
                    <Button 
                      size="sm"
                      onClick={() => updateStoragePathMutation.mutate(newStoragePath)}
                      disabled={updateStoragePathMutation.isPending || !newStoragePath || newStoragePath === storagePath}
                    >
                      <Save className="w-4 h-4 mr-1.5" />
                      Update
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Changing the storage path will migrate all existing audiobooks to the new location.
                  </p>
                </div>

                {newStoragePath && newStoragePath !== storagePath && (
                  <div className="p-4 rounded-md bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 space-y-3">
                    <div className="flex items-start gap-2">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-amber-900 dark:text-amber-100">Migrate existing files?</p>
                        <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                          All audiobooks and their metadata will be copied to the new location and database will be updated.
                        </p>
                      </div>
                    </div>
                    
                    {migrationResult ? (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2 text-sm">
                          <Check className="w-4 h-4 text-green-500" />
                          <span>Migrated: {migrationResult.migrated} files</span>
                        </div>
                        {migrationResult.failed > 0 && (
                          <div className="flex items-center gap-2 text-sm text-destructive">
                            <X className="w-4 h-4" />
                            <span>Failed: {migrationResult.failed} files</span>
                          </div>
                        )}
                        <div className="flex gap-2 pt-2">
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => cleanupMutation.mutate(newStoragePath)}
                            disabled={cleanupMutation.isPending}
                          >
                            <Trash2 className="w-4 h-4 mr-1.5" />
                            Clean up old files
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => {
                              setMigrationResult(null);
                              setNewStoragePath(storagePath);
                            }}
                          >
                            Done
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <Button 
                        size="sm"
                        onClick={() => {
                          setIsMigrating(true);
                          migrateMutation.mutate(newStoragePath);
                        }}
                        disabled={isMigrating}
                      >
                        {isMigrating ? (
                          <>
                            <div className="w-4 h-4 mr-1.5 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent" />
                            Migrating...
                          </>
                        ) : (
                          <>
                            <Save className="w-4 h-4 mr-1.5" />
                            Migrate Files
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="about">
            <Card>
              <CardHeader>
                <CardTitle>Scripts to Audiobook</CardTitle>
                <CardDescription>Version 1.0.0</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-sm text-muted-foreground">
                <p>
                  A multi-voice audiobook generation tool that supports multiple TTS providers.
                </p>
                <div>
                  <p className="font-medium text-foreground mb-2">Supported TTS Providers:</p>
                  <ul className="list-disc list-inside space-y-1">
                    <li>Edge TTS (Free, built-in)</li>
                    <li>iFlytek 科大讯飞 (Requires API key)</li>
                    <li>Baidu 百度语音 (Requires API key)</li>
                    <li>ElevenLabs (Requires API key)</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
