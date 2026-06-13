"use client";

import { useCallback, useEffect, useState } from "react";
import {
  MemoryStick,
  Bell,
  BellOff,
  RefreshCw,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Clock,
  Zap,
  Smartphone,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Deal {
  id: number;
  source: string;
  message: string;
  acked: boolean;
  acked_at: string | null;
  created_at: string;
}

interface Config {
  threshold_gbp: number;
  ntfy_topic: string;
  enabled: boolean;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtRelative(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

function extractUrl(message: string): string | null {
  const m = message.match(/https?:\/\/\S+/);
  return m ? m[0] : null;
}

function extractPrice(message: string): string | null {
  const m = message.match(/£([\d.]+)/);
  return m ? `£${parseFloat(m[1]).toFixed(2)}` : null;
}

function extractTitle(message: string): string {
  // "Title — £XX.XX (threshold …) | URL"
  return message.split(" — £")[0].split(" | ")[0].trim();
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatChip({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-white/10 bg-white/5 p-4">
      <span className="text-[11px] uppercase tracking-widest text-white/40">{label}</span>
      <span className={`text-2xl font-bold ${accent ? "text-emerald-400" : "text-white"}`}>
        {value}
      </span>
    </div>
  );
}

function DealRow({ deal }: { deal: Deal }) {
  const url = extractUrl(deal.message);
  const price = extractPrice(deal.message);
  const title = extractTitle(deal.message);

  return (
    <div className="group flex items-start gap-4 rounded-lg border border-white/10 bg-white/5 p-4 transition-colors hover:border-emerald-500/40 hover:bg-emerald-500/5">
      <div className="mt-0.5 shrink-0">
        <CheckCircle2 className="h-4 w-4 text-emerald-400" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          {price && (
            <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-sm font-bold text-emerald-400">
              {price}
            </span>
          )}
          <span className="rounded bg-white/10 px-2 py-0.5 text-xs text-white/50">
            {deal.source}
          </span>
          <span className="text-xs text-white/30">{fmtRelative(deal.created_at)}</span>
        </div>
        <p className="mt-1 text-sm text-white/80 leading-snug">{title}</p>
        <p className="mt-0.5 text-xs text-white/30">{fmtDate(deal.created_at)}</p>
      </div>
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 rounded p-1.5 text-white/30 transition-colors hover:text-emerald-400"
          title="Open post"
        >
          <ExternalLink className="h-4 w-4" />
        </a>
      )}
    </div>
  );
}

// ── Setup guide ───────────────────────────────────────────────────────────────

function NtfySetup({ topic }: { topic: string }) {
  const isConfigured = Boolean(topic);

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
      <div className="flex items-center gap-2 mb-4">
        <Smartphone className="h-5 w-5 text-blue-400" />
        <h2 className="font-semibold text-white">Phone Notifications via ntfy.sh</h2>
        {isConfigured ? (
          <span className="ml-auto rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-400">
            Configured
          </span>
        ) : (
          <span className="ml-auto rounded-full bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-400">
            Not configured
          </span>
        )}
      </div>

      {isConfigured ? (
        <p className="text-sm text-white/60">
          Notifications going to topic{" "}
          <code className="rounded bg-white/10 px-1.5 py-0.5 text-emerald-400">{topic}</code>.
          Install the ntfy app and subscribe to that topic to receive deal alerts on your phone.
        </p>
      ) : (
        <ol className="space-y-3 text-sm text-white/60">
          <li className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-500/20 text-xs font-bold text-blue-400">1</span>
            <span>
              Install the{" "}
              <a href="https://ntfy.sh" target="_blank" rel="noopener noreferrer" className="text-blue-400 underline">
                ntfy app
              </a>{" "}
              on your phone (iOS or Android — it&apos;s free).
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-500/20 text-xs font-bold text-blue-400">2</span>
            <span>
              Choose a unique topic name, e.g.{" "}
              <code className="rounded bg-white/10 px-1.5 py-0.5 text-white/80">flipflop-ram-abc123</code>.
              Subscribe to it in the app.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-500/20 text-xs font-bold text-blue-400">3</span>
            <span>
              Add to your backend <code className="rounded bg-white/10 px-1.5 py-0.5 text-white/80">.env</code>:
              <br />
              <code className="mt-1 block rounded bg-black/40 px-3 py-2 text-emerald-400">
                NTFY_TOPIC=flipflop-ram-abc123
              </code>
            </span>
          </li>
          <li className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-500/20 text-xs font-bold text-blue-400">4</span>
            <span>Restart the backend, then use the Test button above to verify it works.</span>
          </li>
        </ol>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function RamWatchPage() {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [dealsRes, configRes] = await Promise.all([
        fetch(`${API_BASE_URL}/ram-watch/deals`),
        fetch(`${API_BASE_URL}/ram-watch/config`),
      ]);
      if (dealsRes.ok) setDeals(await dealsRes.json());
      if (configRes.ok) setConfig(await configRes.json());
      setLastRefresh(new Date());
    } catch {
      // backend may not be running; fail silently
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const triggerScan = async () => {
    setTriggering(true);
    try {
      await fetch(`${API_BASE_URL}/ram-watch/trigger`, { method: "POST" });
      await load();
    } finally {
      setTriggering(false);
    }
  };

  const sendTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE_URL}/ram-watch/test-notify`, { method: "POST" });
      const data = await res.json();
      setTestResult(data.ok ? "Notification sent!" : `Failed: ${data.reason}`);
    } catch {
      setTestResult("Request failed — is the backend running?");
    } finally {
      setTesting(false);
      setTimeout(() => setTestResult(null), 5000);
    }
  };

  const totalDeals = deals.length;
  const threshold = config?.threshold_gbp ?? 240;
  const ntfyTopic = config?.ntfy_topic ?? "";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <MemoryStick className="h-6 w-6 text-emerald-400" />
            <h1 className="text-2xl font-bold text-white">RAM Watch</h1>
          </div>
          <p className="mt-1 text-sm text-white/50">
            Monitors r/buildapcsales &amp; r/buildapcuk every 15 min for DDR5 deals below{" "}
            <span className="text-emerald-400 font-semibold">£{threshold}</span>.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {lastRefresh && (
            <span className="flex items-center gap-1 text-xs text-white/30">
              <Clock className="h-3 w-3" />
              {fmtRelative(lastRefresh.toISOString())}
            </span>
          )}
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white/70 transition-colors hover:border-white/20 hover:text-white disabled:opacity-40"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button
            onClick={triggerScan}
            disabled={triggering}
            className="flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-sm text-emerald-400 transition-colors hover:bg-emerald-500/20 disabled:opacity-40"
          >
            <Zap className="h-3.5 w-3.5" />
            {triggering ? "Scanning…" : "Scan now"}
          </button>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatChip label="Deals found" value={totalDeals} accent={totalDeals > 0} />
        <StatChip label="Threshold" value={`£${threshold}`} />
        <StatChip label="Check interval" value="15 min" />
        <StatChip
          label="Notifications"
          value={ntfyTopic ? "On" : "Off"}
          accent={Boolean(ntfyTopic)}
        />
      </div>

      {/* ntfy status + test */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-white/10 bg-white/5 px-4 py-3">
        {ntfyTopic ? (
          <Bell className="h-4 w-4 text-emerald-400" />
        ) : (
          <BellOff className="h-4 w-4 text-white/30" />
        )}
        <span className="text-sm text-white/60">
          {ntfyTopic ? (
            <>
              Pushing to{" "}
              <code className="rounded bg-white/10 px-1.5 py-0.5 text-emerald-400">{ntfyTopic}</code>
            </>
          ) : (
            "ntfy.sh not configured — see setup guide below"
          )}
        </span>
        <button
          onClick={sendTest}
          disabled={testing || !ntfyTopic}
          className="ml-auto flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/50 transition-colors hover:border-white/20 hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
          title={ntfyTopic ? "Send test notification" : "Configure ntfy_topic first"}
        >
          {testing ? (
            <RefreshCw className="h-3 w-3 animate-spin" />
          ) : (
            <Bell className="h-3 w-3" />
          )}
          Test notification
        </button>
        {testResult && (
          <span
            className={`flex items-center gap-1 text-xs ${
              testResult.startsWith("Notification") ? "text-emerald-400" : "text-red-400"
            }`}
          >
            {testResult.startsWith("Notification") ? (
              <CheckCircle2 className="h-3 w-3" />
            ) : (
              <AlertCircle className="h-3 w-3" />
            )}
            {testResult}
          </span>
        )}
      </div>

      {/* Deal feed */}
      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-widest text-white/40">
          Deal history
        </h2>
        {loading ? (
          <div className="flex items-center justify-center py-12 text-white/30">
            <RefreshCw className="h-5 w-5 animate-spin" />
          </div>
        ) : deals.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-white/10 py-16 text-center">
            <MemoryStick className="h-10 w-10 text-white/20" />
            <p className="text-sm text-white/40">No deals found yet</p>
            <p className="max-w-xs text-xs text-white/25">
              The watcher checks every 15 minutes. Hit &ldquo;Scan now&rdquo; to run immediately, or
              wait for the next scheduled pass.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {deals.map((d) => (
              <DealRow key={d.id} deal={d} />
            ))}
          </div>
        )}
      </div>

      {/* Setup guide */}
      <NtfySetup topic={ntfyTopic} />

      {/* Config hint */}
      <div className="rounded-lg border border-white/10 bg-white/5 p-4 text-xs text-white/40 space-y-1">
        <p className="font-semibold text-white/60">Configuring the watcher</p>
        <p>
          Set these in your backend <code className="text-white/60">.env</code> or{" "}
          <code className="text-white/60">.env.local</code>:
        </p>
        <pre className="mt-2 rounded bg-black/40 p-3 text-emerald-400/80 leading-relaxed">
          {`NTFY_TOPIC=your-unique-topic-name
RAM_WATCH_THRESHOLD_GBP=240.0
RAM_WATCH_ENABLED=true`}
        </pre>
        <p>Restart the backend after changing env vars.</p>
      </div>
    </div>
  );
}
