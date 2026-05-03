"use client";

import { useEffect, useState } from "react";
import { Search, Save, RotateCcw, Target, DollarSign, Cpu, HardDrive, Monitor, Bot, ShoppingCart, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

type Intent = "flip_gaming" | "flip_workstation" | "personal";
type Condition = "new" | "used" | "refurb";

interface Config {
  id?: number;
  min_price: number;
  max_price: number;
  conditions: Condition[];
  cpu_types: string[];
  ram_min_gb: number;
  ram_types: string[];
  require_storage: boolean;
  require_gpu: boolean;
  keywords: string[];
  exclude_keywords: string[];
  intent: Intent;
  gem_keywords: string[];
  auto_buy_enabled: boolean;
  auto_buy_max_price: number;
  auto_buy_min_score: number;
}

const DEFAULT_CONFIG: Config = {
  min_price: 0,
  max_price: 150,
  conditions: ["used"],
  cpu_types: ["Intel i5", "Intel i7", "AMD Ryzen 5"],
  ram_min_gb: 8,
  ram_types: ["DDR4"],
  require_storage: false,
  require_gpu: false,
  keywords: ["PC", "desktop", "tower", "computer"],
  exclude_keywords: ["Mac", "iMac", "Apple", "Chromebook"],
  intent: "flip_gaming",
  gem_keywords: ["no hdd", "untested", "collection only", "for parts", "no gpu", "spares"],
  auto_buy_enabled: false,
  auto_buy_max_price: 100,
  auto_buy_min_score: 75,
};

const INTENT_OPTIONS: { value: Intent; label: string; desc: string }[] = [
  { value: "flip_gaming", label: "Flip Gaming", desc: "Target gaming PCs for resale to gamers" },
  { value: "flip_workstation", label: "Flip Workstation", desc: "Target workstations/Xeons for pro resale" },
  { value: "personal", label: "Personal Use", desc: "Find a good deal for yourself" },
];

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

export default function SearchConfigPage() {
  const [config, setConfig] = useState<Config>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [newKeyword, setNewKeyword] = useState("");
  const [newExclude, setNewExclude] = useState("");

  useEffect(() => {
    api.config.get().then(data => {
      if (data) setConfig(prev => ({ ...prev, ...(data as Partial<Config>) }));
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.config.update(config as unknown as Record<string, unknown>);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally {
      setSaving(false);
    }
  };

  const toggleCondition = (c: Condition) => {
    setConfig(p => ({
      ...p,
      conditions: p.conditions.includes(c) ? p.conditions.filter(x => x !== c) : [...p.conditions, c],
    }));
  };

  const addKeyword = () => {
    if (newKeyword.trim()) {
      setConfig(p => ({ ...p, keywords: [...p.keywords, newKeyword.trim()] }));
      setNewKeyword("");
    }
  };

  const addExclude = () => {
    if (newExclude.trim()) {
      setConfig(p => ({ ...p, exclude_keywords: [...p.exclude_keywords, newExclude.trim()] }));
      setNewExclude("");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500 text-sm gap-2">
        <RefreshCw className="w-4 h-4 animate-spin" /> Loading config…
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Search className="w-5 h-5 text-slate-400" /> Search Config
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">Define your target listing criteria — drives all swarm searches</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setConfig(DEFAULT_CONFIG)}>
            <RotateCcw className="w-3.5 h-3.5" /> Reset
          </Button>
          <Button variant="primary" size="sm" onClick={save} disabled={saving}>
            <Save className="w-3.5 h-3.5" />
            {saving ? "Saving…" : saved ? "Saved ✓" : "Save Config"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Flip Intent */}
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Target className="w-3.5 h-3.5 text-[#00dc82]" /> Flip Intent</CardTitle></CardHeader>
          <CardContent className="space-y-2 pt-0">
            {INTENT_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setConfig(p => ({ ...p, intent: opt.value }))}
                className={`w-full flex items-start gap-3 p-3 rounded-xl border text-left transition-all ${
                  config.intent === opt.value
                    ? "border-[#00dc82]/40 bg-[#00dc82]/8"
                    : "border-[#1e2d45] bg-[#0a1119] hover:border-slate-600"
                }`}
              >
                <div className={`w-4 h-4 rounded-full border-2 mt-0.5 flex-shrink-0 transition-colors ${
                  config.intent === opt.value ? "border-[#00dc82] bg-[#00dc82]" : "border-slate-600"
                }`} />
                <div>
                  <div className="text-sm font-medium text-slate-200">{opt.label}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{opt.desc}</div>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Price & Condition */}
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><DollarSign className="w-3.5 h-3.5 text-[#00dc82]" /> Price Range</CardTitle></CardHeader>
          <CardContent className="space-y-4 pt-0">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-500 mb-1.5 block">Min Price (£)</label>
                <input
                  type="number"
                  value={config.min_price}
                  onChange={e => setConfig(p => ({ ...p, min_price: Number(e.target.value) }))}
                  className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 outline-none focus:border-[#00dc82]/50"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1.5 block">Max Price (£)</label>
                <input
                  type="number"
                  value={config.max_price}
                  onChange={e => setConfig(p => ({ ...p, max_price: Number(e.target.value) }))}
                  className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 outline-none focus:border-[#00dc82]/50"
                />
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-2 block">Condition</label>
              <div className="flex gap-2">
                {(["new", "used", "refurb"] as Condition[]).map(c => (
                  <button
                    key={c}
                    onClick={() => toggleCondition(c)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border capitalize transition-all ${
                      config.conditions.includes(c)
                        ? "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/30"
                        : "bg-[#0a1119] text-slate-500 border-[#1e2d45] hover:border-slate-600"
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-2 block">Min RAM (GB)</label>
              <div className="flex gap-2">
                {[4, 8, 16, 32].map(gb => (
                  <button
                    key={gb}
                    onClick={() => setConfig(p => ({ ...p, ram_min_gb: gb }))}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                      config.ram_min_gb === gb
                        ? "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/30"
                        : "bg-[#0a1119] text-slate-500 border-[#1e2d45] hover:border-slate-600"
                    }`}
                  >
                    {gb}GB
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Hardware Requirements */}
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Cpu className="w-3.5 h-3.5 text-blue-400" /> Hardware Requirements</CardTitle></CardHeader>
          <CardContent className="space-y-4 pt-0">
            <div>
              <label className="text-xs text-slate-500 mb-2 block">RAM Types</label>
              <div className="flex gap-2">
                {["DDR3", "DDR4", "DDR5"].map(t => (
                  <button
                    key={t}
                    onClick={() => setConfig(p => ({
                      ...p,
                      ram_types: p.ram_types.includes(t) ? p.ram_types.filter(x => x !== t) : [...p.ram_types, t]
                    }))}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                      config.ram_types.includes(t)
                        ? "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/30"
                        : "bg-[#0a1119] text-slate-500 border-[#1e2d45]"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              {[
                { key: "require_storage" as const, icon: HardDrive, label: "Require Storage", desc: "Only show listings with HDD/SSD" },
                { key: "require_gpu" as const, icon: Monitor, label: "Require GPU", desc: "Only show listings with dedicated GPU" },
              ].map(({ key, icon: Icon, label, desc }) => (
                <div key={key} className="flex items-center justify-between p-3 bg-[#0a1119] rounded-xl border border-[#1e2d45]">
                  <div>
                    <div className="text-sm text-slate-300 font-medium flex items-center gap-2">
                      <Icon className="w-3.5 h-3.5 text-slate-500" /> {label}
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">{desc}</div>
                  </div>
                  <Toggle checked={config[key]} onChange={() => setConfig(p => ({ ...p, [key]: !p[key] }))} />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Keywords */}
        <Card>
          <CardHeader><CardTitle>Keyword Configuration</CardTitle></CardHeader>
          <CardContent className="space-y-4 pt-0">
            <div>
              <label className="text-xs text-slate-500 mb-2 block">Target Keywords</label>
              <div className="flex gap-2 mb-2">
                <input
                  value={newKeyword}
                  onChange={e => setNewKeyword(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && addKeyword()}
                  placeholder="Add keyword…"
                  className="flex-1 px-3 py-1.5 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-xs text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50"
                />
                <Button variant="secondary" size="sm" onClick={addKeyword}>Add</Button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {config.keywords.map(kw => (
                  <button key={kw} onClick={() => setConfig(p => ({ ...p, keywords: p.keywords.filter(k => k !== kw) }))}
                    className="flex items-center gap-1 px-2 py-0.5 bg-blue-500/10 text-blue-400 border border-blue-500/25 rounded-md text-xs hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/25 transition-colors">
                    {kw} ×
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-2 block">Gem Heuristics (auto-boost score)</label>
              <div className="flex flex-wrap gap-1.5">
                {config.gem_keywords.map(kw => (
                  <span key={kw} className="px-2 py-0.5 bg-[#00dc82]/10 text-[#00dc82] border border-[#00dc82]/25 rounded-md text-xs">
                    💎 {kw}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-2 block">Exclude Keywords</label>
              <div className="flex gap-2 mb-2">
                <input
                  value={newExclude}
                  onChange={e => setNewExclude(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && addExclude()}
                  placeholder="Add exclusion…"
                  className="flex-1 px-3 py-1.5 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-xs text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50"
                />
                <Button variant="secondary" size="sm" onClick={addExclude}>Add</Button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {config.exclude_keywords.map(kw => (
                  <button key={kw} onClick={() => setConfig(p => ({ ...p, exclude_keywords: p.exclude_keywords.filter(k => k !== kw) }))}
                    className="flex items-center gap-1 px-2 py-0.5 bg-red-500/10 text-red-400 border border-red-500/25 rounded-md text-xs hover:bg-slate-700/50 hover:text-slate-400 transition-colors">
                    {kw} ×
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Auto-Buy — Hermes Agent */}
        <Card className="xl:col-span-2 border-cyan-400/15">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="w-3.5 h-3.5 text-cyan-400" /> Hermes Auto-Buy
              <span className="ml-2 text-[10px] px-2 py-0.5 rounded-full bg-cyan-400/10 text-cyan-400 border border-cyan-400/25 font-medium uppercase tracking-wider">
                Autonomous
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="p-4 rounded-xl border border-cyan-400/20 bg-cyan-400/5 mb-4">
              <p className="text-xs text-slate-400 leading-relaxed">
                When enabled, Hermes will automatically queue purchases for listings that exceed your minimum score threshold and stay within your price cap.
                Purchases are flagged for your approval unless you enable fully autonomous mode in Settings.
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex items-center justify-between p-3 bg-[#0a1119] rounded-xl border border-[#1e2d45] md:col-span-3">
                <div>
                  <div className="text-sm text-slate-300 font-medium flex items-center gap-2">
                    <Bot className="w-3.5 h-3.5 text-cyan-400" /> Enable Auto-Buy
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">Hermes monitors gems and queues purchases automatically</div>
                </div>
                <Toggle checked={config.auto_buy_enabled} onChange={() => setConfig(p => ({ ...p, auto_buy_enabled: !p.auto_buy_enabled }))} />
              </div>
              <div className={`transition-opacity ${config.auto_buy_enabled ? "opacity-100" : "opacity-40 pointer-events-none"}`}>
                <label className="text-xs text-slate-500 mb-1.5 block">Max Auto-Buy Price (£)</label>
                <input
                  type="number"
                  value={config.auto_buy_max_price}
                  onChange={e => setConfig(p => ({ ...p, auto_buy_max_price: Number(e.target.value) }))}
                  className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 outline-none focus:border-cyan-400/50"
                />
                <p className="text-[10px] text-slate-600 mt-1">Hermes will not bid above this price</p>
              </div>
              <div className={`transition-opacity ${config.auto_buy_enabled ? "opacity-100" : "opacity-40 pointer-events-none"}`}>
                <label className="text-xs text-slate-500 mb-1.5 block">Min Gem Score to Trigger</label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min={50}
                    max={95}
                    step={5}
                    value={config.auto_buy_min_score}
                    onChange={e => setConfig(p => ({ ...p, auto_buy_min_score: Number(e.target.value) }))}
                    className="flex-1 accent-cyan-400"
                  />
                  <span className="text-sm font-bold text-cyan-400 w-8 text-right">{config.auto_buy_min_score}</span>
                </div>
                <p className="text-[10px] text-slate-600 mt-1">Only auto-buy listings scoring above this</p>
              </div>
              <div className={`transition-opacity ${config.auto_buy_enabled ? "opacity-100" : "opacity-40 pointer-events-none"}`}>
                <div className="p-3 bg-cyan-400/8 rounded-xl border border-cyan-400/20">
                  <div className="text-xs text-cyan-400 font-semibold mb-1">Hermes is watching</div>
                  <div className="text-xs text-slate-500">
                    Will auto-queue listings scoring ≥ {config.auto_buy_min_score} under £{config.auto_buy_max_price}
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
