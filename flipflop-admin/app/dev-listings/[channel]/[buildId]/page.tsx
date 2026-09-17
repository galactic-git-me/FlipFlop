"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ExternalLink, ShieldCheck, Store } from "lucide-react";

const labels: Record<string, string> = {
  onbuy: "OnBuy",
  amazon: "Amazon",
  facebook_catalog: "Facebook catalog",
  vinted: "Vinted",
};

export default function DevListingPage() {
  const params = useParams<{ channel: string; buildId: string }>();
  const search = useSearchParams();
  const channel = labels[params.channel] ?? params.channel;
  const [preview, setPreview] = useState<Record<string, string> | null>(null);
  useEffect(() => {
    const stored = window.localStorage.getItem(`flipflop-dev-listing:${params.channel}:${params.buildId}`);
    if (stored) {
      try { setPreview(JSON.parse(stored) as Record<string, string>); } catch { /* use defaults */ }
    }
  }, [params.channel, params.buildId]);
  // Query params remain a backwards-compatible fallback for old result links.
  const title = preview?.title || search.get("title") || "FlipFlop PC build";
  const description = preview?.description || search.get("description") || "Development listing preview.";
  const image = preview?.image || search.get("image");
  const price = preview?.price || search.get("price");
  const condition = preview?.condition || search.get("condition") || "Used";
  const sku = preview?.sku || search.get("sku") || `FF-BUILD-${params.buildId}`;

  return (
    <main className="min-h-screen bg-[#020617] px-4 py-8 text-slate-100 md:px-8">
      <div className="mx-auto max-w-5xl">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5">
          <div>
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-yellow-400/30 bg-yellow-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-yellow-200">
              <ShieldCheck className="h-3.5 w-3.5" /> Dev fake listing
            </div>
            <h1 className="text-2xl font-semibold tracking-tight">{channel}</h1>
            <p className="mt-1 text-sm text-slate-400">Preview only · Build {params.buildId} · SKU {sku}</p>
          </div>
          <a href="/cross-listing" className="inline-flex items-center gap-2 rounded-md border border-slate-700 px-3 py-2 text-sm text-slate-300 transition-colors hover:border-emerald-400/60 hover:text-emerald-300">
            <Store className="h-4 w-4" /> Back to Cross-listing
          </a>
        </header>

        <section className="overflow-hidden rounded-2xl border border-slate-800 bg-[#0b121d] shadow-2xl shadow-black/20">
          <div className="grid gap-0 md:grid-cols-[minmax(280px,0.9fr)_1.1fr]">
            <div className="flex min-h-[300px] items-center justify-center bg-slate-950 p-6">
              {image ? <img src={image} alt={title} className="max-h-[420px] w-full rounded-xl object-contain" /> : <div className="text-center text-sm text-slate-500">No product photo supplied</div>}
            </div>
            <div className="p-6 md:p-9">
              <div className="mb-4 flex flex-wrap gap-2 text-xs">
                <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2.5 py-1 text-emerald-300">Available</span>
                <span className="rounded-full border border-slate-700 px-2.5 py-1 text-slate-400">{condition}</span>
              </div>
              <h2 className="text-3xl font-semibold leading-tight text-white">{title}</h2>
              <div className="mt-5 text-3xl font-semibold text-emerald-300">{price ? `£${Number(price).toFixed(2)}` : "Price on request"}</div>
              <p className="mt-6 whitespace-pre-wrap text-sm leading-7 text-slate-300">{description}</p>
              <div className="mt-7 border-t border-slate-800 pt-5 text-xs text-slate-400">
                <div className="flex justify-between gap-4"><span>Delivery</span><span className="text-slate-200">Delivery only</span></div>
                <div className="mt-2 flex justify-between gap-4"><span>Collection</span><span className="text-slate-200">Not available</span></div>
                <div className="mt-2 flex justify-between gap-4"><span>Listing reference</span><span className="text-slate-200">DEV-{params.channel}-{params.buildId}</span></div>
              </div>
              <button type="button" className="mt-7 inline-flex w-full cursor-not-allowed items-center justify-center gap-2 rounded-lg bg-emerald-400 px-4 py-3 font-semibold text-slate-950 opacity-80">
                Add to basket <ExternalLink className="h-4 w-4" />
              </button>
              <p className="mt-3 text-center text-[11px] text-slate-500">This button is disabled in the development preview.</p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
