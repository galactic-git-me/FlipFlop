"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/api";
import { Database, Gauge, Gem, Globe } from "lucide-react";

type Service = { name: string; path?: string; url?: string; icon: typeof Gauge };
type ProbeStatus = {
  failures: number;
  lastCheckedAt: string;
  lastSuccessAt?: string;
  detail?: string;
};

const BASE_SERVICES: Service[] = [
  // Keep these probes independent: the API route is process liveness, the DB
  // route runs SELECT 1, and Gem reports its background queue worker pool.
  { name: "API", path: "/health/live", icon: Gauge },
  { name: "DB", path: "/health/database", icon: Database },
  { name: "Gem", path: "/api/gem-radar/health", icon: Gem },
  { name: "Shop", url: "http://localhost:4313/api/health", icon: Globe },
];

export function ServiceHealthPanel() {
  const [statuses, setStatuses] = useState<Record<string, ProbeStatus>>({});
  // LIVE runs the admin UI on localhost while it talks to production. Use the
  // selected runtime mode rather than the browser hostname to choose links.
  const liveOperator = process.env.NEXT_PUBLIC_FLIPFLOP_ENV === "live";
  // Keep the first render identical on the server and client. The browser
  // hostname is only available after hydration, so resolve local links in the
  // existing effect and update them afterwards.
  const [isLocalhost, setIsLocalhost] = useState(process.env.NEXT_PUBLIC_FLIPFLOP_ENV === "development");
  useEffect(() => {
    let mounted = true;
    const check = async () => {
      const local = !liveOperator && ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
      setIsLocalhost(local);
      const services: Service[] = [
        ...BASE_SERVICES.slice(0, 3),
        { name: "Shop", url: local ? "http://localhost:4313/api/health" : "https://www.theflipflop.shop/api/health", icon: Globe },
      ];
      await Promise.all(services.map(async (service) => {
        const checkedAt = new Date().toISOString();
        let healthy = false;
        let detail = "No response";
        try {
          const target = service.url ?? `${API_BASE_URL}${service.path}`;
          const response = await fetch(target, {
            cache: "no-store",
            mode: "cors",
            signal: AbortSignal.timeout(4000),
          });
          const body = await response.json().catch(() => null) as Record<string, unknown> | null;
          healthy = response.ok && body?.ok === true;
          detail = healthy
            ? service.name === "Gem"
              ? `${String(body?.online_workers ?? 0)}/${String(body?.expected_workers ?? 0)} workers`
              : String(body?.service ?? "heartbeat acknowledged")
            : `HTTP ${response.status}${typeof body?.detail === "string" ? `: ${body.detail}` : ""}`;
        } catch (error) {
          detail = error instanceof Error ? error.message : "Probe failed";
        }
        if (mounted) setStatuses((current) => ({
          ...current,
          [service.name]: {
            failures: healthy ? 0 : (current[service.name]?.failures ?? 0) + 1,
            lastCheckedAt: checkedAt,
            lastSuccessAt: healthy ? checkedAt : current[service.name]?.lastSuccessAt,
            detail,
          },
        }));
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
          const status = statuses[service.name];
          const color = !status ? "text-slate-100" : status.failures === 0 ? "text-emerald-400" : status.failures === 1 ? "text-amber-300" : "text-rose-400";
          const Icon = service.icon;
          const state = !status ? "checking" : status.failures === 0 ? "online" : `${status.failures} failed probe${status.failures === 1 ? "" : "s"}`;
          const checked = status ? new Date(status.lastCheckedAt).toLocaleTimeString() : "not checked yet";
          const tooltip = `${service.name}: ${state}${status ? ` · ${status.detail} · checked ${checked}${status.lastSuccessAt ? ` · last success ${new Date(status.lastSuccessAt).toLocaleTimeString()}` : ""}` : ""}`;
          const className = "flex flex-col items-center justify-center gap-0.5 px-1 py-1 text-[9px] font-semibold text-slate-300";
          const content = <><Icon className={`h-6 w-6 ${color} ${status?.failures === 0 ? "animate-pulse" : ""}`} />{service.name}</>;
          return service.name === "Shop" ? (
            <a key={service.name} href={isLocalhost ? "http://localhost:4313" : "https://www.theflipflop.shop"} target="_blank" rel="noreferrer" className={className} title={tooltip} aria-label={tooltip}>
              {content}
            </a>
          ) : (
            <div key={service.name} className={className} title={tooltip} aria-label={tooltip}>
              {content}
            </div>
          );
        })}
      </div>
    </section>
  );
}
