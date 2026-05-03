"use client";

import { useEffect, useState } from "react";
import { WifiOff, RefreshCw, X } from "lucide-react";

export function BackendStatus() {
  const [offline, setOffline] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [checking, setChecking] = useState(false);

  const check = async () => {
    setChecking(true);
    const url = (process.env.NEXT_PUBLIC_API_URL ?? "http://prometheus:8088/api").replace(/\/api$/, "");
    try {
      const res = await fetch(`${url}/health`, { signal: AbortSignal.timeout(3000) });
      setOffline(!res.ok);
      if (res.ok) setDismissed(false);
    } catch {
      setOffline(true);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    check();
    const interval = setInterval(check, 30_000);
    return () => clearInterval(interval);
  }, []);

  if (!offline || dismissed) return null;

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-3 rounded-xl bg-red-900/90 border border-red-500/40 backdrop-blur-sm shadow-2xl text-sm">
      <WifiOff className="w-4 h-4 text-red-400 flex-shrink-0" />
      <div>
        <span className="font-semibold text-red-300">Backend offline</span>
        <span className="text-red-400/80 ml-2">— start the API server on port 8088</span>
      </div>
      <button
        onClick={check}
        disabled={checking}
        className="ml-2 px-2 py-1 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-300 text-xs font-medium transition-colors disabled:opacity-50"
      >
        <RefreshCw className={`w-3 h-3 inline ${checking ? "animate-spin" : ""}`} />
        {checking ? "" : " Retry"}
      </button>
      <button onClick={() => setDismissed(true)} className="text-red-500/60 hover:text-red-400 ml-1">
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
