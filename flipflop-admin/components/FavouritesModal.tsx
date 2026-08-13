"use client";

import { useEffect, useState } from "react";
import { X, Heart, Trash2, Search, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Favourite, FavouriteMatrixRow } from "@/lib/types";
import { VENDOR_ORDER, VENDOR_META } from "@/lib/vendors";
import { VendorLogo } from "./VendorLogo";

const CATEGORY_OPTIONS = ["cpu", "gpu", "ram", "motherboard", "ssd", "psu", "cooler", "case", "other"];

function classificationRing(classification: string): string {
  if (classification === "SUPER_GEM") return "ring-1 ring-amber-400/70 bg-amber-500/10";
  if (classification === "GEM") return "ring-1 ring-blue-400/60 bg-blue-500/10";
  return "";
}

function ProductsList({
  products,
  selectedCpk,
  onSelect,
}: {
  products: Array<{ cpk: string; lowest_price: number; title: string }>;
  selectedCpk: string | null;
  onSelect: (cpk: string) => void;
}) {
  if (products.length === 0) return null;

  return (
    <div className="space-y-2 mt-2 p-2 rounded-lg bg-white/3 border border-white/8">
      <div className="text-xs uppercase tracking-wide text-slate-400 font-semibold">Or select a product:</div>
      <div className="space-y-1 max-h-[200px] overflow-y-auto">
        {products.map((product) => (
          <button
            key={product.cpk}
            onClick={() => onSelect(product.cpk)}
            className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${
              selectedCpk === product.cpk
                ? "bg-rose-500/30 border border-rose-400/50 text-rose-200"
                : "bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10"
            }`}
          >
            <div className="font-medium truncate">{product.title}</div>
            <div className="text-slate-400 text-[10px]">£{product.lowest_price.toFixed(2)}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

function MatrixTable({ row }: { row: FavouriteMatrixRow }) {
  const present = VENDOR_ORDER.filter((v) => row.vendors[v]);
  if (present.length === 0) {
    return <div className="text-xs text-slate-500 py-2">No current listings match this search.</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="text-xs">
        <thead>
          <tr>
            {present.map((vendor) => (
              <th key={vendor} className="px-3 py-1 text-center">
                <div className="flex flex-col items-center gap-1">
                  <VendorLogo vendor={vendor} />
                  <span className="text-slate-400">{VENDOR_META[vendor]?.label ?? vendor}</span>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            {present.map((vendor) => {
              const cell = row.vendors[vendor];
              return (
                <td key={vendor} className="px-1 py-1">
                  <a
                    href={cell.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`block rounded-md px-3 py-2 text-center font-semibold text-slate-100 hover:brightness-110 transition ${classificationRing(cell.classification)}`}
                    title={cell.classification || undefined}
                  >
                    £{cell.lowest_price.toFixed(2)}
                  </a>
                </td>
              );
            })}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function FavouritesModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [previewCategory, setPreviewCategory] = useState<string>("other");
  const [previewResult, setPreviewResult] = useState<FavouriteMatrixRow | null>(null);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selectedProductCpk, setSelectedProductCpk] = useState<string | null>(null);

  const [favourites, setFavourites] = useState<Favourite[]>([]);
  const [matrix, setMatrix] = useState<Record<number, FavouriteMatrixRow>>({});
  const [loadingList, setLoadingList] = useState(false);

  const refreshFavourites = async () => {
    setLoadingList(true);
    try {
      const [{ items }, matrixRows] = await Promise.all([api.favourites.list(), api.favourites.matrix()]);
      setFavourites(items);
      setMatrix(matrixRows);
    } catch {
      // keep whatever we had; modal stays usable
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    if (open) void refreshFavourites();
  }, [open]);

  // Debounced live fuzzy search against current listings as the user types.
  useEffect(() => {
    if (!query.trim()) {
      setPreviewResult(null);
      setSelectedProductCpk(null);
      return;
    }
    setSearching(true);
    const handle = setTimeout(async () => {
      try {
        const result = await api.favourites.search(query.trim());
        setPreviewResult(result);
        setPreviewCategory(result.category ?? "other");
        setSelectedProductCpk(null);
      } catch {
        setPreviewResult(null);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(handle);
  }, [query]);

  const handleSave = async () => {
    if (!query.trim() && !selectedProductCpk) return;
    setSaving(true);
    try {
      await api.favourites.create(
        selectedProductCpk ? undefined : query.trim(),
        previewCategory,
        selectedProductCpk || undefined
      );
      setQuery("");
      setSelectedProductCpk(null);
      setPreviewResult(null);
      await refreshFavourites();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    await api.favourites.remove(id);
    await refreshFavourites();
  };

  const handleCategoryChange = async (id: number, category: string) => {
    await api.favourites.update(id, category);
    await refreshFavourites();
  };

  if (!open) return null;

  const grouped = favourites.reduce<Record<string, Favourite[]>>((acc, fav) => {
    const key = fav.category || "other";
    acc[key] = acc[key] ? [...acc[key], fav] : [fav];
    return acc;
  }, {});

  return (
    <div className="fixed inset-0 z-[90] flex items-start justify-center pt-16 bg-black/60" onClick={onClose}>
      <div
        className="w-[min(920px,92vw)] max-h-[80vh] rounded-xl border border-white/10 bg-[#0b111d]/98 backdrop-blur-md shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 pt-4 pb-3 border-b border-white/8 shrink-0">
          <div className="flex items-center gap-2">
            <Heart className="h-4 w-4 text-rose-400" />
            <span className="text-sm uppercase tracking-wider text-slate-200 font-semibold">Favourites</span>
          </div>
          <button onClick={onClose} aria-label="Close" className="text-slate-400 hover:text-slate-200">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-4 py-3 border-b border-white/8 shrink-0 space-y-2">
          <div className="flex items-center gap-2">
            <div className="flex-1 flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2">
              <Search className="h-4 w-4 text-slate-500" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search a component to favourite (e.g. RTX 3080)..."
                className="flex-1 bg-transparent text-sm text-slate-100 placeholder:text-slate-500 outline-none"
              />
              {searching && <Loader2 className="h-4 w-4 text-slate-500 animate-spin" />}
            </div>
            <select
              value={previewCategory}
              onChange={(e) => setPreviewCategory(e.target.value)}
              className="rounded-lg border border-white/10 bg-white/5 px-2 py-2 text-xs text-slate-200"
            >
              {CATEGORY_OPTIONS.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <button
              onClick={handleSave}
              disabled={(!query.trim() && !selectedProductCpk) || saving}
              className="px-3 py-2 rounded-lg text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30 hover:bg-rose-500/30 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? "Saving…" : selectedProductCpk ? "Save Product" : "Save Search"}
            </button>
          </div>
          {previewResult && (
            <div className="space-y-2">
              <MatrixTable row={previewResult} />
              <ProductsList
                products={previewResult.products}
                selectedCpk={selectedProductCpk}
                onSelect={setSelectedProductCpk}
              />
            </div>
          )}
        </div>

        <div className="overflow-y-auto flex-1 p-4 space-y-4">
          {loadingList && favourites.length === 0 ? (
            <div className="text-sm text-slate-500 text-center py-6">Loading favourites…</div>
          ) : favourites.length === 0 ? (
            <div className="text-sm text-slate-500 text-center py-6">
              No favourites yet — search above and save one to start tracking it.
            </div>
          ) : (
            Object.entries(grouped)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([category, favs]) => (
                <div key={category}>
                  <div className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold mb-2">
                    {category} ({favs.length})
                  </div>
                  <div className="space-y-3">
                    {favs.map((fav) => (
                      <div key={fav.id} className="rounded-lg border border-white/8 bg-white/3 p-3">
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <span className="text-sm text-slate-100 font-medium">
                            {fav.cpk ? `[Product: ${fav.cpk}]` : fav.term}
                          </span>
                          <div className="flex items-center gap-2">
                            <select
                              value={fav.category ?? "other"}
                              onChange={(e) => void handleCategoryChange(fav.id, e.target.value)}
                              className="rounded border border-white/10 bg-white/5 px-1.5 py-1 text-[10px] text-slate-300"
                            >
                              {CATEGORY_OPTIONS.map((c) => (
                                <option key={c} value={c}>{c}</option>
                              ))}
                            </select>
                            <button
                              onClick={() => void handleDelete(fav.id)}
                              aria-label={`Remove ${fav.term} from favourites`}
                              className="text-slate-500 hover:text-red-400"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                        {matrix[fav.id] ? (
                          <MatrixTable row={matrix[fav.id]} />
                        ) : (
                          <div className="text-xs text-slate-500">No current listings match this search.</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))
          )}
        </div>
      </div>
    </div>
  );
}
