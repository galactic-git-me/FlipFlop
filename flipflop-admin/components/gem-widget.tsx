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
  const [currentGem, setCurrentGem] = useState<GemData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchGems = async () => {
    try {
      const response = await fetch("/api/gem-radar/current-gem", { cache: "no-store" });
      if (response.ok) {
        const data = await response.json();
        setCurrentGem(data ?? null);
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
      {currentGem && (
        <a
          href={currentGem.url}
          target="_blank"
          rel="noopener noreferrer"
          className="block p-3 rounded bg-gradient-to-br from-amber-600/20 to-orange-600/20 border border-amber-500/30 hover:border-amber-500/60 transition group"
        >
          <div className="flex items-start gap-2">
            <Gem className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
            <GemThumbnail src={currentGem.image_url} alt={currentGem.title} />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-amber-300 uppercase tracking-wide">Best Available Gem</p>
              <p className="text-sm text-white truncate group-hover:underline">
                {currentGem.title.substring(0, 40)}...
              </p>
              <p className="text-lg font-bold text-amber-200 mt-1">£{currentGem.price.toFixed(2)}</p>
              <p className="text-xs text-slate-300 mt-1">{currentGem.condition}</p>
            </div>
            <ExternalLink className="w-3 h-3 text-slate-400 flex-shrink-0 opacity-0 group-hover:opacity-100 transition" />
          </div>
        </a>
      )}

      {!loading && !currentGem && (
        <p className="text-xs text-slate-400 text-center py-2">No available gems in the current snapshot</p>
      )}
    </div>
  );
}
