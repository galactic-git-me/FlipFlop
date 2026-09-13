"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/api";
import { Database, Gauge, Globe, Radar } from "lucide-react";

type Service = { name: string; path?: string; url?: string; icon: typeof Gauge };

const BASE_SERVICES: Service[] = [
  { name: "API", path: "/settings", icon: Gauge },
  { name: "DB", path: "/settings", icon: Database },
  { name: "Gem", path: "/gem-radar/health", icon: Radar },
  { name: "Shop", url: "http://localhost:4313", icon: Globe },
];

export function ServiceHealthPanel() {
  const [misses, setMisses] = useState<Record<string, number>>({});
  const missesRef = useRef<Record<string, number>>({});

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      const local = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
      const services: Service[] = [
        ...BASE_SERVICES.slice(0, 3),
        { name: "Storefront", url: local ? "http://localhost:4313" : "https://www.theflipflop.shop" },
      ];
      const next: Record<string, number> = {};
      await Promise.all(services.map(async (service) => {
        try {
          const target = service.url ?? `${API_BASE_URL}${service.path}`;
          const response = await fetch(target, { cache: "no-store", signal: AbortSignal.timeout(4000) });
          next[service.name] = response.ok ? 0 : (missesRef.current[service.name] ?? 0) + 1;
        } catch {
          next[service.name] = (missesRef.current[service.name] ?? 0) + 1;
        }
      }));
      if (mounted) { missesRef.current = next; setMisses(next); }
    };
    void check();
    const timer = setInterval(() => { void check(); }, 10000);
    return () => { mounted = false; clearInterval(timer); };
  }, []);

  return (
    <section className="mx-2 mt-auto rounded border border-cyan-300/15 bg-slate-950/55 px-2 py-1.5" aria-label="Service health">
      <div className="mb-1.5 flex items-center justify-between text-[8px] font-bold uppercase tracking-[0.16em] text-cyan-200/80">
        <span>System heartbeat</span><span className="animate-pulse text-cyan-300">●</span>
      </div>
      <div className="grid grid-cols-4 gap-1">
        {BASE_SERVICES.map((service) => {
          const count = misses[service.name];
          const color = count == null ? "bg-amber-300 animate-pulse" : count === 0 ? "bg-emerald-400" : count === 1 ? "bg-amber-300" : "bg-rose-400";
          const Icon = service.icon;
          const state = count == null ? "checking" : count === 0 ? "online" : `${count} missed`;
          return <div key={service.name} className="flex items-center justify-center gap-1 text-[9px] font-semibold text-slate-300" title={`${service.name}: ${state}`}><Icon className="h-3 w-3 text-slate-400" /><span className={`h-1.5 w-1.5 rounded-full ${color}`} />{service.name}</div>;
        })}
      </div>
    </section>
  );
}
