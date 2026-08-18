"use client";

import { useEffect, useMemo, useState } from "react";
import { Settings, Save, RefreshCw, Database, Search, Plus, Trash2, Link2, Unlink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, SourceSearchTerm } from "@/lib/api";

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
  opportunity_gem_profit_gbp: number;
  opportunity_gem_roi_pct: number;
  opportunity_gem_confidence: number;
  opportunity_gem_liquidity: number;
  opportunity_gem_score: number;
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
  opportunity_gem_profit_gbp: 30,
  opportunity_gem_roi_pct: 18,
  opportunity_gem_confidence: 70,
  opportunity_gem_liquidity: 45,
  opportunity_gem_score: 75,
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

type TabKey = "general" | "opportunity" | "seller-policies" | "sources" | "terms";

export default function SettingsPage() {
  const [tab, setTab] = useState<TabKey>("general");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [settings, setSettings] = useState<AppSettings>(DEFAULTS);
  const [sources, setSources] = useState<DataSource[]>([]);
  const [terms, setTerms] = useState<SourceSearchTerm[]>([]);

  const [newSourceName, setNewSourceName] = useState("");
  const [newSourceUrl, setNewSourceUrl] = useState("");

  const [scope, setScope] = useState("cases");
  const [newGroup, setNewGroup] = useState("Fish Tank / Panoramic Cases");
  const [newTerm, setNewTerm] = useState("");
  const [newTermSources, setNewTermSources] = useState<string[]>([]);

  const [ebayStatus, setEbayStatus] = useState<{
    connected: boolean;
    connected_at: string | null;
    scopes: string[];
    refresh_token_expires_at: string | null;
  } | null>(null);
  const [connectingEbay, setConnectingEbay] = useState(false);

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
      const [s, src, t] = await Promise.allSettled([
        withTimeout(api.settings.get()),
        withTimeout(api.sources.list() as Promise<DataSource[]>),
        withTimeout(api.sourceSearchTerms.list(scope)),
      ]);

      if (s.status === "fulfilled" && s.value) {
        setSettings(prev => ({ ...prev, ...(s.value as Partial<AppSettings>) }));
      }
      if (src.status === "fulfilled") {
        setSources(src.value ?? []);
      } else {
        setSources([]);
      }
      if (t.status === "fulfilled") {
        setTerms(t.value.items ?? []);
      } else {
        setTerms([]);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    withTimeout(api.sourceSearchTerms.list(scope))
      .then(r => setTerms(r.items ?? []))
      .catch(() => setTerms([]));
  }, [scope]);

  const groups = useMemo(() => Array.from(new Set(terms.map(t => t.group_name))).sort(), [terms]);

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
          disabled={saving || (tab !== "general" && tab !== "opportunity" && tab !== "seller-policies")}
        >
          <Save className="w-3.5 h-3.5" />
          {saving ? "Saving…" : saved ? "Saved ✓" : "Save"}
        </Button>
      </div>

      <div className="flex gap-2">
        {[
          { key: "general", label: "General" },
          { key: "opportunity", label: "Opportunity Scoring" },
          { key: "seller-policies", label: "Seller Policies" },
          { key: "sources", label: "Data Sources" },
          { key: "terms", label: "Search Terms" },
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

      {tab === "general" && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card>
            <CardHeader><CardTitle>General</CardTitle></CardHeader>
            <CardContent className="space-y-3 pt-0">
              <label className="text-xs text-slate-500 block">Max Concurrent Flips</label>
              <input
                type="range"
                min={1}
                max={10}
                value={settings.max_concurrent_flips}
                onChange={e => setSettings(p => ({ ...p, max_concurrent_flips: Number(e.target.value) }))}
                className="w-full accent-[#00dc82]"
              />
              <label className="text-xs text-slate-500 block">Default Sell Platform</label>
              <input
                value={settings.default_sell_platform}
                onChange={e => setSettings(p => ({ ...p, default_sell_platform: e.target.value }))}
                className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm"
              />
              <div className="flex items-center justify-between p-2 bg-[#0a1119] rounded border border-[#1e2d45]">
                <span className="text-sm text-slate-300">Auto Buy Autonomous</span>
                <Toggle checked={settings.auto_buy_autonomous} onChange={() => setSettings(p => ({ ...p, auto_buy_autonomous: !p.auto_buy_autonomous }))} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Model + eBay</CardTitle></CardHeader>
            <CardContent className="space-y-3 pt-0">
              <input value={settings.openrouter_primary_model} onChange={e => setSettings(p => ({ ...p, openrouter_primary_model: e.target.value }))} placeholder="OpenRouter primary model" className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm" />
              <input value={settings.ollama_base_url} onChange={e => setSettings(p => ({ ...p, ollama_base_url: e.target.value }))} placeholder="Ollama URL" className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm" />
              <input value={settings.ollama_model} onChange={e => setSettings(p => ({ ...p, ollama_model: e.target.value }))} placeholder="Ollama model" className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm" />
              <input value={settings.ebay_app_id} onChange={e => setSettings(p => ({ ...p, ebay_app_id: e.target.value }))} placeholder="eBay App ID" className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm" />
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "opportunity" && (
        <div className="space-y-6">
          <div className="rounded-lg border border-sky-500/20 bg-sky-500/5 p-4 text-sm text-slate-300">
            Labels are earned only after identity and evidence gates pass. Price cannot compensate for an accessory,
            bundle, retro-platform exclusion, or an inadequate same-condition sold cohort.
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {[
              { title: "SUPER_GEM + BUY_NOW", prefix: "opportunity_super", fields: [["profit_gbp", "Minimum profit (£)"], ["roi_pct", "Minimum ROI (%)"], ["confidence", "Market confidence"], ["liquidity", "Liquidity score"], ["score", "Overall score"]] },
              { title: "GEM + BUY_NOW", prefix: "opportunity_gem", fields: [["profit_gbp", "Minimum profit (£)"], ["roi_pct", "Minimum ROI (%)"], ["confidence", "Market confidence"], ["liquidity", "Liquidity score"], ["score", "Overall score"]] },
            ].map(group => (
              <Card key={group.prefix}>
                <CardHeader><CardTitle>{group.title}</CardTitle></CardHeader>
                <CardContent className="grid grid-cols-2 gap-3 pt-0">
                  {group.fields.map(([suffix, label]) => {
                    const key = `${group.prefix}_${suffix}` as keyof AppSettings;
                    return <label key={key} className="text-xs text-slate-500">{label}
                      <input type="number" min={0} step="0.1" value={settings[key] as number}
                        onChange={e => setSettings(p => ({ ...p, [key]: Number(e.target.value) }))}
                        className="mt-1 w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-200" />
                    </label>;
                  })}
                </CardContent>
              </Card>
            ))}
          </div>
          <Card>
            <CardHeader><CardTitle>Cost stack and evidence gates</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-0">
              {[
                ["opportunity_delivery_fallback_gbp", "Delivery fallback (£)"],
                ["opportunity_ebay_fee_pct", "eBay fee (%)"],
                ["opportunity_packaging_gbp", "Packaging (£)"],
                ["opportunity_testing_refurbishment_gbp", "Testing/refurb (£)"],
                ["opportunity_returns_warranty_pct", "Returns/warranty reserve (%)"],
                ["opportunity_minimum_sold_comps", "Minimum sold comps"],
                ["opportunity_minimum_source_diversity", "Minimum source diversity"],
              ].map(([field, label]) => {
                const key = field as keyof AppSettings;
                return <label key={field} className="text-xs text-slate-500">{label}
                  <input type="number" min={0} step="0.1" value={settings[key] as number}
                    onChange={e => setSettings(p => ({ ...p, [key]: Number(e.target.value) }))}
                    className="mt-1 w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-200" />
                </label>;
              })}
            </CardContent>
          </Card>
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
              {ebayStatus?.connected ? (
                <div className="flex items-center justify-between p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5">
                  <div>
                    <p className="text-sm text-emerald-400 font-semibold">Connected</p>
                    <p className="text-xs text-slate-500">
                      Since {ebayStatus.connected_at ? new Date(ebayStatus.connected_at).toLocaleDateString() : "—"}
                      {ebayStatus.refresh_token_expires_at && (
                        <> · re-consent needed by {new Date(ebayStatus.refresh_token_expires_at).toLocaleDateString()}</>
                      )}
                    </p>
                  </div>
                  <Button variant="outline" size="sm" onClick={disconnectEbay}>
                    <Unlink className="w-3.5 h-3.5" /> Disconnect
                  </Button>
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

      {tab === "terms" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Search className="w-4 h-4" /> Search Terms</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 pt-0">
            <div className="flex flex-wrap gap-2 items-center">
              <select value={scope} onChange={e => setScope(e.target.value)} className="px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm">
                <option value="cases">cases</option>
                <option value="flip_opportunities">flip_opportunities</option>
                <option value="accessories">accessories</option>
                <option value="upgrade_parts">upgrade_parts</option>
              </select>
              <select value={newGroup} onChange={e => setNewGroup(e.target.value)} className="px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm">
                {groups.map(g => <option key={g} value={g}>{g}</option>)}
                <option value="Custom">Custom</option>
              </select>
              <input value={newTerm} onChange={e => setNewTerm(e.target.value)} placeholder="New search term" className="flex-1 min-w-[260px] px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm" />
              <Button
                variant="primary"
                size="sm"
                onClick={async () => {
                  if (!newTerm.trim()) return;
                  const groupName = newGroup === "Custom" ? "Custom" : newGroup;
                  await api.sourceSearchTerms.create({
                    scope,
                    group_name: groupName,
                    term: newTerm.trim(),
                    source_names: newTermSources,
                    attributes: { capture_fields: ["color", "material", "size", "form_factor", "theme", "style", "franchise"] },
                    enabled: true,
                  });
                  setNewTerm("");
                  setTerms((await api.sourceSearchTerms.list(scope)).items);
                }}
              >
                <Plus className="w-3.5 h-3.5" /> Add Term
              </Button>
            </div>

            <div className="p-3 bg-[#0a1119] border border-[#1e2d45] rounded-xl">
              <div className="text-xs text-slate-500 mb-2">Assign new term to data sources</div>
              <div className="flex flex-wrap gap-2">
                {sources.map(s => {
                  const picked = newTermSources.includes(s.name);
                  return (
                    <button
                      key={s.id}
                      onClick={() => setNewTermSources(prev => picked ? prev.filter(n => n !== s.name) : [...prev, s.name])}
                      className={`px-2 py-1 rounded text-xs border ${picked ? "bg-[#00dc82]/15 border-[#00dc82]/40 text-[#00dc82]" : "border-[#1e2d45] text-slate-400"}`}
                    >
                      {s.name}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2 max-h-[55vh] overflow-auto pr-1">
              {terms.map(term => (
                <div key={term.id} className="p-3 rounded-xl border border-[#1e2d45] bg-[#0a1119] space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm text-slate-200">{term.term}</div>
                      <div className="text-xs text-slate-500">{term.group_name} · {term.scope}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Toggle
                        checked={term.enabled}
                        onChange={async () => {
                          const upd = await api.sourceSearchTerms.update(term.id, { enabled: !term.enabled });
                          setTerms(prev => prev.map(t => t.id === term.id ? upd : t));
                        }}
                      />
                      <button
                        className="p-1.5 rounded border border-red-500/30 text-red-400"
                        onClick={async () => {
                          await api.sourceSearchTerms.delete(term.id);
                          setTerms(prev => prev.filter(t => t.id !== term.id));
                        }}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {sources.map(s => {
                      const selected = term.source_names.includes(s.name);
                      return (
                        <button
                          key={`${term.id}-${s.id}`}
                          onClick={async () => {
                            const next = selected ? term.source_names.filter(n => n !== s.name) : [...term.source_names, s.name];
                            const upd = await api.sourceSearchTerms.update(term.id, { source_names: next });
                            setTerms(prev => prev.map(t => t.id === term.id ? upd : t));
                          }}
                          className={`px-2 py-1 rounded text-xs border ${selected ? "bg-cyan-500/10 border-cyan-500/40 text-cyan-300" : "border-[#1e2d45] text-slate-500"}`}
                        >
                          {s.name}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
