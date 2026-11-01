"use client";

import { useEffect, useState } from "react";

interface GemSpotlightItem {
  id: number;
  title: string;
  price: number;
  url: string;
  image_url?: string | null;
  cpu?: string | null;
  classification?: "GEM" | "SUPER_GEM";
}

type GemSpotlights = Record<string, GemSpotlightItem | null>;

const componentOrder = ["motherboard", "cpu", "cooler", "ram", "gpu", "ssd", "psu", "case"];
const labels: Record<string, string> = {
  motherboard: "Gem Motherboard", cpu: "Gem CPU", cooler: "Gem CPU Cooler", ram: "Gem RAM",
  gpu: "Gem GPU", ssd: "Gem SSD", psu: "Gem PSU", case: "Gem PC Case",
};
const accents: Record<string, string> = {
  motherboard: "text-emerald-300", cpu: "text-cyan-300", cooler: "text-sky-300", ram: "text-pink-300",
  gpu: "text-purple-300", ssd: "text-blue-300", psu: "text-orange-300", case: "text-amber-300",
};

function spotlightImageUrl(value: string) {
  try {
    const url = new URL(value);
    if (url.protocol !== "https:") return null;
    if (["www.scan.co.uk", "computerorbit.com", "www.computerorbit.com", "www.overclockers.co.uk", "i.ebayimg.com", "m.media-amazon.com", "images-eu.ssl-images-amazon.com", "images-na.ssl-images-amazon.com"].includes(url.hostname)) {
      return `/api/proxy-image?url=${encodeURIComponent(url.toString())}`;
    }
    return value;
  } catch {
    return null;
  }
}

export default function GemSpotlightRow() {
  const [gems, setGems] = useState<GemSpotlights | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const response = await fetch("/api/gem-radar/gem-by-component", { cache: "no-store", signal: AbortSignal.timeout(30_000) });
        if (response.ok && active) setGems(await response.json());
      } catch (error) {
        console.warn("Could not load Sourcing Gem cards:", error);
      }
    };
    void load();
    const interval = setInterval(load, 5 * 60_000);
    return () => { active = false; clearInterval(interval); };
  }, []);

  return <section aria-label="Top Gems by component" className="mb-5 mt-5 grid w-full min-w-0 grid-cols-8 gap-2">
    {componentOrder.map(category => {
      const gem = gems?.[category];
      if (!gem) return <div key={category} className="flex aspect-square min-w-0 flex-col justify-between rounded-xl border border-white/10 bg-white/[0.03] p-3">
        <span className={`truncate text-[10px] font-semibold uppercase tracking-wide ${accents[category]}`}>{labels[category]}</span>
        <p className="text-xs text-slate-500">No qualifying Gem</p>
      </div>;
      const imageSrc = gem.image_url ? spotlightImageUrl(gem.image_url) : null;
      return <a key={category} href={gem.url} target="_blank" rel="noopener noreferrer" className="group relative block aspect-square min-w-0 overflow-hidden rounded-xl ring-1 ring-white/15 shadow-lg shadow-black/30">
        {imageSrc ? <img src={imageSrc} alt={gem.title} className="absolute inset-0 h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" onError={event => { event.currentTarget.style.display = "none"; event.currentTarget.nextElementSibling?.classList.remove("hidden"); }} /> : null}
        <div className={`absolute inset-0 flex items-center justify-center bg-gradient-to-br from-slate-800 via-slate-900 to-indigo-950 ${imageSrc ? "hidden" : ""}`} aria-hidden="true"><span className="text-5xl font-black text-white/10">{labels[category].replace("Gem ", "").slice(0, 2).toUpperCase()}</span></div>
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/10 to-black/45" />
        <span className={`absolute left-2 top-2 max-w-[calc(100%-1rem)] truncate rounded-full bg-black/50 px-2 py-1 text-[9px] font-semibold uppercase tracking-wide ${accents[category]}`}>{labels[category]}</span>
        <div className="absolute inset-x-0 bottom-0 min-w-0 border-t border-white/10 bg-black/35 p-2 backdrop-blur-sm">
          <p className="truncate text-xs font-medium text-white">{gem.title}</p>
          {gem.cpu && <p className="truncate text-[10px] text-white/70">{gem.cpu}</p>}
          <p className="mt-0.5 text-base font-bold text-emerald-200">£{gem.price.toFixed(2)}</p>
        </div>
      </a>;
    })}
  </section>;
}
