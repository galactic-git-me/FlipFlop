"use client";

import { useEffect, useMemo, useState } from "react";
import { api, AntiBotPreflightStatus } from "@/lib/api";

export function AntiBotPreflightBanner() {
  const [status, setStatus] = useState<AntiBotPreflightStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastOpenedAt, setLastOpenedAt] = useState<Date | null>(null);

  const load = async () => {
    try {
      const s = await api.preflight.antibotStatus();
      setStatus(s);
    } catch {
      setStatus(null);
    }
  };

  useEffect(() => {
    const first = setTimeout(() => {
      void load();
    }, 0);
    const id = setInterval(() => {
      void load();
    }, 10000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, []);

  const challengeUrls = useMemo(() => {
    const urls = status?.urls || [];
    return urls.filter((u) => typeof u === "string" && u.startsWith("http"));
  }, [status]);

  const openTabs = () => {
    setBusy(true);
    try {
      for (const url of challengeUrls) {
        window.open(url, "_blank", "noopener,noreferrer");
      }
      setLastOpenedAt(new Date());
    } finally {
      setTimeout(() => setBusy(false), 300);
    }
  };

  if (!status || status.last_result === "success") return null;

  return (
    <div className="rounded-xl border px-3 py-2 text-sm bg-amber-500/10 border-amber-400/40 text-amber-200">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="font-semibold">Marketplace Challenges</div>
          <div className="opacity-90">
            Complete login/captcha challenges in browser tabs, then return here and rerun scan.
          </div>
          {lastOpenedAt && (
            <div className="opacity-75 mt-1 text-xs">
              Tabs opened: {lastOpenedAt.toLocaleTimeString()}
            </div>
          )}
        </div>
        <button
          className="px-3 py-1.5 rounded-md border border-white/25 hover:border-white/50 disabled:opacity-60"
          disabled={busy || challengeUrls.length === 0}
          onClick={openTabs}
          title={challengeUrls.length === 0 ? "No challenge URLs available" : "Open challenge tabs"}
        >
          {busy ? "Opening…" : "Open Challenge Tabs"}
        </button>
      </div>
    </div>
  );
}

