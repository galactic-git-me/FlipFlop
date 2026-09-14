"use client";

import { useEffect, useMemo, useState } from "react";
import { Settings, Save, RefreshCw, Database, Plus, Trash2, Link2, Unlink, Terminal, Circle, Search } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, API_BASE_URL } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface AppSettings {
  max_concurrent_flips: number;
  auto_buy_autonomous: boolean;
  auto_buy_daily_limit: number;
  ollama_base_url: string;
  ollama_model: string;
  openrouter_api_key: string;
  openrouter_primary_model: string;
  image_gen_enabled: boolean;
  image_gen_provider: string;
  default_sell_platform: string;
  ebay_app_id: string;
  // Seller Policies (playbook rows 11-15, 43, 44) — configured once, applied
  // to every listing, not re-entered per build (see build details Dispatch tab).
  handling_time_days: number;
  returns_accepted: boolean;
  returns_window_days: number;
  free_shipping_enabled: boolean;
  local_pickup_enabled: boolean;
  listing_type_default: string;
  opportunity_super_profit_gbp: number;
  opportunity_super_roi_pct: number;
  opportunity_super_confidence: number;
  opportunity_super_liquidity: number;
  opportunity_super_score: number;
  opportunity_super_market_discount_pct: number;
  opportunity_gem_profit_gbp: number;
  opportunity_gem_roi_pct: number;
  opportunity_gem_confidence: number;
  opportunity_gem_liquidity: number;
  opportunity_gem_score: number;
  opportunity_gem_market_discount_pct: number;
  opportunity_delivery_fallback_gbp: number;
  opportunity_ebay_fee_pct: number;
  opportunity_packaging_gbp: number;
  opportunity_testing_refurbishment_gbp: number;
  opportunity_returns_warranty_pct: number;
  opportunity_minimum_sold_comps: number;
  opportunity_minimum_source_diversity: number;
}

interface DataSource {
  id: number;
  name: string;
  url: string;
  source_type: string;
  enabled: boolean;
  config?: Record<string, unknown>;
}

const SCORE_COMPONENTS = [
  { label: "Economic return · 45%", description: "How attractive the resale economics are after purchase and selling costs.", calculation: "Compares the listing price with the median same-condition market price, subtracts delivery, fees, packaging, testing and reserve costs, then normalises expected profit and ROI against the configured GEM and SUPER GEM floors. It contributes 45% of the final score." },
  { label: "Desirability · 15%", description: "How strongly buyers are likely to want the identified product.", calculation: "Uses product and category demand signals, preferred-product fit and inventory fit. It contributes 15%." },
  { label: "Market confidence · 15%", description: "How trustworthy the market-price estimate is.", calculation: "Combines comparable sample size, source diversity and identity confidence. It contributes 15%." },
  { label: "Risk safety · 5%", description: "How few risks or warnings were found for the listing.", calculation: "Starts from a safe score and deducts for identity, condition, seller and evidence risks. It contributes 5%." },
  { label: "Liquidity · 20%", description: "How likely the item is to sell within a reasonable time.", calculation: "Uses sold volume, active competition and available watch or bid velocity. It contributes 20%." },
] as const;

const CLASSIFICATION_COLORS = ["#f97316", "#3b82f6", "#a78bfa", "#22c55e", "#eab308", "#ef4444", "#64748b", "#94a3b8"];

const DEFAULTS: AppSettings = {
  max_concurrent_flips: 1,
  auto_buy_autonomous: false,
  auto_buy_daily_limit: 3,
  ollama_base_url: process.env.NEXT_PUBLIC_OLLAMA_BASE_URL ?? "",
  ollama_model: process.env.NEXT_PUBLIC_OLLAMA_MODEL ?? "",
  openrouter_api_key: "",
  openrouter_primary_model: "google/gemma-4-31b-it:free",
  image_gen_enabled: true,
  image_gen_provider: "pollinations",
  default_sell_platform: "ebay",
  ebay_app_id: "",
  handling_time_days: 2,
  returns_accepted: true,
  returns_window_days: 30,
  free_shipping_enabled: true,
  local_pickup_enabled: true,
  listing_type_default: "FixedPrice",
  opportunity_super_profit_gbp: 50,
  opportunity_super_roi_pct: 25,
  opportunity_super_confidence: 80,
  opportunity_super_liquidity: 60,
  opportunity_super_score: 85,
  opportunity_super_market_discount_pct: 35,
  opportunity_gem_profit_gbp: 30,
  opportunity_gem_roi_pct: 18,
  opportunity_gem_confidence: 70,
  opportunity_gem_liquidity: 45,
  opportunity_gem_score: 75,
  opportunity_gem_market_discount_pct: 25,
  opportunity_delivery_fallback_gbp: 15,
  opportunity_ebay_fee_pct: 0,
  opportunity_packaging_gbp: 6,
  opportunity_testing_refurbishment_gbp: 10,
  opportunity_returns_warranty_pct: 5,
  opportunity_minimum_sold_comps: 3,
  opportunity_minimum_source_diversity: 2,
};

function Toggle({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      className={`w-10 h-6 rounded-full border-2 relative transition-all flex-shrink-0 ${
        checked ? "bg-[#00dc82] border-[#00dc82]" : "bg-[#1e2d45] border-[#1e2d45]"
      }`}
    >
      <div className={`w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all ${checked ? "left-4" : "left-0.5"}`} />
    </button>
  );
}

type TabKey = "opportunity" | "seller-policies" | "sources" | "extension-logs" | "sold-logs" | "server-logs" | "price-evidence";

