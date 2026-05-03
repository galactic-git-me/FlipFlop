"use client";

import { useEffect, useState } from "react";
import { Settings, Save, Bot, Layers, RefreshCw, ShieldCheck, Cpu } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

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
}

const DEFAULTS: AppSettings = {
  max_concurrent_flips: 1,
  auto_buy_autonomous: false,
  auto_buy_daily_limit: 3,
  ollama_base_url: "http://localhost:11434",
  ollama_model: "gemma3:4b",
  openrouter_api_key: "",
  openrouter_primary_model: "google/gemma-4-31b-it:free",
  image_gen_enabled: true,
  image_gen_provider: "pollinations",
  default_sell_platform: "ebay",
  ebay_app_id: "",
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

function SettingRow({ label, desc, children }: { label: string; desc?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 p-3 bg-[#0a1119] rounded-xl border border-[#1e2d45]">
      <div>
        <div className="text-sm text-slate-300 font-medium">{label}</div>
        {desc && <div className="text-xs text-slate-600 mt-0.5">{desc}</div>}
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>(DEFAULTS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.settings.get().then(data => {
      if (data) setSettings(prev => ({ ...prev, ...(data as Partial<AppSettings>) }));
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.settings.update(settings as unknown as Record<string, unknown>);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally {
      setSaving(false);
    }
  };

  const set = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    setSettings(prev => ({ ...prev, [key]: value }));
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
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Settings className="w-5 h-5 text-slate-400" /> Settings
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">Platform-wide configuration — Hermes, auto-buy limits, image generation</p>
        </div>
        <Button variant="primary" size="sm" onClick={save} disabled={saving}>
          <Save className="w-3.5 h-3.5" />
          {saving ? "Saving…" : saved ? "Saved ✓" : "Save Settings"}
        </Button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Flip Management */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Layers className="w-3.5 h-3.5 text-[#00dc82]" /> Flip Management
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pt-0">
            <div className="p-3 bg-[#0a1119] rounded-xl border border-[#1e2d45]">
              <label className="text-xs text-slate-500 mb-2 block">Max Concurrent Flips</label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min={1}
                  max={10}
                  value={settings.max_concurrent_flips}
                  onChange={e => set("max_concurrent_flips", Number(e.target.value))}
                  className="flex-1 accent-[#00dc82]"
                />
                <span className="text-xl font-black text-[#00dc82] w-6 text-right">
                  {settings.max_concurrent_flips}
                </span>
              </div>
              <p className="text-xs text-slate-600 mt-1">
                {settings.max_concurrent_flips === 1
                  ? "Single flip at a time — conservative approach"
                  : `Up to ${settings.max_concurrent_flips} simultaneous flips — higher capital required`}
              </p>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-2 block">Default Sell Platform</label>
              <div className="flex gap-2">
                {["ebay", "facebook", "gumtree"].map(p => (
                  <button
                    key={p}
                    onClick={() => set("default_sell_platform", p)}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-medium border capitalize transition-all ${
                      settings.default_sell_platform === p
                        ? "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/30"
                        : "bg-[#0a1119] text-slate-500 border-[#1e2d45]"
                    }`}
                  >
                    {p === "ebay" ? "eBay" : p.charAt(0).toUpperCase() + p.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Hermes AI Model */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" /> Hermes AI Model
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pt-0">
            <div className="p-2.5 bg-cyan-400/5 border border-cyan-400/15 rounded-xl text-[11px] text-slate-400 leading-relaxed">
              Priority: <span className="text-cyan-300 font-mono">OpenRouter primary</span> → OpenRouter fallbacks → Ollama local → Claude Haiku
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1.5 block">OpenRouter API Key</label>
              <input
                type="password"
                value={settings.openrouter_api_key}
                onChange={e => set("openrouter_api_key", e.target.value)}
                placeholder="sk-or-…"
                className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 font-mono outline-none focus:border-cyan-400/50"
              />
              <p className="text-[10px] text-slate-600 mt-1">Get a free key at <span className="text-cyan-400">openrouter.ai</span> — required for OpenRouter models</p>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1.5 block">Primary Model (OpenRouter)</label>
              <input
                value={settings.openrouter_primary_model}
                onChange={e => set("openrouter_primary_model", e.target.value)}
                placeholder="google/gemma-4-31b-it:free"
                className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 font-mono outline-none focus:border-cyan-400/50"
              />
              <p className="text-[10px] text-slate-600 mt-1">Used for all chats, scoring, and listing generation — append <code className="text-cyan-400">:free</code> for free tier</p>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1.5 block">Ollama Model (local fallback)</label>
              <div className="flex gap-2">
                <input
                  value={settings.ollama_base_url}
                  onChange={e => set("ollama_base_url", e.target.value)}
                  placeholder="http://localhost:11434"
                  className="w-1/2 px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 font-mono outline-none focus:border-cyan-400/50"
                />
                <input
                  value={settings.ollama_model}
                  onChange={e => set("ollama_model", e.target.value)}
                  placeholder="gemma3:4b"
                  className="w-1/2 px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 font-mono outline-none focus:border-cyan-400/50"
                />
              </div>
              <p className="text-[10px] text-slate-600 mt-1">Used when OpenRouter is unavailable. Run <code className="text-cyan-400">ollama pull gemma3:4b</code> on your Ollama host.</p>
            </div>
          </CardContent>
        </Card>

        {/* Auto-Buy Safety */}
        <Card className="border-yellow-400/10">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="w-3.5 h-3.5 text-yellow-400" /> Auto-Buy Safety Controls
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pt-0">
            <div className="p-3 bg-yellow-400/5 border border-yellow-400/15 rounded-xl text-xs text-slate-400 leading-relaxed">
              Autonomous mode allows Hermes to purchase units without manual approval. This requires valid eBay API credentials.
              Start with queue-only mode until you trust the scoring.
            </div>
            <SettingRow
              label="Fully Autonomous Mode"
              desc="Hermes purchases without approval — requires eBay API"
            >
              <Toggle checked={settings.auto_buy_autonomous} onChange={() => set("auto_buy_autonomous", !settings.auto_buy_autonomous)} />
            </SettingRow>
            <div className="p-3 bg-[#0a1119] rounded-xl border border-[#1e2d45]">
              <label className="text-xs text-slate-500 mb-2 block">Max Auto-Buys per Day</label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min={1}
                  max={10}
                  value={settings.auto_buy_daily_limit}
                  onChange={e => set("auto_buy_daily_limit", Number(e.target.value))}
                  className="flex-1 accent-yellow-400"
                />
                <span className="text-lg font-black text-yellow-400 w-6 text-right">{settings.auto_buy_daily_limit}</span>
              </div>
              <p className="text-xs text-slate-600 mt-1">Hard cap on purchases regardless of available gems</p>
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1.5 block">eBay App ID (for auto-buy)</label>
              <input
                type="password"
                value={settings.ebay_app_id}
                onChange={e => set("ebay_app_id", e.target.value)}
                placeholder="eBay-AppID-…"
                className="w-full px-3 py-2 bg-[#0a1119] border border-[#1e2d45] rounded-lg text-sm text-slate-300 font-mono outline-none focus:border-yellow-400/50"
              />
            </div>
          </CardContent>
        </Card>

        {/* Image Generation */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="w-3.5 h-3.5 text-pink-400" /> AI Image Generation
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pt-0">
            <SettingRow
              label="Enable Image Generation"
              desc="Generate AI product photos for selling listings"
            >
              <Toggle checked={settings.image_gen_enabled} onChange={() => set("image_gen_enabled", !settings.image_gen_enabled)} />
            </SettingRow>
            <div>
              <label className="text-xs text-slate-500 mb-2 block">Image Provider</label>
              <div className="flex gap-2">
                {[
                  { value: "pollinations", label: "Pollinations.ai", desc: "Free · No API key" },
                  { value: "stability", label: "Stability AI", desc: "Paid · Higher quality" },
                ].map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => set("image_gen_provider", opt.value)}
                    className={`flex-1 p-2.5 rounded-xl border text-left transition-all ${
                      settings.image_gen_provider === opt.value
                        ? "border-pink-400/40 bg-pink-400/8"
                        : "border-[#1e2d45] bg-[#0a1119] hover:border-slate-600"
                    }`}
                  >
                    <div className="text-xs font-medium text-slate-200">{opt.label}</div>
                    <div className="text-[10px] text-slate-500 mt-0.5">{opt.desc}</div>
                  </button>
                ))}
              </div>
            </div>
            <div className="p-3 bg-[#0a1119] rounded-xl border border-[#1e2d45] text-xs text-slate-500 leading-relaxed">
              Images are generated using Stable Diffusion with product-photography prompts based on your PC specs and case theme.
              Each flip gets a hero shot, side view, and detail shot — ready to copy-paste into eBay listings.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
