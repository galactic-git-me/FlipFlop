"use client";

import { useEffect, useState } from "react";
import { Database, Plus, RefreshCw, Trash2, CheckCircle, XCircle, Globe, Code } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { DataSource } from "@/lib/types";
import { api, SearchTelemetryItem, SearchTelemetrySourceSummary } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";

export default function SourcesPage() {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [saving, setSaving] = useState(false);
  const [scrapingId, setScrapingId] = useState<number | null>(null);
  const [telemetrySummary, setTelemetrySummary] = useState<Record<string, SearchTelemetrySourceSummary>>({});
  const [telemetryItems, setTelemetryItems] = useState<Record<string, SearchTelemetryItem[]>>({});
  const [telemetryLoading, setTelemetryLoading] = useState(true);
  const [newSource, setNewSource] = useState({ name: "", url: "", type: "scrape" as "api" | "scrape" });

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.sources.list() as DataSource[];
      setSources(data);
    } catch {
      setSources([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => { void load(); }, 0);
    return () => clearTimeout(t);
  }, []);

  const loadTelemetry = async () => {
    setTelemetryLoading(true);
    try {
      const data = await api.searchTelemetry.bySource(1200);
      setTelemetrySummary(data.summary || {});
      setTelemetryItems(data.items || {});
    } catch {
      setTelemetrySummary({});
      setTelemetryItems({});
    } finally {
      setTelemetryLoading(false);
    }
  };

  useEffect(() => {
    const t = setTimeout(() => { void loadTelemetry(); }, 0);
    return () => clearTimeout(t);
  }, []);

  const toggle = async (source: DataSource) => {
    try {
      const updated = await api.sources.update(source.id, { enabled: !source.enabled }) as DataSource;
      setSources(prev => prev.map(s => s.id === source.id ? updated : s));
    } catch { /* ignore */ }
  };

  const remove = async (id: number) => {
    try {
      await api.sources.delete(id);
      setSources(prev => prev.filter(s => s.id !== id));
    } catch { /* ignore */ }
  };

  const add = async () => {
    if (!newSource.name || !newSource.url) return;
    setSaving(true);
    try {
      const created = await api.sources.create({
        name: newSource.name,
        url: newSource.url,
        source_type: newSource.type,
        enabled: true,
      }) as DataSource;
      setSources(prev => [...prev, created]);
      setNewSource({ name: "", url: "", type: "scrape" });
      setShowAdd(false);
    } finally {
      setSaving(false);
    }
  };

  const scrape = async (id: number) => {
    setScrapingId(id);
    try {
      await api.sources.trigger(id);
      await load();
      await loadTelemetry();
    } finally {
      setScrapingId(null);
    }
  };

  const enabledCount = sources.filter(s => s.enabled).length;
  const totalListings = sources.reduce((sum, s) => sum + (s.listings_found_total ?? 0), 0);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
            <Database className="w-5 h-5 text-[var(--nf-primary)]" /> Source_Control
          </h1>
          <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
            {enabledCount} of {sources.length} sources active · {totalListings.toLocaleString()} total listings
          </p>
        </div>
        <Button variant="primary" size="sm" onClick={() => setShowAdd(!showAdd)}>
          <Plus className="w-3.5 h-3.5" /> Add Source
        </Button>
      </div>

      {showAdd && (
        <Card className="border-[#00dc82]/20">
          <CardContent className="pt-4 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <input
                placeholder="Source name (e.g. Shpock)"
                value={newSource.name}
                onChange={e => setNewSource(p => ({ ...p, name: e.target.value }))}
                className="px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50"
              />
              <input
                placeholder="URL (e.g. https://shpock.com)"
                value={newSource.url}
                onChange={e => setNewSource(p => ({ ...p, url: e.target.value }))}
                className="px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50"
              />
              <select
                value={newSource.type}
                onChange={e => setNewSource(p => ({ ...p, type: e.target.value as "api" | "scrape" }))}
                className="px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 outline-none focus:border-[#00dc82]/50"
              >
                <option value="scrape">Web Scraping</option>
                <option value="api">API</option>
              </select>
            </div>
            <div className="flex gap-2">
              <Button variant="primary" size="sm" onClick={add} disabled={saving}>
                {saving ? "Saving…" : "Save Source"}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setShowAdd(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="pt-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm uppercase tracking-wider text-[var(--nf-primary)] font-mono">Search Telemetry</h2>
            <Button variant="ghost" size="sm" onClick={loadTelemetry} disabled={telemetryLoading}>
              <RefreshCw className={`w-3.5 h-3.5 ${telemetryLoading ? "animate-spin" : ""}`} />
              {telemetryLoading ? "Refreshing…" : "Refresh"}
            </Button>
          </div>
          {telemetryLoading ? (
            <div className="text-xs text-slate-500">Loading telemetry…</div>
          ) : Object.keys(telemetrySummary).length === 0 ? (
            <div className="text-xs text-slate-500">No telemetry yet. Run a source scrape first.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#1e2d45]">
                    {["Source", "Terms", "Found", "New", "Errors", "Recent Error Terms"].map(h => (
                      <th key={h} className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1e2d45]">
                  {Object.entries(telemetrySummary).map(([source, summary]) => {
                    const rows = telemetryItems[source] || [];
                    const recentErrorTerms = rows.filter(r => r.error).slice(-3).map(r => r.term);
                    return (
                      <tr key={source} className="hover:bg-white/[0.02] transition-colors">
                        <td className="px-3 py-2 text-slate-200 font-medium">{source}</td>
                        <td className="px-3 py-2 text-slate-300">{summary.terms}</td>
                        <td className="px-3 py-2 text-slate-300">{summary.found_total}</td>
                        <td className="px-3 py-2 text-[#00dc82]">{summary.new_total}</td>
                        <td className={`px-3 py-2 ${summary.errors > 0 ? "text-amber-400" : "text-slate-400"}`}>{summary.errors}</td>
                        <td className="px-3 py-2 text-xs text-slate-400">
                          {recentErrorTerms.length > 0 ? recentErrorTerms.join(" · ") : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-500 text-sm gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" /> Loading sources…
        </div>
      ) : sources.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No data sources configured"
          description='Add your first source above. eBay, Gumtree and Facebook Marketplace are auto-seeded on first run.'
          action={{ label: "Reload", onClick: load }}
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#1e2d45]">
                  {["Source", "Type", "Status", "Last Scraped", "Listings", ""].map(h => (
                    <th key={h} className="px-5 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2d45]">
                {sources.map(source => (
                  <tr key={source.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-5 py-4">
                      {(() => {
                        const failures = source.config?.consecutive_failures ?? 0;
                        const autoDisabled = !source.enabled && failures >= 3 && !!source.last_error?.includes("auto-disabled");
                        return (
                      <div className="flex items-center gap-2">
                        <Globe className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
                        <div>
                          <div className="font-medium text-slate-200">{source.name}</div>
                          <div className="text-xs text-slate-500 mt-0.5">{source.url}</div>
                          {failures > 0 && (
                            <div className={`text-[11px] mt-1 ${autoDisabled ? "text-red-400" : "text-amber-400"}`}>
                              {autoDisabled ? "Auto-disabled" : "Backoff active"} · {failures} consecutive failure{failures === 1 ? "" : "s"}
                            </div>
                          )}
                          {autoDisabled && source.last_error && (
                            <div className="text-[10px] text-slate-500 mt-0.5 line-clamp-1">{source.last_error}</div>
                          )}
                        </div>
                      </div>
                        );
                      })()}
                    </td>
                    <td className="px-5 py-4">
                      <Badge variant={source.source_type === "api" ? "info" : "muted"}>
                        {source.source_type === "api" ? <Code className="w-3 h-3" /> : <Globe className="w-3 h-3" />}
                        {source.source_type === "api" ? "API" : "Scraping"}
                      </Badge>
                    </td>
                    <td className="px-5 py-4">
                      <button
                        onClick={() => toggle(source)}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-all ${
                          source.enabled
                            ? "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/30 hover:bg-red-500/10 hover:text-red-400 hover:border-red-400/30"
                            : "bg-slate-700/30 text-slate-500 border-slate-700/50 hover:bg-[#00dc82]/10 hover:text-[#00dc82] hover:border-[#00dc82]/30"
                        }`}
                      >
                        {source.enabled
                          ? <><CheckCircle className="w-3 h-3" /> Active</>
                          : <><XCircle className="w-3 h-3" /> Disabled</>}
                      </button>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-1.5">
                        <RefreshCw className="w-3 h-3 text-slate-600" />
                        <span className="text-xs text-slate-400">
                          {source.last_scraped_at ? formatRelativeTime(new Date(source.last_scraped_at)) : "Never"}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-sm font-semibold text-slate-300">
                        {(source.listings_found ?? 0).toLocaleString()}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => scrape(source.id)}
                          disabled={scrapingId === source.id}
                        >
                          <RefreshCw className={`w-3 h-3 ${scrapingId === source.id ? "animate-spin" : ""}`} />
                          {scrapingId === source.id ? "Scraping…" : "Scrape"}
                        </Button>
                        <Button variant="danger" size="sm" onClick={() => remove(source.id)}>
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