export default function SettingsPage() {
  const [tab, setTab] = useState<TabKey>("opportunity");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [settings, setSettings] = useState<AppSettings>(DEFAULTS);
  const [sources, setSources] = useState<DataSource[]>([]);

  const [newSourceName, setNewSourceName] = useState("");
  const [newSourceUrl, setNewSourceUrl] = useState("");
  const [extensionLogs, setExtensionLogs] = useState<import("@/lib/api").SearchTelemetryItem[]>([]);
  const [soldLogs, setSoldLogs] = useState<import("@/lib/api").SoldScrapingItem[]>([]);
  const [soldLogNote, setSoldLogNote] = useState("");
  const [logsLoading, setLogsLoading] = useState(false);
  const [opportunityItems, setOpportunityItems] = useState<OpportunityPolicyItem[]>([]);
  const [opportunityCounts, setOpportunityCounts] = useState({ active: 0, total: 0, historical: 0 });
  const [opportunityPreviewDirty, setOpportunityPreviewDirty] = useState(false);
  const [opportunityLoading, setOpportunityLoading] = useState(false);
  const [opportunityError, setOpportunityError] = useState<string | null>(null);


  const [ebayStatus, setEbayStatus] = useState<{
    connected: boolean;
    connected_at: string | null;
    username: string | null;
    email: string | null;
    seller_eligible: boolean | null;
    scopes: string[];
    refresh_token_expires_at: string | null;
  } | null>(null);
  const [connectingEbay, setConnectingEbay] = useState(false);

  const ebaySellerScopes = new Set(ebayStatus?.scopes ?? []);
  const hasSellerApiAccess = [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
  ].every(scope => ebaySellerScopes.has(scope));

  async function loadEbayStatus() {
    try {
      setEbayStatus(await api.ebayOAuth.status());
    } catch {
      setEbayStatus(null);
    }
  }

  async function connectEbay() {
    setConnectingEbay(true);
    try {
      const { url } = await api.ebayOAuth.authorizeUrl();
      window.location.href = url;
    } catch (err) {
      alert(err instanceof Error ? err.message : "Could not start eBay connection.");
    } finally {
      setConnectingEbay(false);
    }
  }

  async function disconnectEbay() {
    await api.ebayOAuth.disconnect();
    await loadEbayStatus();
  }

  async function withTimeout<T>(p: Promise<T>, ms = 8000): Promise<T> {
    return await Promise.race([
      p,
      new Promise<T>((_, reject) => setTimeout(() => reject(new Error("timeout")), ms)),
    ]);
  }

  async function loadAll() {
    setLoading(true);
    try {
      const [s, src] = await Promise.allSettled([
        withTimeout(api.settings.get()),
        withTimeout(api.sources.list() as Promise<DataSource[]>),
      ]);

      if (s.status === "fulfilled" && s.value) {
        setSettings(prev => ({ ...prev, ...(s.value as Partial<AppSettings>) }));
      }
      if (src.status === "fulfilled") {
        setSources(src.value ?? []);
      } else {
        setSources([]);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const t = setTimeout(() => {
      void loadAll();
      void loadEbayStatus();
    }, 0);
    return () => clearTimeout(t);
     
  }, []);

  useEffect(() => {
    if (tab === "opportunity") {
      setOpportunityLoading(true);
      setOpportunityError(null);
      void api.gemRadar.opportunityPolicyData()
        .then(result => {
          setOpportunityItems(result.items ?? []);
          setOpportunityCounts({ active: result.active_scored_count ?? result.items?.length ?? 0, total: result.total_scored_count ?? result.items?.length ?? 0, historical: result.historical_scored_count ?? 0 });
          setOpportunityPreviewDirty(false);
        })
        .catch((error) => {
          setOpportunityItems([]);
          setOpportunityCounts({ active: 0, total: 0, historical: 0 });
          setOpportunityPreviewDirty(false);
          setOpportunityError(error instanceof Error ? error.message : "Could not load scored listings.");
        })
        .finally(() => setOpportunityLoading(false));
    }
    if (tab === "extension-logs") {
      setLogsLoading(true);
      void api.searchTelemetry.recent(200).then(result => setExtensionLogs(result.items ?? [])).catch(() => setExtensionLogs([])).finally(() => setLogsLoading(false));
    }
    if (tab === "sold-logs") {
      setLogsLoading(true);
      void api.logs.soldScraping(200).then(result => { setSoldLogs(result.items ?? []); setSoldLogNote(result.note ?? ""); }).catch(() => { setSoldLogs([]); setSoldLogNote(""); }).finally(() => setLogsLoading(false));
    }
  }, [tab]);

  // eBay returns here with a result flag. Keep the user on the relevant tab
  // and refresh the authoritative status from the eBay-operations backend.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const result = params.get("ebay_connected");
    if (!result) return;

    setTab("seller-policies");
    void loadEbayStatus();

    // The flag is only a one-time navigation result; removing it prevents a
    // later refresh from looking like a new OAuth completion.
    params.delete("ebay_connected");
    params.delete("reason");
    const query = params.toString();
    window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
     
  }, []);

  const saveSettings = async () => {
    setSaving(true);
    try {
      await api.settings.update(settings as unknown as Record<string, unknown>);
      setSaved(true);
      setTimeout(() => setSaved(false), 2200);
    } finally {
      setSaving(false);
    }
  };

  const opportunityAnalysis = useMemo(() => {
    const baseOrder = ["SUPER_GEM", "GEM", "EVIDENCE_LIMITED_DEAL", "OK_DEAL", "AVERAGE_DEAL", "POOR_DEAL", "INSUFFICIENT_DATA", "INELIGIBLE"];
    const current: Record<string, number> = {};
    const preview: Record<string, number> = {};
    for (const item of opportunityItems) {
      current[item.classification] = (current[item.classification] ?? 0) + 1;
      const next = opportunityPreviewDirty ? previewOpportunity(item, settings).classification : item.classification;
      preview[next] = (preview[next] ?? 0) + 1;
    }
    // Keep pipeline statuses visible too (for example IDENTITY_PENDING),
    // otherwise the cards appear to add up to far fewer listings than the
    // endpoint actually returned.
    const order = [...baseOrder, ...Object.keys(current).filter(key => !baseOrder.includes(key)).sort()];
    const average = (key: keyof Pick<OpportunityPolicyItem, "market_confidence" | "liquidity_score" | "desirability_score" | "risk_score">) => {
      const values = opportunityItems.map(item => item[key]).filter((value): value is number => value != null);
      return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
    };
    const chart = order.map(classification => ({
      name: classification.replaceAll("_", " "),
      current: current[classification] ?? 0,
      preview: preview[classification] ?? 0,
    }));
    const identityFailedCount = current.IDENTITY_FAILED ?? 0;
    const insufficientDataCount = current.INSUFFICIENT_DATA ?? 0;
    const identityFailedPreviewCount = preview.IDENTITY_FAILED ?? 0;
    const insufficientDataPreviewCount = preview.INSUFFICIENT_DATA ?? 0;
    const chartOrder = order.filter(classification => !["IDENTITY_FAILED", "INSUFFICIENT_DATA"].includes(classification));
    const splitChart = [
      { name: "Current", ...Object.fromEntries(chartOrder.map(classification => [classification, current[classification] ?? 0])) },
      { name: "Preview", ...Object.fromEntries(chartOrder.map(classification => [classification, preview[classification] ?? 0])) },
    ];
    const currentTotal = Object.values(current).reduce((sum, value) => sum + value, 0);
    const previewTotal = Object.values(preview).reduce((sum, value) => sum + value, 0);
    return { order, chartOrder, current, preview, average, chart, splitChart, identityFailedCount, identityFailedPreviewCount, insufficientDataCount, insufficientDataPreviewCount, currentTotal, previewTotal };
  }, [opportunityItems, settings, opportunityPreviewDirty]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500 text-sm gap-2">
        <RefreshCw className="w-4 h-4 animate-spin" /> Loading settings…
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Settings className="w-5 h-5 text-slate-400" /> Settings
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">General controls, dynamic data sources, and source-linked search terms.</p>
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={saveSettings}
          disabled={saving || (tab !== "opportunity" && tab !== "seller-policies")}
        >
          <Save className="w-3.5 h-3.5" />
          {saving ? "Saving…" : saved ? "Saved ✓" : "Save"}
        </Button>
      </div>

      {tab !== "seller-policies" && (
        <Card>
          <CardContent className="py-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className={`text-sm font-semibold ${ebayStatus?.connected ? "text-emerald-400" : "text-slate-400"}`}>
                eBay {ebayStatus?.connected ? "Connected" : "Not connected"}
              </p>
              {ebayStatus?.connected && (
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                  <span>Username: {ebayStatus.username ?? "Unavailable"}</span>
                  <span>Email: {ebayStatus.email ?? "Unavailable"}</span>
                  {ebayStatus.seller_eligible !== null && (
                    <span>Seller eligibility: {ebayStatus.seller_eligible ? "Enabled" : "Needs setup"}</span>
                  )}
                </div>
              )}
            </div>
            {ebayStatus?.connected && (
              <button onClick={() => setTab("seller-policies")} className="text-xs text-sky-300 hover:text-sky-200">
                Manage connection
              </button>
            )}
          </CardContent>
        </Card>
      )}

      <div className="flex gap-2">
        {[
          { key: "opportunity", label: "Opportunity Scoring" },
          { key: "seller-policies", label: "Seller Policies" },
          { key: "sources", label: "Data Sources" },
          { key: "extension-logs", label: "Extension Logs" },
          { key: "sold-logs", label: "Sold Scraping" },
          { key: "server-logs", label: "Server Logs" },
          { key: "price-evidence", label: "Price Evidence" },
        ].map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as TabKey)}
            className={`px-3 py-1.5 rounded-lg text-sm border ${
              tab === t.key ? "border-[#00dc82]/40 bg-[#00dc82]/10 text-[#00dc82]" : "border-[#1e2d45] text-slate-400"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "opportunity" && (
        <div className="space-y-6">
          <div className="rounded-lg border border-sky-500/20 bg-sky-500/5 p-4 text-sm font-semibold text-slate-200">
            This view shows the actual inputs used by Gem Radar. Identity and evidence gates run first; eligible listings then combine economics, desirability, market confidence, risk and liquidity into the deal score.
          </div>
          <Card>
            <CardHeader><CardTitle>How the final score is built</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-2 md:grid-cols-5 gap-3 pt-0">
              {SCORE_COMPONENTS.map((component, index) => {
                const values = [100, opportunityAnalysis.average("desirability_score"), opportunityAnalysis.average("market_confidence"), opportunityAnalysis.average("risk_score"), opportunityAnalysis.average("liquidity_score")];
                const tooltipId = `score-component-${index}`;
                return <div key={component.label} className="group relative rounded-lg border border-[#1e2d45] bg-[#0a1119] p-3"><div tabIndex={0} aria-describedby={tooltipId} className="rounded outline-none focus-visible:ring-2 focus-visible:ring-[#00dc82]/70"><p className="text-xs font-semibold text-slate-300">{component.label} <span className="text-[#00dc82]" aria-hidden="true">ⓘ</span></p><p className="mt-2 text-lg font-bold text-slate-100">{values[index].toFixed(0)}<span className="text-xs font-semibold text-slate-300">/100 avg</span></p><div className="mt-2 h-1.5 rounded-full bg-slate-800"><div className="h-full rounded-full bg-[#00dc82]" style={{ width: `${Math.max(0, Math.min(100, values[index]))}%` }} /></div></div><div id={tooltipId} role="tooltip" className="pointer-events-none absolute left-2 right-2 top-full z-30 mt-2 rounded-lg border border-[#00dc82]/40 bg-[#07101a] p-3 text-xs text-slate-200 opacity-0 shadow-xl transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"><p className="font-bold text-[#00dc82]">{component.label}</p><p className="mt-1 font-semibold">{component.description}</p><p className="mt-1 text-slate-300">{component.calculation}</p></div></div>;
              })}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Current classifications and live preview</CardTitle><p className="text-xs font-semibold text-slate-300">{opportunityLoading ? "Loading active scored listings…" : `Showing ${opportunityCounts.active} active scored listings${opportunityCounts.total > opportunityCounts.active ? ` · ${opportunityCounts.total} scored listings retained in the database (${opportunityCounts.historical} historical)` : ""}`}. Current total: <strong className="text-orange-300">{opportunityAnalysis.currentTotal}</strong> · Preview total: <strong className="text-blue-300">{opportunityAnalysis.previewTotal}</strong>. Change a value below to see the estimated split before saving. Historical rows are retained for evidence and price history but are excluded from this current inventory preview. Below-market price is calculated as <strong className="text-slate-200">(market median − listing price) ÷ market median</strong>.</p></CardHeader>
            <CardContent className="pt-0 space-y-3">
              {opportunityError && <p className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-300">Could not load the scored listings: {opportunityError}</p>}
              {!opportunityLoading && !opportunityError && opportunityItems.length === 0 && <p className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-300">No active scored listings are available for this environment yet. The preview is empty; the zero values are not a scoring result. Run a scan and wait for listings to be scored, then refresh this tab.</p>}
              <div className="opportunity-classification-strip rounded-xl p-2">
                <p className="mb-2 px-1 text-[10px] font-semibold text-slate-500">Cards resize to fit the available width and wrap only on smaller screens.</p><div className="grid grid-cols-[repeat(auto-fit,minmax(118px,1fr))] gap-2">
                  {opportunityAnalysis.order.map(classification => { const current = opportunityItems.length ? (opportunityAnalysis.current[classification] ?? 0) : null; const next = opportunityItems.length ? (opportunityAnalysis.preview[classification] ?? 0) : null; const delta = current !== null && next !== null ? next - current : 0; return <div key={classification} className="min-w-0 rounded-lg border border-[#1e2d45] bg-[#0a1119]/95 p-2.5"><p className="break-words text-[9px] font-semibold uppercase leading-tight tracking-wide text-slate-300">{classification.replaceAll("_", " ")}</p><p className="mt-1 text-lg font-bold text-slate-100">{current ?? "—"}</p><p className={`text-[11px] font-semibold ${delta > 0 ? "text-emerald-400" : delta < 0 ? "text-rose-400" : "text-slate-300"}`}>{next === null ? "Preview unavailable" : `Preview ${next}${delta ? ` (${delta > 0 ? "+" : ""}${delta})` : ""}`}</p></div>; })}
                </div>
              </div>
              <div className="rounded-lg border border-[#1e2d45] bg-[#0a1119] p-3">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2"><div><p className="text-sm font-bold text-slate-200">Current vs preview split</p><p className="text-[11px] text-slate-500">Coloured segments show the classifications affected by scoring controls. Excluded statuses are shown as counts beside the chart.</p></div><div className="flex flex-wrap gap-2"><span title="The listing could not be matched confidently to a specific product identity, so the scoring gates cannot be trusted yet." className="cursor-help rounded-full border border-slate-500/30 bg-slate-500/10 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-slate-300">Identity failed · {opportunityAnalysis.identityFailedCount} → {opportunityAnalysis.identityFailedPreviewCount} <span aria-hidden="true">ⓘ</span></span><span title="The listing does not have enough comparable pricing or sold-evidence data to recalculate a reliable opportunity score." className="cursor-help rounded-full border border-slate-500/30 bg-slate-500/10 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-slate-300">Insufficient data · {opportunityAnalysis.insufficientDataCount} → {opportunityAnalysis.insufficientDataPreviewCount} <span aria-hidden="true">ⓘ</span></span></div></div>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={opportunityAnalysis.splitChart} layout="vertical" margin={{ top: 8, right: 18, bottom: 8, left: 8 }} barCategoryGap="35%" reverseStackOrder={false}>
                    <CartesianGrid stroke="#17304a" strokeDasharray="3 3" vertical={false} />
                    <XAxis type="number" allowDecimals={false} tick={{ fill: "#64748b", fontSize: 10 }} />
                    <YAxis type="category" dataKey="name" width={62} tick={{ fill: "#cbd5e1", fontSize: 11, fontWeight: 700 }} />
                    <Tooltip cursor={{ fill: "#17263a", opacity: 0.5 }} contentStyle={{ background: "#07101a", border: "1px solid #1e2d45", borderRadius: 8, color: "#e2e8f0", fontSize: 11 }} />
                    {opportunityAnalysis.chartOrder.map((classification, index) => <Bar key={classification} dataKey={classification} name={classification.replaceAll("_", " ")} stackId="split" fill={CLASSIFICATION_COLORS[index % CLASSIFICATION_COLORS.length]} />)}
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] font-semibold uppercase tracking-wide text-slate-300">
                  {opportunityAnalysis.chartOrder.map((classification, index) => <span key={classification}><span className="mr-1" style={{ color: CLASSIFICATION_COLORS[index % CLASSIFICATION_COLORS.length] }}>■</span>{classification.replaceAll("_", " ")}</span>)}
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Buy-now gates</CardTitle>
              <p className="text-xs font-semibold text-slate-300">A listing must meet every gate in its row. The below-market threshold compares the listing price with the same-condition market median.</p>
            </CardHeader>
            <CardContent className="pt-0 overflow-x-auto">
              <div className="min-w-[760px]">
                <div className="grid grid-cols-[1.35fr_repeat(6,minmax(95px,1fr))] gap-2 px-3 pb-2 text-[10px] font-bold uppercase tracking-wide text-slate-500">
                  <span>Tier</span><span>Profit</span><span>ROI</span><span className="text-[#00dc82]">Below market</span><span>Confidence</span><span>Liquidity</span><span>Score</span>
                </div>
                {[{ title: "SUPER GEM", prefix: "opportunity_super", tone: "text-amber-300", fields: [["profit_gbp", "£"], ["roi_pct", "%"], ["market_discount_pct", "%"], ["confidence", "/100"], ["liquidity", "/100"], ["score", "/100"]] }, { title: "GEM", prefix: "opportunity_gem", tone: "text-cyan-300", fields: [["profit_gbp", "£"], ["roi_pct", "%"], ["market_discount_pct", "%"], ["confidence", "/100"], ["liquidity", "/100"], ["score", "/100"]] }].map(group => (
                  <div key={group.prefix} className="grid grid-cols-[1.35fr_repeat(6,minmax(95px,1fr))] items-center gap-2 rounded-lg border border-[#1e2d45] bg-[#0a1119] p-3 mb-2">
                    <div><p className={`text-sm font-bold ${group.tone}`}>{group.title}</p><p className="text-[10px] text-slate-500">All gates required</p></div>
                    {group.fields.map(([suffix, unit]) => { const key = `${group.prefix}_${suffix}` as keyof AppSettings; const fallback = DEFAULTS[key]; return <label key={key} className={`text-xs font-semibold ${suffix === "market_discount_pct" ? "text-[#00dc82]" : "text-slate-300"}`}><span className="sr-only">{group.title} {suffix}</span><div className="relative"><input type="number" min={0} step="0.1" aria-label={`${group.title} ${suffix}`} value={typeof settings[key] === "number" && Number.isFinite(settings[key] as number) ? settings[key] as number : typeof fallback === "number" ? fallback : 0} onChange={e => { setOpportunityPreviewDirty(true); setSettings(p => ({ ...p, [key]: Number(e.target.value) })); }} className="w-full px-2 py-2 pr-9 bg-[#07101a] border border-[#1e2d45] rounded-lg text-sm font-bold text-slate-100" /><span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-slate-500">{unit}</span></div></label>; })}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
          <Card><CardHeader><CardTitle>Cost stack and evidence gates</CardTitle><p className="text-xs font-semibold text-slate-300">These values recalculate estimated profit, ROI and evidence eligibility in the preview. Component items use their category rules.</p></CardHeader><CardContent className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-0">{[["opportunity_delivery_fallback_gbp", "Delivery fallback (£)"], ["opportunity_ebay_fee_pct", "eBay fee (%)"], ["opportunity_packaging_gbp", "Packaging (£)"], ["opportunity_testing_refurbishment_gbp", "Testing/refurb (£)"], ["opportunity_returns_warranty_pct", "Returns/warranty reserve (%)"], ["opportunity_minimum_sold_comps", "Minimum sold comps"], ["opportunity_minimum_source_diversity", "Minimum source diversity"]].map(([field, label]) => { const key = field as keyof AppSettings; return <label key={field} className="text-xs font-semibold text-slate-300">{label}<input type="number" min={0} step="0.1" value={settings[key] as number} onChange={e => { setOpportunityPreviewDirty(true); setSettings(p => ({ ...p, [key]: Number(e.target.value) })); }} className="mt-1 w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-200" /></label>; })}</CardContent></Card>
        </div>
      )}
      {tab === "seller-policies" && (
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><Link2 className="w-4 h-4" /> eBay Connection</CardTitle></CardHeader>
            <CardContent className="pt-0 space-y-3">
              <p className="text-xs text-slate-500">
                Every live eBay write this app makes — posting/ending/republishing listings,
                pushing these Seller Policies, creating Promoted Listings campaigns — needs a
                one-time eBay seller consent. Without it, everything below still runs
                internally (pricing, scheduling, rules) but doesn&apos;t reach eBay itself.
              </p>
              {!ebayStatus?.connected && typeof window !== "undefined" && window.location.hostname === "localhost" && (
                <p className="text-xs text-amber-300/80">
                  This is the local development instance. eBay consent is stored by the backend/database,
                  so consent completed on the deployed FlipFlop app will not appear here.
                </p>
              )}
              {ebayStatus?.connected ? (
                <div className="flex items-center justify-between p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5">
                  <div>
                    <p className="text-sm text-emerald-400 font-semibold">Connected</p>
                    <p className="text-xs text-slate-300">eBay username: {ebayStatus.username ?? "Unavailable"}</p>
                    <p className="text-xs text-slate-400">eBay email: {ebayStatus.email ?? "Unavailable"}</p>
                    <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                      <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-emerald-300">
                        Seller API access: {hasSellerApiAccess ? "Enabled" : "Limited"}
                      </span>
                      {ebayStatus.seller_eligible !== null && (
                        <span className={`rounded-full border px-2 py-0.5 ${
                          ebayStatus.seller_eligible
                            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                            : "border-amber-500/30 bg-amber-500/10 text-amber-300"
                        }`}>
                          Seller eligibility: {ebayStatus.seller_eligible ? "Enabled" : "Needs setup"}
                        </span>
                      )}
                      {ebayStatus.username === null && ebayStatus.email === null && (
                        <span className="text-amber-300/80">Account details unavailable from eBay</span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500">
                      Since {ebayStatus.connected_at ? new Date(ebayStatus.connected_at).toLocaleDateString() : "—"}
                      {ebayStatus.refresh_token_expires_at && (
                        <> · re-consent needed by {new Date(ebayStatus.refresh_token_expires_at).toLocaleDateString()}</>
                      )}
                    </p>
                  </div>
                    <div className="flex items-center gap-2">
                      <Button variant="outline" size="sm" onClick={loadEbayStatus}>
                        Refresh details
                      </Button>
                      <Button variant="outline" size="sm" onClick={connectEbay} disabled={connectingEbay}>
                      <Link2 className="w-3.5 h-3.5" /> {connectingEbay ? "Redirecting…" : "Reconnect"}
                    </Button>
                    <Button variant="outline" size="sm" onClick={disconnectEbay}>
                      <Unlink className="w-3.5 h-3.5" /> Disconnect
                    </Button>
                  </div>
                </div>
              ) : (
                <Button variant="primary" size="sm" onClick={connectEbay} disabled={connectingEbay}>
                  <Link2 className="w-3.5 h-3.5" /> {connectingEbay ? "Redirecting…" : "Connect eBay"}
                </Button>
              )}
              <p className="text-[11px] text-slate-600">
                Requires <code>ebay_app_id</code> and a registered redirect URL (RuName) in the
                eBay Developer Portal to be configured first — this is a one-time external setup
                step, not something this app can do for you.
              </p>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card>
            <CardHeader><CardTitle>Handling &amp; Returns</CardTitle></CardHeader>
            <CardContent className="space-y-3 pt-0">
              <label className="text-xs text-slate-500 block">
                Handling time (business days) — default proposed, confirm once
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={settings.handling_time_days}
                onChange={e => setSettings(p => ({ ...p, handling_time_days: Number(e.target.value) }))}
                className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm"
              />
              <p className="text-xs text-slate-600">
                Row 11/12: fastest you can realistically hit, factoring in burn-in/QA — never
                padded "just in case", since eBay's Money Back Guarantee already covers late orders.
              </p>

              <div className="flex items-center justify-between p-2 bg-[#0a1119] rounded border border-[#1e2d45]">
                <span className="text-sm text-slate-300">Returns accepted (row 13/14)</span>
                <Toggle checked={settings.returns_accepted} onChange={() => setSettings(p => ({ ...p, returns_accepted: !p.returns_accepted }))} />
              </div>
              <label className="text-xs text-slate-500 block">Returns window (days)</label>
              <input
                type="number"
                min={14}
                max={60}
                value={settings.returns_window_days}
                onChange={e => setSettings(p => ({ ...p, returns_window_days: Number(e.target.value) }))}
                className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm"
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Shipping &amp; Listing Type</CardTitle></CardHeader>
            <CardContent className="space-y-3 pt-0">
              <div className="flex items-center justify-between p-2 bg-[#0a1119] rounded border border-[#1e2d45]">
                <span className="text-sm text-slate-300">Free shipping, absorbed into price (row 15/35)</span>
                <Toggle checked={settings.free_shipping_enabled} onChange={() => setSettings(p => ({ ...p, free_shipping_enabled: !p.free_shipping_enabled }))} />
              </div>
              <div className="flex items-center justify-between p-2 bg-[#0a1119] rounded border border-[#1e2d45]">
                <span className="text-sm text-slate-300">Local pickup offered (row 43)</span>
                <Toggle checked={settings.local_pickup_enabled} onChange={() => setSettings(p => ({ ...p, local_pickup_enabled: !p.local_pickup_enabled }))} />
              </div>
              <label className="text-xs text-slate-500 block">Default listing type (row 44)</label>
              <select
                value={settings.listing_type_default}
                onChange={e => setSettings(p => ({ ...p, listing_type_default: e.target.value }))}
                className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm"
              >
                <option value="FixedPrice">Fixed Price</option>
                <option value="Auction">Auction (not recommended — see row 44)</option>
              </select>
              <p className="text-xs text-slate-600">
                Applied once here via the eBay Business Policies API to every listing — not
                re-entered per build. Per-build overrides live on the Dispatch &amp; Delivery
                tab, only for builds that genuinely can&apos;t hit the global default.
              </p>
            </CardContent>
          </Card>
          </div>
        </div>
      )}

      {tab === "sources" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Database className="w-4 h-4" /> Data Sources</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 pt-0">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <input value={newSourceName} onChange={e => setNewSourceName(e.target.value)} placeholder="Source name" className="px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm" />
              <input value={newSourceUrl} onChange={e => setNewSourceUrl(e.target.value)} placeholder="Source URL" className="px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm" />
              <Button
                variant="primary"
                size="sm"
                onClick={async () => {
                  if (!newSourceName.trim()) return;
                  await api.sources.create({ name: newSourceName.trim(), url: newSourceUrl.trim(), source_type: "scrape", enabled: true, config: {} });
                  setNewSourceName("");
                  setNewSourceUrl("");
                  setSources(await api.sources.list() as DataSource[]);
                }}
              >
                <Plus className="w-3.5 h-3.5" /> Add Source
              </Button>
            </div>

            <div className="space-y-2">
              {sources.map(src => (
                <div key={src.id} className="flex items-center justify-between gap-3 p-3 rounded-xl border border-[#1e2d45] bg-[#0a1119]">
                  <div>
                    <div className="text-sm text-slate-200">{src.name}</div>
                    <div className="text-xs text-slate-500">{src.url || "No URL"}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Toggle
                      checked={src.enabled}
                      onChange={async () => {
                        const updated = await api.sources.update(src.id, { enabled: !src.enabled }) as DataSource;
                        setSources(prev => prev.map(p => (p.id === src.id ? updated : p)));
                      }}
                    />
                    <button
                      className="p-1.5 rounded border border-red-500/30 text-red-400"
                      onClick={async () => {
                        await api.sources.delete(src.id);
                        setSources(await api.sources.list() as DataSource[]);
                      }}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "extension-logs" && (
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Terminal className="w-4 h-4" /> Extension Logs</CardTitle></CardHeader>
          <CardContent className="space-y-3 pt-0">
            <p className="text-xs text-slate-500">Search-run telemetry from FlipFlopXtension. The detailed live progress grid remains in the extension; these durable rows show what reached the backend.</p>
            {logsLoading ? <p className="text-sm text-slate-500">Loading…</p> : extensionLogs.length === 0 ? <p className="text-sm text-slate-600">No extension scan telemetry has arrived yet.</p> : (
              <div className="max-h-[520px] overflow-auto rounded-lg border border-[#1e2d45]">
                <table className="w-full text-xs"><thead className="sticky top-0 bg-[#0a1119] text-slate-500"><tr><th className="text-left p-2">Time</th><th className="text-left p-2">Source</th><th className="text-left p-2">Search term</th><th className="text-right p-2">Found</th><th className="text-right p-2">New</th><th className="text-left p-2">Result</th></tr></thead><tbody>
                  {extensionLogs.map((row, i) => <tr key={`${row.ts}-${i}`} className="border-t border-[#1e2d45]"><td className="p-2 text-slate-500 whitespace-nowrap">{new Date(row.ts).toLocaleString()}</td><td className="p-2 text-slate-300">{row.source || "—"}</td><td className="p-2 text-slate-300">{row.term}</td><td className="p-2 text-right text-slate-300">{row.found}</td><td className="p-2 text-right text-emerald-300">{row.new}</td><td className={`p-2 ${row.error ? "text-red-300" : "text-emerald-300"}`}>{row.error || "completed"}</td></tr>)}
                </tbody></table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "sold-logs" && (
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Database className="w-4 h-4" /> Sold Scraping Logs</CardTitle></CardHeader>
          <CardContent className="space-y-3 pt-0">
            <p className="text-xs text-slate-500">Completed-sale observations persisted by the sold scraper. These are deduplicated and reused by price benchmarks and demand analysis.</p>
            {soldLogNote && <p className="text-[11px] text-slate-600">{soldLogNote}</p>}
            {logsLoading ? <p className="text-sm text-slate-500">Loading…</p> : soldLogs.length === 0 ? <p className="text-sm text-slate-600">No sold scraping results have been stored yet.</p> : (
              <div className="max-h-[520px] overflow-auto rounded-lg border border-[#1e2d45]"><table className="w-full text-xs"><thead className="sticky top-0 bg-[#0a1119] text-slate-500"><tr><th className="text-left p-2">Observed</th><th className="text-left p-2">Item</th><th className="text-left p-2">Condition</th><th className="text-right p-2">Price</th><th className="text-left p-2">Identity</th></tr></thead><tbody>
                {soldLogs.map(row => <tr key={row.id} className="border-t border-[#1e2d45]"><td className="p-2 text-slate-500 whitespace-nowrap">{row.observed_at ? new Date(row.observed_at).toLocaleString() : "—"}</td><td className="p-2 text-slate-300">{row.title}</td><td className="p-2 text-slate-400">{row.condition}</td><td className="p-2 text-right text-emerald-300">£{row.price.toFixed(2)}</td><td className="p-2 text-slate-500">{row.cpk || row.match_key}</td></tr>)}
              </tbody></table></div>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "server-logs" && (
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Terminal className="w-4 h-4" /> Server Logs</CardTitle></CardHeader>
          <CardContent className="pt-0"><ServerLogPanel /></CardContent>
        </Card>
      )}

      {tab === "price-evidence" && <PriceEvidencePanel />}

    </div>
  );
}

interface OpportunityPolicyItem {
  listing_id: string;
  title: string;
  category: string | null;
  condition: string | null;
  classification: string;
  deal_score: number | null;
  expected_profit: number | null;
  roi_pct: number | null;
  market_confidence: number | null;
  market_sample_size: number | null;
  market_source_diversity: number | null;
  liquidity_score: number | null;
  desirability_score: number | null;
  risk_score: number | null;
  eligible: boolean;
  listing_price: number | null;
  resale_price: number | null;
  market_new_price: number | null;
  market_used_price: number | null;
  sold_count: number | null;
  active_count: number | null;
}

const COMPONENT_CATEGORIES = new Set(["cpu", "gpu", "motherboard", "ram", "ssd", "psu", "case", "cooler", "fan"]);

function policyEconomics(item: OpportunityPolicyItem, settings: AppSettings) {
  const category = (item.category ?? "").toLowerCase();
  if (category === "cpu" || category === "ram" || category === "ssd" || category === "cooler" || category === "fan") {
    return { superProfit: 8, superRoi: 25, gemProfit: 3, gemRoi: 15 };
  }
  if (category === "motherboard" || category === "psu" || category === "case") {
    return { superProfit: 15, superRoi: 22, gemProfit: 6, gemRoi: 16 };
  }
  if (category === "gpu") {
    return { superProfit: 25, superRoi: 20, gemProfit: 12, gemRoi: 15 };
  }
  return {
    superProfit: settings.opportunity_super_profit_gbp,
    superRoi: settings.opportunity_super_roi_pct,
    gemProfit: settings.opportunity_gem_profit_gbp,
    gemRoi: settings.opportunity_gem_roi_pct,
  };
}

function previewOpportunity(item: OpportunityPolicyItem, settings: AppSettings): { classification: string; profit: number | null; roi: number | null } {
  const resale = item.resale_price ?? 0;
  const purchase = item.listing_price ?? 0;
  if (!resale || !purchase || item.market_confidence == null || item.liquidity_score == null) {
    // Preserve the backend's current pipeline status when the read model does
    // not contain enough facts to run a local threshold preview. Converting
    // every such row to INSUFFICIENT_DATA made the preview look wildly wrong.
    return { classification: item.classification || "INSUFFICIENT_DATA", profit: null, roi: null };
  }
  const component = COMPONENT_CATEGORIES.has((item.category ?? "").toLowerCase());
  const isNew = (item.condition ?? "").toLowerCase() === "new";
  const shipping = component ? 0 : settings.opportunity_delivery_fallback_gbp;
  const fee = component ? 0 : resale * settings.opportunity_ebay_fee_pct / 100;
  const packaging = component ? 0 : settings.opportunity_packaging_gbp;
  const testing = component ? (isNew ? 0 : 3) : settings.opportunity_testing_refurbishment_gbp;
  const warrantyPct = component ? (isNew ? 0.5 : 2) : settings.opportunity_returns_warranty_pct;
  const totalCost = purchase + shipping + fee + packaging + testing + resale * warrantyPct / 100;
  const profit = resale - totalCost;
  const roi = totalCost > 0 ? profit / totalCost * 100 : 0;
  // Tier decisions must use the same scored facts as the backend. The local
  // cost preview can differ slightly because older rows may have been scored
  // with a different fee/cost policy; using it for tier gates made an isolated
  // market-threshold change demote existing GEM rows to POOR_DEAL.
  const tierProfit = item.expected_profit ?? profit;
  const tierRoi = item.roi_pct ?? roi;
  // The below-market gate compares the listing with the same-condition market
  // benchmark. Conservative resale is used for profit, but must not be used as
  // the market-price denominator because it can include a separate haircut.
  const condition = (item.condition ?? "").toLowerCase();
  const marketPrice = condition.includes("new")
    ? (item.market_new_price ?? item.market_used_price ?? resale)
    : (item.market_used_price ?? item.market_new_price ?? resale);
  const marketDiscount = marketPrice > 0 ? (marketPrice - purchase) / marketPrice * 100 : -Infinity;
  const economics = policyEconomics(item, settings);
  const sample = item.market_sample_size ?? 0;
  const sold = item.sold_count ?? 0;
  if (!item.eligible) return { classification: "INELIGIBLE", profit, roi };
  if (sample < settings.opportunity_minimum_sold_comps || sold < settings.opportunity_minimum_sold_comps) {
    // A threshold what-if cannot recalculate a reliable tier without the
    // evidence gate. Keep the backend's current status visible rather than
    // making the listing disappear into a new preview bucket.
    return { classification: item.classification || "INSUFFICIENT_DATA", profit, roi };
  }
  if (tierProfit >= economics.superProfit && tierRoi >= economics.superRoi && marketDiscount >= settings.opportunity_super_market_discount_pct) {
    return { classification: "SUPER_GEM", profit, roi };
  }
  // A Super Gem threshold what-if must not demote an existing Gem merely
  // because the row was scored with an older cost snapshot. The Gem controls
  // are independent; preserve that tier unless the row actually qualifies for
  // the newly-previewed Super Gem tier.
  if (item.classification === "GEM") return { classification: "GEM", profit, roi };
  if (tierProfit >= economics.gemProfit && tierRoi >= economics.gemRoi && marketDiscount >= settings.opportunity_gem_market_discount_pct) {
    return { classification: "GEM", profit, roi };
  }
  if (tierProfit >= economics.gemProfit && tierRoi >= economics.gemRoi && marketDiscount >= settings.opportunity_gem_market_discount_pct) return { classification: "EVIDENCE_LIMITED_DEAL", profit, roi };
  if (tierProfit > 0) return { classification: "OK_DEAL", profit, roi };
  return { classification: "POOR_DEAL", profit, roi };
}

function ServerLogPanel() {
  const [lines, setLines] = useState<{ ts: string; level: string; msg: string; extra?: Record<string, string> }[]>([]);
  const [connected, setConnected] = useState(false);
  const [target, setTarget] = useState("api");
  const [mode, setMode] = useState<"live" | "dev">((process.env.NEXT_PUBLIC_APP_MODE as "live" | "dev") || "dev");
  const [targets, setTargets] = useState<Array<{ id: string; label: string; available: boolean }>>([]);
  useEffect(() => { void api.logs.targets().then(setTargets).catch(() => setTargets([])); }, []);
  useEffect(() => {
    setLines([]); setConnected(false);
    const es = new EventSource(`${API_BASE_URL}/logs/stream?target=${encodeURIComponent(target)}&mode=${mode}`);
    es.onopen = () => setConnected(true); es.onerror = () => setConnected(false);
    es.onmessage = event => { try { setLines(prev => [...prev, JSON.parse(event.data)].slice(-500)); } catch {} };
    return () => es.close();
  }, [target, mode]);
  return <div className="space-y-3"><div className="flex flex-wrap items-center gap-2"><label className="text-xs text-slate-500">Server<select value={target} onChange={e => setTarget(e.target.value)} className="ml-2 px-2 py-1 rounded bg-[#0a1119] border border-[#1e2d45] text-xs text-slate-200">{targets.length ? targets.map(item => <option key={item.id} value={item.id}>{item.label}{item.available ? "" : " (unavailable)"}</option>) : <option value="api">API server</option>}</select></label><label className="text-xs text-slate-500">Mode<select value={mode} onChange={e => setMode(e.target.value as "live" | "dev")} className="ml-2 px-2 py-1 rounded bg-[#0a1119] border border-[#1e2d45] text-xs text-slate-200"><option value="live">Live / production</option><option value="dev">Development</option></select></label><span className="text-[10px] text-slate-600">{targets.find(item => item.id === target)?.available === false ? "No log file is mounted for this service in the selected environment." : "Streaming selected service"}</span></div><div className="rounded-lg border border-[#1e2d45] bg-black p-3 font-mono text-[11px] max-h-[560px] overflow-auto"><div className="mb-2 text-slate-600"><Circle className={`inline w-2 h-2 mr-1 fill-current ${connected ? "text-emerald-500" : "text-red-500"}`} />{connected ? "LIVE" : "OFFLINE"} · {target} · {mode}</div>{lines.length === 0 ? <span className="text-slate-700">$ waiting for server events…_</span> : lines.map((line, i) => <div key={i} className="leading-6"><span className="text-slate-600">{new Date(line.ts).toLocaleTimeString()}</span> <span className="text-emerald-400">[{line.level}]</span> <span className="text-slate-300">{line.msg}</span></div>)}</div></div>;
}

function PriceEvidencePanel() {
  const [query, setQuery] = useState("");
  const [products, setProducts] = useState<import("@/lib/api").PriceEvidenceProduct[]>([]);
  const [selected, setSelected] = useState<import("@/lib/api").PriceEvidenceProduct | null>(null);
  const [observations, setObservations] = useState<Array<{ kind: string; price: number; observed_at: string | null; source: string | null; source_url: string | null; title: string }>>([]);
  const [loading, setLoading] = useState(false);
  const search = async (value = query) => {
    setLoading(true);
    try { setProducts((await api.priceEvidence.products(value, 200)).items ?? []); } catch { setProducts([]); } finally { setLoading(false); }
  };
  useEffect(() => { void search(""); }, []);
  const choose = async (product: import("@/lib/api").PriceEvidenceProduct) => {
    setSelected(product);
    try { setObservations((await api.priceEvidence.product(product.cpk)).observations ?? []); } catch { setObservations([]); }
  };
  return <div className="space-y-4">
    <Card><CardHeader><CardTitle className="flex items-center gap-2"><Search className="w-4 h-4" /> Product price evidence</CardTitle></CardHeader><CardContent className="space-y-3 pt-0">
      <p className="text-xs text-slate-500">Search canonical products and inspect every active or sold observation contributing to the displayed market range.</p>
      <form className="flex gap-2" onSubmit={e => { e.preventDefault(); void search(); }}><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search product, brand, model or CPK" className="flex-1 px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm" /><Button variant="primary" size="sm" type="submit"><Search className="w-3.5 h-3.5" /> Search</Button></form>
      {loading ? <p className="text-sm text-slate-500">Loading products…</p> : <div className="grid grid-cols-1 lg:grid-cols-[minmax(220px,0.8fr)_minmax(0,2fr)] gap-4">
        <div className="max-h-[560px] overflow-auto rounded-lg border border-[#1e2d45]">{products.length === 0 ? <p className="p-3 text-sm text-slate-600">No products found.</p> : products.map(product => <button key={product.cpk} onClick={() => void choose(product)} className={`w-full text-left p-3 border-b border-[#1e2d45] hover:bg-[#0a1119] ${selected?.cpk === product.cpk ? "bg-[#00dc82]/10" : ""}`}><div className="text-sm text-slate-200">{product.label}</div><div className="text-[10px] text-slate-500">{product.category || "uncategorised"} · {product.listing_count} active contributors</div><div className="text-xs text-emerald-300 mt-1">£{product.min_price?.toFixed(2) ?? "—"} – £{product.max_price?.toFixed(2) ?? "—"}</div></button>)}</div>
        <div className="rounded-lg border border-[#1e2d45] overflow-auto">{!selected ? <p className="p-4 text-sm text-slate-600">Select a product to see its price evidence.</p> : <><div className="p-3 border-b border-[#1e2d45]"><div className="text-sm text-slate-200">{selected.label}</div><div className="text-xs text-slate-500">Market range £{selected.min_price?.toFixed(2) ?? "—"} – £{selected.max_price?.toFixed(2) ?? "—"} · median £{selected.median_price?.toFixed(2) ?? "—"}</div></div><table className="w-full text-xs"><thead className="text-slate-500 bg-[#0a1119]"><tr><th className="text-left p-2">Type</th><th className="text-left p-2">Price</th><th className="text-left p-2">Observed</th><th className="text-left p-2">Source</th><th className="text-left p-2">Item</th></tr></thead><tbody>{observations.map((row, i) => <tr key={`${row.kind}-${row.observed_at}-${i}`} className="border-t border-[#1e2d45]"><td className="p-2 text-slate-400">{row.kind}</td><td className="p-2 text-emerald-300">£{row.price.toFixed(2)}</td><td className="p-2 text-slate-400 whitespace-nowrap">{row.observed_at ? new Date(row.observed_at).toLocaleString() : "—"}</td><td className="p-2 text-slate-400 max-w-[220px] truncate" title={row.source_url || row.source || ""}>{row.source_url || row.source || "—"}</td><td className="p-2 text-slate-300">{row.title}</td></tr>)}</tbody></table></>}</div>
      </div>}
    </CardContent></Card>
  </div>;
}
