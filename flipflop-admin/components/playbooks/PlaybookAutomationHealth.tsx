"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { BrandCubeLoader } from "@/components/ui/brand-cube-loader";
import type { PlaybookRefreshRun } from "@/lib/playbook-proposals";

type AutomationStatus = {
  setting_enabled: boolean;
  registered: boolean;
  enabled: boolean;
  next_run_at: string | null;
  scheduled_latest: PlaybookRefreshRun | null;
  scheduled_rebuild_latest: PlaybookRefreshRun | null;
  manual_latest: PlaybookRefreshRun | null;
};

const dateLabel = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString("en-GB") : "No run recorded";

export default function PlaybookAutomationHealth() {
  const [status, setStatus] = useState<AutomationStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const load = useCallback(async (showProgress = false) => {
    if (showProgress) setChecking(true);
    setError(null);
    try {
      setStatus(await api.commercialReadiness.automation());
      setLastChecked(new Date());
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not load Playbook automation status."
      );
    } finally {
      if (showProgress) setChecking(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 30000);
    return () => window.clearInterval(timer);
  }, [load]);

  const latest = status?.scheduled_latest;
  const latestRebuild = status?.scheduled_rebuild_latest;

  return (
    <section
      aria-label="Scheduled Playbook catalogue refresh"
      className="mt-3 rounded border border-slate-700 bg-slate-950/40 p-3 text-sm"
    >
      <h3 className="font-medium">Automatic catalogue refresh health</h3>
      {error && <p role="alert" className="mt-2 text-amber-300">{error}</p>}
      {!status && !error && (
        <BrandCubeLoader
          label="Checking API scheduler and last run…"
          size="xs"
          className="mt-2"
        />
      )}
      {status && (
        <>
          <p className="mt-2">
            {status.enabled
              ? "Scheduled refresh is enabled and registered."
              : status.setting_enabled
                ? "Refresh is configured on, but its hourly job is not currently registered."
                : "Scheduled catalogue refresh is disabled in this API environment."}
          </p>
          {status.enabled && status.next_run_at && (
            <p className="mt-1 text-slate-400">
              Next scheduled refresh: {dateLabel(status.next_run_at)}
            </p>
          )}
          <p className="mt-1 text-slate-400">
            Last scheduled run: {latest
              ? `${latest.status} · started ${dateLabel(latest.started_at)} · ${latest.phase}`
              : "No durable scheduled run recorded yet."}
          </p>
          {latest?.error && (
            <p role="alert" className="mt-1 text-amber-300">
              Latest scheduled run error: {latest.error}
            </p>
          )}
          <p className="mt-1 text-slate-400">
            Last automatic rebuild after changed supplier facts: {latestRebuild
              ? `${latestRebuild.status} · started ${dateLabel(latestRebuild.started_at)} · ${latestRebuild.phase}`
              : "No changed-fact rebuild has been needed yet."}
          </p>
          {latestRebuild?.error && (
            <p role="alert" className="mt-1 text-amber-300">
              Latest automatic rebuild error: {latestRebuild.error}
            </p>
          )}
          {status.manual_latest && (
            <p className="mt-1 text-slate-500">
              Last manual source refresh: {status.manual_latest.status} · {dateLabel(status.manual_latest.started_at)}
            </p>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={checking}
              onClick={() => void load(true)}
              className="text-emerald-300 underline disabled:cursor-wait disabled:opacity-60"
            >
              {checking ? "Checking status…" : "Check status now"}
            </button>
            {checking ? (
              <BrandCubeLoader
                label="Refreshing scheduler status…"
                size="xs"
              />
            ) : lastChecked ? (
              <p role="status" className="text-slate-400">
                Status checked at {lastChecked.toLocaleTimeString("en-GB")}
              </p>
            ) : null}
          </div>
        </>
      )}
    </section>
  );
}
