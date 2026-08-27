"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BellRing,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Plus,
  RefreshCw,
  RotateCcw,
  X,
} from "lucide-react";
import {
  api,
  type ManualBuildSummary,
  type PriceAlert,
  type PriceAlertList,
} from "@/lib/api";

const EMPTY: PriceAlertList = {
  items: [],
  active_count: 0,
  triggered_count: 0,
  pending_count: 0,
  rules_enabled: false,
  email_enabled: false,
  smtp_configured: false,
};
type Tab = "active" | "pending" | "triggered" | "inactive";

const money = (value: number | null) =>
  value == null ? "—" : `£${value.toFixed(2)}`;
const date = (value: string | null) =>
  value
    ? new Date(value).toLocaleString("en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "—";

export default function PriceAlertsPage() {
  const [data, setData] = useState(EMPTY);
  const [builds, setBuilds] = useState<ManualBuildSummary[]>([]);
  const [tab, setTab] = useState<Tab>("active");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | "create" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [buildId, setBuildId] = useState("");
  const [email, setEmail] = useState("");
  const [target, setTarget] = useState("");

  const load = useCallback(async () => {
    setError(null);
    try {
      const [alerts, buildRows] = await Promise.all([
        api.priceAlerts.list(),
        api.manualBuilds.list(),
      ]);
      setData(alerts);
      setBuilds(buildRows);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Price alerts could not be loaded."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const rows = useMemo(
    () =>
      data.items.filter((item) =>
        tab === "triggered"
          ? item.monitoring_status === "triggered"
          : tab === "pending"
          ? item.monitoring_status.startsWith("pending_")
          : tab === "active"
          ? item.monitoring_status === "armed"
          : item.monitoring_status === "dismissed"
      ),
    [data.items, tab]
  );

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy("create");
    setError(null);
    try {
      await api.priceAlerts.create({
        manual_build_id: Number(buildId),
        user_email: email.trim(),
        target_price_gbp: Number(target),
      });
      setShowCreate(false);
      setBuildId("");
      setTarget("");
      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Alert could not be created."
      );
    } finally {
      setBusy(null);
    }
  };

  const changeState = async (item: PriceAlert) => {
    setBusy(item.id);
    setError(null);
    try {
      if (item.is_active) await api.priceAlerts.dismiss(item.id);
      else await api.priceAlerts.rearm(item.id);
      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Alert could not be updated."
      );
    } finally {
      setBusy(null);
    }
  };

  return (
    <main className="min-h-screen p-5 text-slate-100 md:p-8">
      <div className="mx-auto max-w-7xl space-y-5">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-2 flex items-center gap-2 text-cyan-300">
              <BellRing className="h-5 w-5" />
              <span className="text-xs font-semibold uppercase tracking-[0.18em]">
                Price monitoring
              </span>
            </div>
            <h1 className="text-2xl font-bold">Price Alerts</h1>
            <p className="mt-1 text-sm text-slate-400">
              Monitor build prices and act when they cross your target.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => void load()}
              className="cursor-pointer rounded-lg border border-white/10 p-2.5 text-slate-300 transition-colors hover:border-cyan-300/40 hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
              aria-label="Refresh alerts"
              title="Refresh alerts"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
            <button
              onClick={() => setShowCreate(true)}
              className="flex cursor-pointer items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300"
            >
              <Plus className="h-4 w-4" />
              New alert
            </button>
          </div>
        </header>

        <section className="grid gap-3 sm:grid-cols-4">
          {[
            {
              label: "Pending",
              value: data.pending_count,
              tone: "text-violet-300",
            },
            {
              label: "Active",
              value: data.active_count,
              tone: "text-cyan-300",
            },
            {
              label: "Triggered",
              value: data.triggered_count,
              tone: "text-amber-300",
            },
            {
              label: "All alerts",
              value: data.items.length,
              tone: "text-slate-100",
            },
          ].map((card) => (
            <div
              key={card.label}
              className="rounded-xl border border-white/10 bg-slate-900/60 p-4"
            >
              <div className="text-xs uppercase tracking-wider text-slate-500">
                {card.label}
              </div>
              <div className={`mt-1 text-2xl font-bold ${card.tone}`}>
                {card.value}
              </div>
            </div>
          ))}
        </section>

        {error && (
          <div
            role="alert"
            className="rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-200"
          >
            {error}
          </div>
        )}

        {(!data.rules_enabled || !data.email_enabled || !data.smtp_configured) && (
          <div role="status" className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            Monitoring is not fully operational:
            {!data.rules_enabled ? " rules are disabled;" : ""}
            {!data.smtp_configured ? " SMTP is not configured;" : ""}
            {!data.email_enabled ? " email dispatch is disabled." : ""}
          </div>
        )}

        <section className="overflow-hidden rounded-xl border border-white/10 bg-slate-950/45">
          <div className="flex border-b border-white/10 p-2">
            {(["active", "pending", "triggered", "inactive"] as Tab[]).map((value) => (
              <button
                key={value}
                onClick={() => setTab(value)}
                className={`cursor-pointer rounded-md px-4 py-2 text-sm capitalize transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 ${
                  tab === value
                    ? "bg-cyan-400/15 text-cyan-200"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {value}
              </button>
            ))}
          </div>
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading price alerts…
            </div>
          ) : rows.length === 0 ? (
            <div className="py-16 text-center">
              <BellRing className="mx-auto mb-3 h-7 w-7 text-slate-600" />
              <p className="text-sm text-slate-400">No {tab} price alerts.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead className="bg-white/[0.03] text-xs uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Build / component</th>
                    <th className="px-4 py-3">Target</th>
                    <th className="px-4 py-3">Reference price</th>
                    <th className="px-4 py-3">Email</th>
                    <th className="px-4 py-3">Triggered</th>
                    <th className="px-4 py-3">Listing</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.07]">
                  {rows.map((item) => (
                    <tr key={item.id} className="hover:bg-white/[0.025]">
                      <td className="px-4 py-3">
                        {item.manual_build_id ? (
                          <Link
                            href={`/builds/${item.manual_build_id}`}
                            className="font-semibold text-cyan-200 hover:underline"
                          >
                            {item.build_name}
                          </Link>
                        ) : (
                          <span className="font-semibold text-violet-200">
                            {item.component_key}
                          </span>
                        )}
                        <div className="mt-0.5 text-xs capitalize text-slate-500">
                          {item.alert_type === "component"
                            ? `${item.component_slot ?? "component"} · ${
                                item.discount_threshold_pct ?? 15
                              }% below reference`
                            : item.build_status?.replaceAll("_", " ") ??
                              "Unknown"}
                        </div>
                        <div className="mt-1 text-xs text-slate-400">
                          {item.monitoring_status === "pending_identity"
                            ? "Pending exact CPK identity — monitoring has not started"
                            : item.monitoring_status === "pending_evidence"
                              ? "CPK confirmed; waiting for sufficient fresh market evidence"
                              : item.monitoring_status.replaceAll("_", " ")}
                        </div>
                      </td>
                      <td className="px-4 py-3 font-semibold text-emerald-300">
                        {money(item.target_price_gbp)}
                      </td>
                          <td className="px-4 py-3">
                            {money(item.current_price_gbp)}
                            <div className="mt-0.5 text-xs text-slate-500">
                              {item.reference_basis === "market_median"
                                ? "matched market median"
                                : item.reference_basis === "build_valuation"
                                  ? "recorded build valuation"
                                  : "reference"}
                            </div>
                          </td>
                      <td className="px-4 py-3 text-slate-400">
                        {item.user_email}
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {date(item.triggered_at)}
                        {item.triggered_price_gbp != null && (
                          <div className="text-xs text-amber-300">
                            at {money(item.triggered_price_gbp)}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {item.listing_url ? (
                          <a
                            href={item.listing_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 font-semibold text-cyan-200 hover:text-cyan-100 hover:underline"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                            View listing
                          </a>
                        ) : item.monitoring_status === "pending_identity" ? (
                          <span className="text-xs text-slate-500">Not monitoring—CPK required</span>
                        ) : item.monitoring_status === "pending_evidence" ? (
                          <span className="text-xs text-slate-500">Waiting for fresh CPK evidence</span>
                        ) : (
                          <span className="text-xs text-slate-500">
                            No triggered listing
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          disabled={busy === item.id}
                          onClick={() => void changeState(item)}
                          className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-white/10 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:border-cyan-300/40 hover:text-cyan-200 disabled:cursor-wait disabled:opacity-50"
                        >
                          {item.is_active ? (
                            <>
                              <X className="h-3.5 w-3.5" />
                              Dismiss
                            </>
                          ) : (
                            <>
                              <RotateCcw className="h-3.5 w-3.5" />
                              Re-arm
                            </>
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {showCreate && (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onMouseDown={(e) => {
            if (e.currentTarget === e.target) setShowCreate(false);
          }}
        >
          <form
            onSubmit={create}
            className="w-full max-w-lg rounded-2xl border border-white/15 bg-[#0b111d] p-5 shadow-2xl"
          >
            <div className="mb-5 flex items-start justify-between">
              <div>
                <h2 className="text-lg font-bold">Create price alert</h2>
                <p className="mt-1 text-xs text-slate-400">
                  Notify this email when the monitored build falls below the
                  target.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="cursor-pointer rounded-md p-1 text-slate-400 hover:text-white"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <label className="block text-xs font-medium text-slate-300">
                Build
                <select
                  required
                  value={buildId}
                  onChange={(e) => setBuildId(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2.5 text-sm focus:border-cyan-300/60 focus:outline-none"
                >
                  <option value="">Choose a build…</option>
                  {builds.map((build) => (
                    <option key={build.id} value={build.id}>
                      {build.name} · {money(build.total_cost)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs font-medium text-slate-300">
                Notification email
                <input
                  required
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="mt-1.5 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2.5 text-sm focus:border-cyan-300/60 focus:outline-none"
                />
              </label>
              <label className="block text-xs font-medium text-slate-300">
                Target price (£)
                <input
                  required
                  min="0.01"
                  step="0.01"
                  type="number"
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  placeholder="799.99"
                  className="mt-1.5 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2.5 text-sm focus:border-cyan-300/60 focus:outline-none"
                />
              </label>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="cursor-pointer rounded-lg px-4 py-2 text-sm text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                disabled={busy === "create"}
                className="flex cursor-pointer items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:cursor-wait disabled:opacity-50"
              >
                {busy === "create" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-4 w-4" />
                )}
                Create alert
              </button>
            </div>
          </form>
        </div>
      )}
    </main>
  );
}
