"use client";

import { useEffect, useState } from "react";
import { WifiOff, RefreshCw, X } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

export function BackendStatus() {
  const [offline, setOffline] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [checking, setChecking] = useState(false);

  const check = async () => {
    setChecking(true);
    try {
      const res = await fetch(`${API_BASE_URL}/health/live`, { signal: AbortSignal.timeout(4000), cache: "no-store" });
      const body = await res.json().catch(() => null) as { ok?: boolean } | null;
      if (!res.ok || body?.ok !== true) throw new Error(`API liveness returned ${res.status}`);
      setOffline(false);
      setDismissed(false);
    } catch {
      setOffline(true);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    // Delay the first check so the page settles before hitting the network.
    const boot = setTimeout(() => { void check(); }, 2000);
    const interval = setInterval(check, 30_000);
    return () => {
      clearTimeout(boot);
      clearInterval(interval);
    };
  }, []);

  return null;
}
