"use client";

import { useEffect, useState } from "react";
import { api, AntiBotPreflightStatus } from "@/lib/api";

export function AntiBotPreflightBanner() {
  const [status, setStatus] = useState<AntiBotPreflightStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null);
  const [checkError, setCheckError] = useState<string | null>(null);

  const load = async () => {
    try {
      const s = await api.preflight.antibotStatus();
      setStatus(s);
      setLastCheckedAt(new Date());
      setCheckError(null);
    } catch {
      setStatus(null);
      setCheckError("Check failed; retry.");
    }
  };

  useEffect(() => {
    const first = setTimeout(() => {
      void load();
    }, 0);
    const id = setInterval(() => {
      void load();
    }, 8000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, []);

  if (!status || status.last_result === "success") return null;

  const noGui = status.enabled && !status.interactive_mode;
  const tone = noGui ? "bg-amber-500/10 border-amber-400/40 text-amber-200" : "bg-cyan-500/10 border-cyan-400/40 text-cyan-200";

  return (
    <div className={`rounded-xl border px-3 py-2 text-sm ${tone}`}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="font-semibold">Anti-bot preflight</div>
          <div className="opacity-90">
            {noGui
              ? "No GUI display in backend runtime, so challenge windows cannot open automatically. Scraping continues in background."
              : `Status: ${status.last_result} — ${status.last_message}`}
          </div>
          {noGui && (
            <div className="opacity-90 mt-1">
              This banner is informational only and does not block dashboard loading.
            </div>
          )}
          {noGui && lastCheckedAt && (
            <div className="opacity-75 mt-1 text-xs">
              Last checked: {lastCheckedAt.toLocaleTimeString()}
            </div>
          )}
          {noGui && checkError && (
            <div className="opacity-90 mt-1 text-xs text-amber-100">
              {checkError}
            </div>
          )}
        </div>
        <button
          className="px-3 py-1.5 rounded-md border border-white/25 hover:border-white/50 disabled:opacity-60"
          disabled={busy || status.running}
          onClick={async () => {
            setBusy(true);
            try {
              if (noGui) {
                await Promise.race([
                  load(),
                  new Promise((resolve) => setTimeout(resolve, 2500)),
                ]);
              } else {
                await api.preflight.triggerAntibot();
                setTimeout(() => void load(), 1000);
              }
            } finally {
              setBusy(false);
            }
          }}
        >
          {noGui ? (busy ? "Checking…" : "Re-check Session") : (status.running || busy ? "Running…" : "Run Preflight")}
        </button>
      </div>
    </div>
  );
}
