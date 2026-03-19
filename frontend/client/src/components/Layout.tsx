import { useLocation, Link } from "wouter";
import { useApp } from "@/App";
import { t } from "@/lib/i18n";
import { Moon, Sun, Globe, FileText, Mic2, PlaySquare, Library, Wand2, Album, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const navItems = [
  { path: "/", icon: FileText, keyEn: "nav.script" },
  { path: "/cast", icon: Mic2, keyEn: "nav.voices" },
  { path: "/generate", icon: Wand2, keyEn: "nav.generate" },
  { path: "/playback", icon: PlaySquare, keyEn: "nav.playback" },
  { path: "/catalog", icon: Library, keyEn: "nav.catalog" },
  { path: "/library", icon: Album, keyEn: "nav.library" },
  { path: "/settings", icon: Settings, keyEn: "nav.settings" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const [location] = useLocation();
  const { lang, setLang, isDark, setIsDark, characters, scriptLines, audioUrl } = useApp();

  const hasScript = scriptLines.length > 0;
  const hasCast = characters.length > 0;
  const hasAudio = !!audioUrl;

  function isActive(path: string) {
    const loc = location.replace(/^#/, "");
    if (path === "/") return loc === "/" || loc === "";
    return loc === path || loc.startsWith(path + "/");
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside className="w-16 lg:w-56 flex flex-col border-r border-border bg-sidebar shrink-0">
        {/* Logo */}
        <div className="flex items-center gap-3 px-3 py-4 border-b border-border bg-gradient-to-r from-sidebar to-sidebar">
          <div className="w-8 h-8 shrink-0">
            <svg viewBox="0 0 32 32" fill="none" aria-label="Scripts to Audiobook" className="w-8 h-8">
              <defs>
                <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="hsl(258 90% 66%)" />
                  <stop offset="100%" stopColor="hsl(190 90% 50%)" />
                </linearGradient>
              </defs>
              <rect width="32" height="32" rx="8" fill="url(#logoGradient)" />
              <path d="M8 9h10M8 13h8M8 17h10M8 21h6" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
              <circle cx="23" cy="21" r="5" fill="white" fillOpacity="0.9" />
              <path d="M21.5 19.5v3l2.5-1.5-2.5-1.5z" fill="hsl(258 90% 66%)"/>
            </svg>
          </div>
          <div className="hidden lg:block overflow-hidden">
            <p className="text-xs font-semibold leading-tight gradient-text truncate">
              {t("app.title", lang)}
            </p>
            <p className="text-[10px] text-muted-foreground truncate">Multi-voice Audiobook</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-2 space-y-1">
          {navItems.map(({ path, icon: Icon, keyEn }) => {
            const active = isActive(path);
            const disabled = 
              (path === "/cast" && !hasScript) ||
              (path === "/generate" && !hasCast) ||
              (path === "/playback" && !hasAudio);
            
            const className = `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
              active
                ? "bg-primary text-primary-foreground"
                : disabled
                ? "opacity-40 cursor-not-allowed text-muted-foreground"
                : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            }`;
            
            if (disabled) {
              return (
                <span
                  key={path}
                  data-testid={`nav-${path.replace("/", "") || "home"}`}
                  className={className}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span className="hidden lg:block truncate">{t(keyEn, lang)}</span>
                </span>
              );
            }
            
            return (
              <Link
                key={path}
                to={path}
                data-testid={`nav-${path.replace("/", "") || "home"}`}
                className={className}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="hidden lg:block truncate">{t(keyEn, lang)}</span>
              </Link>
            );
          })}
        </nav>

        {/* Bottom controls */}
        <div className="p-2 border-t border-border space-y-1">
          {/* Language toggle */}
          <button
            data-testid="lang-toggle"
            onClick={() => setLang(lang === "en" ? "zh" : "en")}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors"
          >
            <Globe className="w-4 h-4 shrink-0" />
            <span className="hidden lg:block">{lang === "en" ? "中文" : "English"}</span>
          </button>
          
          {/* Theme toggle */}
          <button
            data-testid="theme-toggle"
            onClick={() => setIsDark(!isDark)}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-sidebar-accent transition-colors"
          >
            {isDark ? <Sun className="w-4 h-4 shrink-0" /> : <Moon className="w-4 h-4 shrink-0" />}
            <span className="hidden lg:block">{isDark ? "Light" : "Dark"}</span>
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
