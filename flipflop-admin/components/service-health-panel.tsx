"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/api";
import { Database, Gauge, Gem, Globe } from "lucide-react";

type Service = { name: string; path?: string; url?: string; icon: typeof Gauge };

const BASE_SERVICES: Service[] = [
  { name: "API", path: "/settings", icon: Gauge },
  { name: "DB", path: "/settings", icon: Database },
  { name: "Gem", path: "/gem-radar/health", icon: Gem },
  { name: "Shop", url: "http://localhost:4313", icon: Globe },
];

export function ServiceHealthPanel() {
  const [misses, setMisses] = useState<Record<string, number>>({});
  // LIVE runs the admin UI on localhost while it talks to production. Use the
  // selected runtime mode rather than the browser hostname to choose links.
  const liveOperator = process.env.NEXT_PUBLIC_FLIPFLOP_ENV === "live";
  // Keep the first render identical on the server and client. The browser
  // hostname is only available after hydration, so resolve local links in the
  // existing effect and update them afterwards.
  const [isLocalhost, setIsLocalhost] = useState(process.env.NEXT_PUBLIC_FLIPFLOP_ENV === "development");
  const missesRef = useRef<Record<string, number>>({});

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      const local = !liveOperator && ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
      setIsLocalhost(local);
      const services: Service[] = [
        ...BASE_SERVICES.slice(0, 3),
        { name: "Shop", url: local ? "http://localhost:4313" : "https://www.theflipflop.shop", icon: Globe },
      ];
      await Promise.all(services.map(async (service) => {
        let status: number;
        try {
          const target = service.url ?? `${API_BASE_URL}${service.path}`;
          const response = await fetch(target, {
            cache: "no-store",
            mode: service.name === "Shop" ? "no-cors" : "cors",
            signal: AbortSignal.timeout(4000),
          });
          // The storefront is cross-origin and may return an opaque response;
          // a completed network request still proves that it is reachable.
          status = response.ok || response.type === "opaque" ? 0 : (missesRef.current[service.name] ?? 0) + 1;
        } catch {
          status = (missesRef.current[service.name] ?? 0) + 1;
        }
        missesRef.current[service.name] = status;
        if (mounted) setMisses((current) => ({ ...current, [service.name]: status }));
      }));
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
          const color = count == null ? "text-slate-100" : count === 0 ? "text-emerald-400" : count === 1 ? "text-amber-300" : "text-rose-400";
          const Icon = service.icon;
          const state = count == null ? "checking" : count === 0 ? "online" : `${count} missed`;
          const className = "flex flex-col items-center justify-center gap-0.5 px-1 py-1 text-[9px] font-semibold text-slate-300";
          const content = <><Icon className={`h-6 w-6 ${color}`} />{service.name}</>;
          return service.name === "Shop" ? (
            <a key={service.name} href={isLocalhost ? "http://localhost:4313" : "https://www.theflipflop.shop"} target="_blank" rel="noreferrer" className={className} title={`${service.name}: ${state}`}>
              {content}
            </a>
          ) : (
            <div key={service.name} className={className} title={`${service.name}: ${state}`}>
              {content}
            </div>
          );
        })}
      </div>
    </section>
  );
}
