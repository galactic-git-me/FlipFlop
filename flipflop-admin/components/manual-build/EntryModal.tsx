// pc-flipper/components/manual-build/EntryModal.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { X, Search } from "lucide-react";
import { api, BuildComponent } from "@/lib/api";

interface CatalogueResult {
  id: number;
  name: string;
  category: string;
  price: number | null;
  image_url: string | null;
  source_url: string | null;
  source_site: string | null;
}

interface EntryModalProps {
  slot: string;
  onConfirm: (component: BuildComponent) => void;
  onClose: () => void;
}

export function EntryModal({ slot, onConfirm, onClose }: EntryModalProps) {
  const [tab, setTab] = useState<"catalogue" | "manual">("catalogue");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CatalogueResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState<CatalogueResult | null>(null);
  const [pricePaid, setPricePaid] = useState("");

  // Manual tab state
  const [manualName, setManualName] = useState("");
  const [manualPrice, setManualPrice] = useState("");

  const search = useCallback(async (q: string) => {
    if (!q.trim()) { setResults([]); return; }
    setSearching(true);
    try {
      const all = await api.parts.list() as CatalogueResult[];
      const lower = q.toLowerCase();
      setResults(all.filter((p) => p.name.toLowerCase().includes(lower)).slice(0, 12));
    } catch {
      setResults([]);
    }
    setSearching(false);
  }, []);

  useEffect(() => {
    const t = setTimeout(() => search(query), 300);
    return () => clearTimeout(t);
  }, [query, search]);

  function handleCatalogueConfirm() {
    if (!selected) return;
    onConfirm({
      slot,
      name: selected.name,
      price_paid: parseFloat(pricePaid) || selected.price || 0,
      source: "catalogue",
      part_id: selected.id,
      listing_url: selected.source_url ?? undefined,
      image_url: selected.image_url ?? undefined,
    });
  }

  function handleManualConfirm() {
    if (!manualName.trim()) return;
    onConfirm({
      slot,
      name: manualName.trim(),
      price_paid: parseFloat(manualPrice) || 0,
      source: "manual",
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="relative w-full max-w-md rounded-xl border border-slate-700 bg-[#0b1220] shadow-2xl p-0 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 pt-4 pb-3 border-b border-slate-800">
          <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wide">
            Add {slot}
          </h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-800">
          {(["catalogue", "manual"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2 text-xs font-mono uppercase transition-colors ${
                tab === t
                  ? "text-[#00dc82] border-b-2 border-[#00dc82]"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {t === "catalogue" ? "From Catalogue" : "Enter Manually"}
            </button>
          ))}
        </div>

        <div className="p-4">
          {tab === "catalogue" ? (
            <div className="space-y-3">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-slate-500" />
                <input
                  autoFocus
                  type="text"
                  placeholder="Search parts catalogue…"
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setSelected(null); }}
                  className="w-full pl-8 pr-3 py-2 text-sm bg-[#0d1a2a] border border-slate-700 rounded-md text-slate-200 placeholder-slate-500 focus:border-[#00dc82] focus:outline-none"
                />
              </div>

              {searching && (
                <p className="text-xs text-slate-500 text-center py-2">Searching…</p>
              )}

              {!searching && results.length === 0 && query.length > 1 && (
                <p className="text-xs text-slate-500 text-center py-2">
                  No catalogue matches —{" "}
                  <button onClick={() => setTab("manual")} className="text-cyan-400 hover:underline">
                    enter manually instead
                  </button>
                </p>
              )}

              <div className="space-y-1 max-h-48 overflow-y-auto">
                {results.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => { setSelected(r); setPricePaid(String(r.price ?? "")); }}
                    className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-left transition-colors ${
                      selected?.id === r.id
                        ? "bg-[#00dc82]/10 border border-[#00dc82]/30"
                        : "hover:bg-slate-800 border border-transparent"
                    }`}
                  >
                    {r.image_url ? (
                      <img src={r.image_url} alt="" className="w-8 h-8 rounded object-cover" />
                    ) : (
                      <div className="w-8 h-8 rounded bg-slate-700" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-slate-200 truncate">{r.name}</p>
                      <p className="text-[10px] text-slate-500">{r.source_site} · {r.category}</p>
                    </div>
                    {r.price != null && (
                      <span className="text-xs text-[#00dc82] font-mono">£{r.price}</span>
                    )}
                  </button>
                ))}
              </div>

              {selected && (
                <div className="flex items-center gap-2 pt-2 border-t border-slate-800">
                  <span className="text-xs text-slate-400">Price paid £</span>
                  <input
                    type="number"
                    value={pricePaid}
                    onChange={(e) => setPricePaid(e.target.value)}
                    className="flex-1 px-2 py-1 text-sm bg-[#0d1a2a] border border-slate-700 rounded text-slate-200 focus:border-[#00dc82] focus:outline-none"
                    min={0}
                    step={0.01}
                    autoFocus
                  />
                  <button
                    onClick={handleCatalogueConfirm}
                    className="px-3 py-1 text-xs font-semibold bg-[#00dc82] text-[#04120d] rounded hover:bg-[#00b86d] transition-colors"
                  >
                    Add
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Component name</label>
                <input
                  autoFocus
                  type="text"
                  placeholder={`e.g. RTX 3060 12GB`}
                  value={manualName}
                  onChange={(e) => setManualName(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-[#0d1a2a] border border-slate-700 rounded-md text-slate-200 placeholder-slate-500 focus:border-[#00dc82] focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Price paid (£)</label>
                <input
                  type="number"
                  placeholder="0.00"
                  value={manualPrice}
                  onChange={(e) => setManualPrice(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-[#0d1a2a] border border-slate-700 rounded-md text-slate-200 placeholder-slate-500 focus:border-[#00dc82] focus:outline-none"
                  min={0}
                  step={0.01}
                />
              </div>
              <button
                onClick={handleManualConfirm}
                disabled={!manualName.trim()}
                className="w-full py-2 text-xs font-semibold bg-[#00dc82] text-[#04120d] rounded hover:bg-[#00b86d] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Add Component
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
