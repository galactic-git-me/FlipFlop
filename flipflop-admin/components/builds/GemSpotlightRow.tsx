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
      return <a key={category} href={gem.url} target="_blank" rel="noopener noreferrer" className="group relative block aspect-square min-w-0 overflow-hidden rounded-xl ring-1 ring-white/15 shadow-lg shadow-black/30">
        {gem.image_url ? <img src={gem.image_url} alt={gem.title} className="absolute inset-0 h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" onError={event => { event.currentTarget.style.display = "none"; }} /> : <div className="absolute inset-0 bg-slate-800" />}
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
