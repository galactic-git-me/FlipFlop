"use client";
import { useEffect, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Loader2, Search, X } from "lucide-react";
import { readJsonResponse } from "@/lib/read-json-response";

type Result = { id: string; thumbnail_url: string; title: string; source_page?: string };
export default function GooglePhotoSearch({ variantId, title, onClose, onSaved }: {
  variantId: number; title: string; onClose: () => void; onSaved: (url: string) => void;
}) {
  const [query, setQuery] = useState(title.split(",")[0].split(/\s+/).slice(0, 12).join(" "));
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [errorStage, setErrorStage] = useState<"search" | "save">("search");
  const alive = useRef(true);
  const initialized = useRef(false);
  const sequence = useRef(0);
  const search = async (value?: string) => {
    const id = ++sequence.current;
    setLoading(true); setError(""); setErrorStage("search"); setResults([]);
    try {
      const suffix = value ? `?query=${encodeURIComponent(value)}` : "";
      const response = await fetch(`/api/assets-3d/catalogue/components/${variantId}/image-search${suffix}`, { cache: "no-store" });
      const data = await readJsonResponse<{ query: string; results: Result[]; detail?: string }>(response);
      if (!response.ok) throw new Error(data.detail || "Google image search failed");
      if (alive.current && id === sequence.current) { setQuery(data.query); setResults(data.results); }
    } catch (reason) { if (alive.current && id === sequence.current) setError(reason instanceof Error ? reason.message : "Could not search images"); }
    finally { if (alive.current && id === sequence.current) setLoading(false); }
  };
  useEffect(() => { alive.current = true; if (!initialized.current) { initialized.current = true; void search(); } return () => { alive.current = false; }; }, []);
  const select = async (result: Result) => {
    setSaving(result.id); setError(""); setErrorStage("save");
    try {
      const response = await fetch(`/api/assets-3d/catalogue/components/${variantId}/search-photo`, {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ result_id: result.id }),
        signal: AbortSignal.timeout(35000),
      });
      const data = await readJsonResponse<{ photo_url?: string; detail?: string }>(response);
      if (!response.ok) throw new Error(data.detail || `Could not save photo (HTTP ${response.status})`);
      if (typeof data.photo_url !== "string" || !data.photo_url) throw new Error("The server did not confirm that the photo was saved. Please retry.");
      onSaved(data.photo_url);
    } catch (reason) { setError(reason instanceof Error && (reason.name === "TimeoutError" || reason.name === "AbortError") ? "Saving this photo timed out. Reopen the family card to check whether it saved, or choose another result." : reason instanceof Error ? reason.message : "Could not save image"); }
    finally { setSaving(null); }
  };
  return <Dialog.Root open onOpenChange={open => { if (!open && !saving) onClose(); }}><Dialog.Portal>
    <Dialog.Overlay className="fixed inset-0 z-[100] bg-black/75" />
    <Dialog.Content className="fixed inset-3 z-[101] flex flex-col overflow-hidden rounded-xl border border-cyan-400/30 bg-slate-950 text-slate-100 sm:inset-8 lg:inset-x-[12%]">
      <header className="border-b border-white/15 p-4"><div className="flex items-start justify-between gap-4"><div><Dialog.Title className="font-semibold">Find a product photo</Dialog.Title><Dialog.Description className="mt-1 text-sm text-slate-400">{title}. Choose a hardware photo without its box. Clicking a result downloads and selects it.</Dialog.Description></div><Dialog.Close disabled={!!saving} aria-label="Close image search" className="rounded p-2 hover:bg-white/10"><X className="h-5 w-5" /></Dialog.Close></div>
      <form onSubmit={event => { event.preventDefault(); void search(query); }} className="mt-4 flex gap-2"><input aria-label="Google image search query" value={query} onChange={event => setQuery(event.target.value)} maxLength={180} disabled={!!saving} placeholder="Product model…" className="min-w-0 flex-1 rounded border border-white/20 bg-slate-900 px-3 py-2" /><button disabled={loading || !!saving || query.trim().length < 2} className="inline-flex items-center gap-2 rounded bg-cyan-400 px-3 py-2 font-medium text-slate-950 disabled:opacity-40"><Search className="h-4 w-4" />Search</button></form></header>
      {error && <p role="alert" className="shrink-0 border-b border-rose-400/30 bg-rose-950/50 px-4 py-3 text-rose-200">{errorStage === "search" ? "Image search failed" : "Photo not saved"}: {error}</p>}
      {saving && <p role="status" className="shrink-0 border-b border-cyan-400/20 px-4 py-3 text-cyan-200">Downloading and saving your selected photo…</p>}
      <div className="flex-1 overflow-auto p-4">{loading ? <p role="status">Searching Google Images…</p> : !results.length ? (error ? null : <p className="text-slate-400">No image results. Try a shorter model name.</p>) : <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">{results.map((result, index) => <button key={result.id} disabled={!!saving} onClick={() => void select(result)} aria-label={`Use Google image ${index + 1}: ${result.title}`} className="overflow-hidden rounded-lg border border-white/15 bg-slate-900 text-left hover:border-cyan-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300 disabled:opacity-50"><div className="relative aspect-square bg-white"><img src={result.thumbnail_url} alt={result.title} referrerPolicy="no-referrer" className="h-full w-full object-contain" />{saving === result.id && <span role="status" className="absolute inset-0 flex items-center justify-center bg-black/70 text-white"><Loader2 className="mr-2 h-5 w-5 animate-spin" />Downloading…</span>}</div><p className="line-clamp-2 p-2 text-xs">{result.title}</p></button>)}</div>}</div>
      <p className="border-t border-white/10 p-3 text-xs text-slate-400">Google Images results · the selected server copy is shared wherever this component is used.</p>
    </Dialog.Content>
  </Dialog.Portal></Dialog.Root>;
}
