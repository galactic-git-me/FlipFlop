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
        { name: "Shop", url: local ? "http://localhost:4313" : "https://www.theflipflop.shop", icon: Globe },
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
      <div className="grid grid-cols-4 divide-x divide-cyan-300/15">
        {BASE_SERVICES.map((service) => {
          const count = misses[service.name];
          const color = count == null ? "text-amber-300 animate-pulse" : count === 0 ? "text-emerald-400" : count === 1 ? "text-amber-300" : "text-rose-400";
          const Icon = service.icon;
          const state = count == null ? "checking" : count === 0 ? "online" : `${count} missed`;
          return <div key={service.name} className="flex flex-col items-center justify-center gap-0.5 px-1 py-1 text-[9px] font-semibold text-slate-300" title={`${service.name}: ${state}`}><Icon className={`h-6 w-6 ${color}`} />{service.name}</div>;
        })}
      </div>
    </section>
  );
}
