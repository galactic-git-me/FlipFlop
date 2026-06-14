"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState, useCallback } from "react";
import { Box, RefreshCw, ExternalLink } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SourceBadge } from "@/components/source-badge";
import { EmptyState } from "@/components/empty-state";
import { Part } from "@/lib/types";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

const THEME_ICONS: Record<string, string> = {
  "Star Trek": "🖖",
  "Borg": "🤖",
  "Star Wars": "⚔️",
  "Battlestar Galactica": "🚀",
  "Cyberpunk": "⚡",
  "Alien/Xenomorph": "👾",
  "Space": "🌌",
  "Futuristic": "🔮",
  "Dune": "🏜️",
  "Halo": "🛡️",
  "Mass Effect": "🪐",
  "General Themed": "✨",
};

const SOURCES = ["All", "eBay", "Amazon", "AliExpress", "Temu", "Scan", "Overclockers", "Box", "Etsy"];

export default function CasesPage() {
  const [cases, setCases] = useState<Part[]>([]);
  const [themes, setThemes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTheme, setActiveTheme] = useState<string | null>(null);
  const [activeSource, setActiveSource] = useState("All");
  const [maxPrice, setMaxPrice] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (activeTheme) params.theme = activeTheme;
      if (activeSource !== "All") params.source_site = activeSource;
      if (maxPrice) params.max_price = maxPrice.toString();

      const [casesData, themesData] = await Promise.all([
        api.parts.cases(params) as Promise<Part[]>,
        api.parts.themes() as Promise<string[]>,
      ]);
      setCases(casesData);
      setThemes(themesData);
    } catch {
      setCases([]);
    } finally {
      setLoading(false);
    }
  }, [activeTheme, activeSource, maxPrice]);

  useEffect(() => {
    const id = setTimeout(() => { void load(); }, 0);
    return () => clearTimeout(id);
  }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    try { await api.swarms.trigger("cases"); await load(); } catch { } finally { setRefreshing(false); }
  };

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Box className="w-5 h-5 text-purple-400" /> Cases Catalogue
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Sci-fi & themed cases · new only · {cases.length} found · eBay · Amazon · AliExpress · Temu · Scan · Overclockers · Box · Etsy
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={refresh} disabled={refreshing}>
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Scanning…" : "Refresh Cases"}
        </Button>
      </div>

      {/* Filters row */}
      <div className="flex flex-wrap gap-4 items-start">
        {/* Theme filter */}
        {themes.length > 0 && (
          <div>
            <div className="text-[10px] text-slate-600 uppercase tracking-wider mb-1.5 font-semibold">Theme</div>
            <div className="flex flex-wrap gap-1.5">
              <button
                onClick={() => setActiveTheme(null)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all ${
                  !activeTheme ? "bg-purple-400/10 text-purple-400 border-purple-400/30" : "text-slate-500 border-[#1e2d45] hover:border-slate-600"
                }`}
              >
                ✨ All themes
              </button>
              {themes.map(theme => (
                <button
                  key={theme}
                  onClick={() => setActiveTheme(activeTheme === theme ? null : theme)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all ${
                    activeTheme === theme ? "bg-purple-400/10 text-purple-400 border-purple-400/30" : "text-slate-500 border-[#1e2d45] hover:border-slate-600"
                  }`}
                >
                  {THEME_ICONS[theme] ?? "🎨"} {theme}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Source filter */}
        <div>
          <div className="text-[10px] text-slate-600 uppercase tracking-wider mb-1.5 font-semibold">Source</div>
          <div className="flex gap-1.5">
            {SOURCES.map(src => (
              <button
                key={src}
                onClick={() => setActiveSource(src)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all ${
                  activeSource === src ? "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/30" : "text-slate-500 border-[#1e2d45] hover:border-slate-600"
                }`}
              >
                {src}
              </button>
            ))}
          </div>
        </div>

        {/* Price cap */}
        <div>
          <div className="text-[10px] text-slate-600 uppercase tracking-wider mb-1.5 font-semibold">Max Price</div>
          <div className="flex gap-1.5">
            {[null, 30, 50, 80, 150].map(p => (
              <button
                key={p ?? "any"}
                onClick={() => setMaxPrice(p)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all ${
                  maxPrice === p ? "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/30" : "text-slate-500 border-[#1e2d45] hover:border-slate-600"
                }`}
              >
                {p ? `£${p}` : "Any"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-500 text-sm gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" /> Loading cases…
        </div>
      ) : cases.length === 0 ? (
        <EmptyState
          icon={Box}
          title="No themed cases yet"
          description='Click "Refresh Cases" to scan eBay, Amazon and AliExpress for sci-fi and themed PC cases (Star Trek, Star Wars, Cyberpunk, etc.).'
          action={{ label: "Scan for Cases", onClick: refresh }}
        />
      ) : activeTheme ? (
        // Filtered by theme — flat grid
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {cases.map(c => (
            <CaseCard key={c.id} item={c} />
          ))}
        </div>
      ) : (
        // No theme filter — grouped by theme with section headers
        <GroupedCasesView cases={cases} onThemeClick={setActiveTheme} />
      )}
    </div>
  );
}

function GroupedCasesView({ cases, onThemeClick }: { cases: Part[]; onThemeClick: (theme: string) => void }) {
  // Group cases by theme
  const grouped = cases.reduce<Record<string, Part[]>>((acc, c) => {
    const theme = c.theme ?? "Other";
    if (!acc[theme]) acc[theme] = [];
    acc[theme].push(c);
    return acc;
  }, {});

  const themes = Object.keys(grouped).sort();

  return (
    <div className="space-y-8">
      {themes.map(theme => {
        const icon = THEME_ICONS[theme] ?? "🎨";
        const items = grouped[theme];
        return (
          <div key={theme}>
            <div className="flex items-center gap-2 mb-3">
              <button
                onClick={() => onThemeClick(theme)}
                className="flex items-center gap-2 text-sm font-semibold text-purple-300 hover:text-purple-200 transition-colors"
              >
                <span>{icon}</span>
                <span>{theme}</span>
              </button>
              <span className="text-xs text-slate-600">· {items.length} item{items.length !== 1 ? "s" : ""}</span>
              <div className="flex-1 h-px bg-[#1e2d45]" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {items.map(c => (
                <CaseCard key={c.id} item={c} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CaseCard({ item }: { item: Part }) {
  const price = item.price_new ?? item.price ?? 0;
  const themeIcon = THEME_ICONS[item.theme ?? ""] ?? "🎨";

  return (
    <div className="relative rounded-xl border border-[#1e2d45] overflow-hidden h-72 flex flex-col group hover:border-[#2a3f5a] transition-colors">
      {/* Full-card background image */}
      {item.image_url ? (
        <img src={item.image_url} alt="" className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
      ) : (
        <div className="absolute inset-0 bg-gradient-to-br from-[#0a1119] to-[#0d1320] flex items-center justify-center opacity-30">
          <Box className="w-16 h-16 text-slate-700" />
        </div>
      )}

      {/* Gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/97 via-black/50 to-black/15" />

      {/* Content */}
      <div className="relative z-10 flex flex-col h-full p-3">

        {/* Top badges */}
        <div className="flex items-start justify-between">
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-black/70 backdrop-blur-sm border border-purple-400/30 text-xs font-semibold text-purple-300">
            {themeIcon} {item.theme ?? "Themed"}
          </span>
          <span className="inline-flex items-center px-1.5 py-0.5 rounded-md bg-[#00dc82] text-[#080c14] text-[10px] font-black uppercase">NEW</span>
        </div>

        {/* Bottom: name + specs + price + action */}
        <div className="mt-auto space-y-2">
          <h3 className="text-sm font-semibold text-white leading-snug line-clamp-2 drop-shadow-[0_1px_3px_rgba(0,0,0,0.9)]">{item.name}</h3>

          {item.specs && (
            <p className="text-xs text-white/50 font-mono line-clamp-1">{item.specs}</p>
          )}

          <div className="flex items-end justify-between gap-2">
            <div>
              <SourceBadge sourceName={item.source_site ?? "Unknown"} url={item.source_url} />
              {item.last_price_update && (
                <div className="text-[9px] text-white/35 mt-0.5">
                  Updated {new Date(item.last_price_update).toLocaleDateString("en-GB")}
                </div>
              )}
            </div>
            <div className="bg-black/70 backdrop-blur-sm border border-[#1e2d45] rounded-lg px-2.5 py-1 flex-shrink-0">
              <span className="text-xl font-black text-white">{formatCurrency(price)}</span>
            </div>
          </div>

          <a href={item.source_url ?? "#"} target="_blank" rel="noopener noreferrer">
            <Button variant="primary" size="sm" className="w-full justify-center">
              <ExternalLink className="w-3.5 h-3.5" /> View on {item.source_site ?? "Store"}
            </Button>
          </a>
        </div>
      </div>
    </div>
  );
}
