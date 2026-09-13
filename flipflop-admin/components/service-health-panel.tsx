"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/api";

type Service = { name: string; path?: string; url?: string };
type State = "checking" | "online" | "offline";

const BASE_SERVICES: Service[] = [
  { name: "API", path: "/settings" },
  { name: "Database", path: "/settings" },
  { name: "Gem Radar", path: "/gem-radar/health" },
  { name: "Storefront", url: "http://localhost:4313" },
];

export function ServiceHealthPanel() {
  const [states, setStates] = useState<Record<string, State>>({});

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      const local = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
      const services: Service[] = [
        ...BASE_SERVICES.slice(0, 3),
        { name: "Storefront", url: local ? "http://localhost:4313" : "https://www.theflipflop.shop" },
      ];
      const next: Record<string, State> = {};
      await Promise.all(services.map(async (service) => {
        try {
          const target = service.url ?? `${API_BASE_URL}${service.path}`;
          const response = await fetch(target, { cache: "no-store", signal: AbortSignal.timeout(4000) });
          next[service.name] = response.ok ? "online" : "offline";
        } catch {
          next[service.name] = "offline";
        }
      }));
      if (mounted) setStates(next);
    };
    void check();
    const timer = setInterval(() => { void check(); }, 10000);
    return () => { mounted = false; clearInterval(timer); };
  }, []);

  return (
    <section className="mx-2 mt-auto rounded-md border border-cyan-300/15 bg-slate-950/55 px-2.5 py-2.5" aria-label="Service health">
      <div className="mb-2 flex items-center justify-between text-[9px] font-bold uppercase tracking-[0.18em] text-cyan-200/80">
        <span>System heartbeat</span><span className="animate-pulse text-cyan-300">●</span>
      </div>
      <div className="grid grid-cols-2 gap-x-2 gap-y-1.5">
        {BASE_SERVICES.map((service) => {
          const state = states[service.name] ?? "checking";
          const color = state === "online" ? "bg-emerald-400" : state === "offline" ? "bg-rose-400" : "bg-amber-300 animate-pulse";
          return <div key={service.name} className="flex items-center gap-1.5 text-[10px] text-slate-300" title={`${service.name}: ${state}`}><span className={`h-1.5 w-1.5 shrink-0 rounded-full ${color}`} />{service.name}</div>;
        })}
      </div>
    </section>
  );
}
