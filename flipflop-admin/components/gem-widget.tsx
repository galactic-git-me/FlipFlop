"use client";

import { useEffect, useState } from "react";
import { Gem, ExternalLink } from "lucide-react";

interface GemData {
  title: string;
  price: number;
  seller?: string;
  condition: string;
  url: string;
  image_url?: string | null;
}

// eslint-disable-next-line @next/next/no-img-element -- external eBay-hosted
// thumbnails; next/image's domain allowlist isn't worth configuring for a
// scraper whose image hosts vary listing to listing.
function GemThumbnail({ src, alt }: { src?: string | null; alt: string }) {
  if (!src) return null;
  return (
    <img
      src={src}
      alt={alt}
      width={40}
      height={40}
      className="rounded object-cover shrink-0 bg-slate-700"
      style={{ width: 40, height: 40 }}
      onError={(e) => {
        (e.target as HTMLImageElement).style.display = "none";
      }}
    />
  );
}

export function GemWidget() {
  const [gemOfDay, setGemOfDay] = useState<GemData | null>(null);
  const [gemOfWeek, setGemOfWeek] = useState<GemData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchGems = async () => {
    try {
      const [dayRes, weekRes] = await Promise.all([
        fetch("/api/gem-radar/gem-of-day"),
        fetch("/api/gem-radar/gem-of-week"),
      ]);

      if (dayRes.ok) {
        const data = await dayRes.json();
        if (data) setGemOfDay(data);
      }

      if (weekRes.ok) {
        const data = await weekRes.json();
        if (data) setGemOfWeek(data);
      }

      setLoading(false);
    } catch (error) {
      console.error("Error fetching gems:", error);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGems();
    const interval = setInterval(fetchGems, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="px-4 py-4 border-t border-slate-700 space-y-3">
      {/* Gem of the Day */}
      {gemOfDay && (
        <a
          href={gemOfDay.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block p-3 rounded bg-gradient-to-br from-amber-600/20 to-orange-600/20 border border-amber-500/30 hover:border-amber-500/60 transition group"
        >
          <div className="flex items-start gap-2">
            <Gem className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
            <GemThumbnail src={gemOfDay.image_url} alt={gemOfDay.title} />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-amber-300 uppercase tracking-wide">Gem of Day</p>
              <p className="text-sm text-white truncate group-hover:underline">
                {gemOfDay.title.substring(0, 40)}...
              </p>
              <p className="text-lg font-bold text-amber-200 mt-1">£{gemOfDay.price.toFixed(2)}</p>
              <p className="text-xs text-slate-300 mt-1">{gemOfDay.condition}</p>
            </div>
            <ExternalLink className="w-3 h-3 text-slate-400 flex-shrink-0 opacity-0 group-hover:opacity-100 transition" />
          </div>
        </a>
      )}

      {/* Gem of the Week */}
      {gemOfWeek && gemOfWeek.url !== gemOfDay?.url && (
        <a
          href={gemOfWeek.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block p-3 rounded bg-gradient-to-br from-blue-600/20 to-purple-600/20 border border-blue-500/30 hover:border-blue-500/60 transition group"
        >
          <div className="flex items-start gap-2">
            <Gem className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
            <GemThumbnail src={gemOfWeek.image_url} alt={gemOfWeek.title} />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-blue-300 uppercase tracking-wide">Gem of Week</p>
              <p className="text-sm text-white truncate group-hover:underline">
                {gemOfWeek.title.substring(0, 40)}...
              </p>
              <p className="text-lg font-bold text-blue-200 mt-1">£{gemOfWeek.price.toFixed(2)}</p>
              <p className="text-xs text-slate-300 mt-1">{gemOfWeek.condition}</p>
            </div>
            <ExternalLink className="w-3 h-3 text-slate-400 flex-shrink-0 opacity-0 group-hover:opacity-100 transition" />
          </div>
        </a>
      )}

      {!loading && !gemOfDay && !gemOfWeek && (
        <p className="text-xs text-slate-400 text-center py-2">No gems found yet</p>
      )}
    </div>
  );
}
