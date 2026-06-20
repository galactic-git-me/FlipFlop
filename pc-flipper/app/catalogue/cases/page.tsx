"use client";

import { useEffect, useState, useCallback } from "react";
import { Plus, RefreshCw, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface CaseItem {
  id: number;
  name: string;
  brand: string;
  form_factor: string;
  images: string[];
  rrp_gbp: number;
  is_transparent_panel: boolean;
  status: string;
  notes: string | null;
}

const FORM_FACTORS = ["atx", "matx", "itx"];

export default function CaseCataloguePage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({
    name: "", brand: "", form_factor: "atx", rrp_gbp: 0,
    is_transparent_panel: true, notes: "", images: "",
  });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.catalogue.cases();
      setCases(data as CaseItem[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleStatus = async (c: CaseItem) => {
    await api.catalogue.updateCase(c.id, {
      status: c.status === "active" ? "hidden" : "active",
    });
    await load();
  };

  const submitAdd = async () => {
    setSaving(true);
    try {
      await api.catalogue.createCase({
        ...form,
        rrp_gbp: Number(form.rrp_gbp),
        images: form.images.split("\n").map(s => s.trim()).filter(Boolean),
      });
      setForm({ name: "", brand: "", form_factor: "atx", rrp_gbp: 0, is_transparent_panel: true, notes: "", images: "" });
      setShowAdd(false);
      await load();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Case Catalogue</h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </Button>
          <Button size="sm" onClick={() => setShowAdd(!showAdd)}>
            <Plus className="w-3.5 h-3.5 mr-1.5" />
            Add Case
          </Button>
        </div>
      </div>

      {showAdd && (
        <div className="border rounded-lg p-4 mb-6 bg-card space-y-3">
          <h2 className="font-semibold text-sm">Add New Case</h2>
          <div className="grid grid-cols-2 gap-3">
            <input
              className="border rounded px-2 py-1.5 text-sm bg-background"
              placeholder="Case name (e.g. O11 Dynamic EVO)"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            />
            <input
              className="border rounded px-2 py-1.5 text-sm bg-background"
              placeholder="Brand (e.g. Lian Li)"
              value={form.brand}
              onChange={e => setForm(f => ({ ...f, brand: e.target.value }))}
            />
            <select
              className="border rounded px-2 py-1.5 text-sm bg-background"
              value={form.form_factor}
              onChange={e => setForm(f => ({ ...f, form_factor: e.target.value }))}
            >
              {FORM_FACTORS.map(ff => <option key={ff} value={ff}>{ff.toUpperCase()}</option>)}
            </select>
            <input
              type="number"
              className="border rounded px-2 py-1.5 text-sm bg-background"
              placeholder="RRP £"
              value={form.rrp_gbp || ""}
              onChange={e => setForm(f => ({ ...f, rrp_gbp: Number(e.target.value) }))}
            />
          </div>
          <textarea
            className="w-full border rounded px-2 py-1.5 text-sm bg-background"
            placeholder="Image URLs (one per line)"
            rows={3}
            value={form.images}
            onChange={e => setForm(f => ({ ...f, images: e.target.value }))}
          />
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_transparent_panel}
                onChange={e => setForm(f => ({ ...f, is_transparent_panel: e.target.checked }))}
              />
              Transparent panel
            </label>
            <input
              className="flex-1 border rounded px-2 py-1.5 text-sm bg-background"
              placeholder="Notes (optional)"
              value={form.notes}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
            />
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={submitAdd} disabled={saving || !form.name || !form.brand}>
              {saving ? "Saving…" : "Add Case"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setShowAdd(false)}>Cancel</Button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {cases.map(c => (
          <div key={c.id} className={`border rounded-lg p-3 bg-card ${c.status === "hidden" ? "opacity-50" : ""}`}>
            {c.images[0] && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={c.images[0]} alt={c.name} className="w-full h-32 object-contain mb-2 rounded" />
            )}
            <p className="font-semibold text-sm truncate">{c.name}</p>
            <p className="text-xs text-muted-foreground">{c.brand} · {c.form_factor.toUpperCase()}</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              £{c.rrp_gbp} RRP · {c.is_transparent_panel ? "Glass panel" : "Solid panel"}
            </p>
            <Button
              size="sm"
              variant="ghost"
              className="mt-2 w-full"
              onClick={() => toggleStatus(c)}
            >
              {c.status === "active"
                ? <><EyeOff className="w-3 h-3 mr-1.5" />Hide</>
                : <><Eye className="w-3 h-3 mr-1.5" />Show</>}
            </Button>
          </div>
        ))}
      </div>

      {!loading && cases.length === 0 && (
        <p className="text-center text-muted-foreground text-sm py-12">
          No cases yet — add the first one above.
        </p>
      )}
    </div>
  );
}
