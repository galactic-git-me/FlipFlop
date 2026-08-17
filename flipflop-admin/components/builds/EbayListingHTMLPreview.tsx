"use client";
/* eslint-disable @next/next/no-img-element */

import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, Heart, ListChecks, Monitor, Search, Smartphone, X } from "lucide-react";
import { useState } from "react";

interface EbayListingHTMLPreviewProps {
  title: string;
  description: string;
  images: string[];
  aspects?: Record<string, string[]> | null;
  price?: number;
  condition?: string;
  shippingCost?: number | null;
  heroPhotoUrl?: string | null;
  onClose?: () => void;
  isModal?: boolean;
}

const CONDITION_LABELS: Record<string, string> = {
  "1000": "New",
  "1500": "New other",
  "2000": "Certified refurbished",
  "2500": "Seller refurbished",
  "3000": "Used",
  "7000": "For parts or not working",
};

export function EbayListingHTMLPreview({
  title,
  description,
  images,
  aspects,
  price,
  condition,
  shippingCost,
  heroPhotoUrl,
  onClose,
  isModal = false,
}: EbayListingHTMLPreviewProps) {
  const [selectedImageIdx, setSelectedImageIdx] = useState(0);
  const [viewport, setViewport] = useState<"desktop" | "mobile">("desktop");
  const [previewMode, setPreviewMode] = useState<"search" | "listing">("search");
  const specifics = Object.entries(aspects ?? {}).filter(([, values]) => values?.length);
  const conditionLabel = CONDITION_LABELS[condition ?? ""] ?? condition ?? "Used";
  const postage = shippingCost && shippingCost > 0 ? `£${shippingCost.toFixed(2)} delivery` : "Free delivery";
  const orderedImages = heroPhotoUrl && images.includes(heroPhotoUrl)
    ? [heroPhotoUrl, ...images.filter((image) => image !== heroPhotoUrl)]
    : images;
  const selectedImage = orderedImages[selectedImageIdx];
  const plainDescription = description.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  const qualityChecks = [
    { label: "Searchable title", detail: `${title.length}/80 characters`, pass: title.length >= 55 && title.length <= 80 },
    { label: "Strong photo coverage", detail: `${orderedImages.length}/12 photos`, pass: orderedImages.length >= 8 },
    { label: "Hero image selected", detail: heroPhotoUrl ? "Cover photo is explicit" : "Select a cover photo", pass: Boolean(heroPhotoUrl) },
    { label: "Rich item specifics", detail: `${specifics.length} completed`, pass: specifics.length >= 10 },
    { label: "Readable description", detail: `${plainDescription.length.toLocaleString()} text characters`, pass: plainDescription.length >= 400 && plainDescription.length <= 9000 },
    { label: "Performance evidence", detail: "Benchmarks or FPS identified", pass: /fps|benchmark|percentile|3dmark|novabench/i.test(plainDescription) },
  ];
  const passedChecks = qualityChecks.filter((check) => check.pass).length;
  const qualityScore = Math.round((passedChecks / qualityChecks.length) * 100);

  const content = (
    <div className="min-h-screen bg-white font-sans text-[#191919]">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1440px] items-center gap-4 px-5 py-4">
          <div aria-label="eBay" className="shrink-0 text-[42px] font-semibold leading-none tracking-[-5px]">
            <span className="text-[#e53238]">e</span><span className="text-[#0064d2]">b</span><span className="text-[#f5af02]">a</span><span className="text-[#86b817]">y</span>
          </div>
          <div className="hidden text-xs leading-tight text-slate-600 md:block">Shop by<br />category⌄</div>
          <div className="flex h-11 min-w-0 flex-1 items-center rounded-full border-2 border-[#191919] px-5 text-sm text-slate-500">
            Search for anything
            <span className="ml-auto hidden border-l border-slate-300 pl-5 md:inline">All Categories⌄</span>
          </div>
          <button className="hidden h-11 rounded-full bg-[#3665f3] px-9 font-semibold text-white md:block">Search</button>
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-5 pb-16 pt-4">
        <div className="mb-5 text-xs text-slate-500">eBay › Computers/Tablets & Networking › Desktops & All-in-Ones</div>
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1.45fr)_minmax(340px,.8fr)]">
          <section className="min-w-0">
            <div className="grid gap-3 sm:grid-cols-[76px_minmax(0,1fr)]">
              <div className="order-2 flex gap-2 overflow-x-auto sm:order-1 sm:flex-col">
                {orderedImages.map((image, index) => (
                  <button key={`${image}-${index}`} onClick={() => setSelectedImageIdx(index)} className={`h-[70px] w-[70px] shrink-0 overflow-hidden rounded-xl border bg-[#f7f7f7] ${selectedImageIdx === index ? "border-2 border-[#191919]" : "border-slate-300"}`}>
                    <img src={image} alt={`Product view ${index + 1}`} className="h-full w-full object-cover" />
                  </button>
                ))}
              </div>
              <div className="order-1 relative flex min-h-[430px] items-center justify-center overflow-hidden rounded-2xl bg-[#f7f7f7] sm:order-2 lg:min-h-[610px]">
                {selectedImage ? <img src={selectedImage} alt={title} className="max-h-[680px] w-full object-contain" /> : <span className="text-slate-400">No product images</span>}
                {orderedImages.length > 1 && <>
                  <button aria-label="Previous image" onClick={() => setSelectedImageIdx((selectedImageIdx - 1 + orderedImages.length) % orderedImages.length)} className="absolute left-4 top-1/2 grid h-12 w-12 -translate-y-1/2 place-items-center rounded-full border border-slate-300 bg-white shadow"><ChevronLeft /></button>
                  <button aria-label="Next image" onClick={() => setSelectedImageIdx((selectedImageIdx + 1) % orderedImages.length)} className="absolute right-4 top-1/2 grid h-12 w-12 -translate-y-1/2 place-items-center rounded-full border border-slate-300 bg-white shadow"><ChevronRight /></button>
                </>}
              </div>
            </div>
          </section>

          <aside>
            <div className="border-b border-slate-300 pb-5">
              <h1 className="text-[22px] font-semibold leading-7">{title}</h1>
              <div className="mt-3 flex items-center gap-3 text-sm">
                <div className="grid h-10 w-10 place-items-center rounded-full bg-slate-950 font-bold text-white">FF</div>
                <div><span className="font-semibold">theflipflop_dot_shop</span><br /><span className="text-xs text-slate-600">100% positive feedback · Seller&apos;s other items</span></div>
              </div>
            </div>
            <div className="border-b border-slate-300 py-6">
              <div className="text-3xl font-bold">£{(price ?? 0).toFixed(2)}</div>
              <div className="mt-5 grid grid-cols-[92px_1fr] gap-y-3 text-sm"><span>Condition:</span><strong>{conditionLabel}</strong><span>Postage:</span><strong className="text-[#067a46]">{postage}</strong><span>Located in:</span><span>Twickenham, United Kingdom</span></div>
            </div>
            <div className="space-y-3 py-6">
              <button className="h-12 w-full rounded-full bg-[#3665f3] text-base font-semibold text-white">Buy it now</button>
              <button className="h-12 w-full rounded-full border-2 border-[#3665f3] font-semibold text-[#3665f3]">Make offer</button>
              <button className="flex h-12 w-full items-center justify-center gap-2 rounded-full border-2 border-[#3665f3] font-semibold text-[#3665f3]"><Heart size={18} /> Add to Watchlist</button>
            </div>
            <div className="rounded-2xl bg-[#f7f7f7] p-5 text-sm"><strong>Shop with confidence</strong><p className="mt-2 text-slate-600">eBay Money Back Guarantee. Get the item you ordered or your money back.</p></div>
          </aside>
        </div>

        <section className="mt-16 border-t border-slate-300 pt-9">
          <h2 className="text-2xl font-semibold">About this item</h2>
          <h3 className="mt-8 text-xl font-semibold">Item specifics</h3>
          {specifics.length ? <div className="mt-5 grid gap-x-12 gap-y-4 md:grid-cols-2">
            {specifics.map(([name, values]) => <div key={name} className="grid grid-cols-[minmax(110px,38%)_1fr] gap-4 text-sm"><span className="text-slate-600">{name}</span><span>{values.join(", ")}</span></div>)}
          </div> : <p className="mt-4 text-sm text-slate-500">No item specifics have been saved yet.</p>}
        </section>
      </main>

      <section className="border-y border-slate-200 bg-[#f7f7f7] px-5 py-12">
        <div className="mx-auto max-w-[1380px]">
          <h2 className="mb-6 text-2xl font-semibold text-[#191919]">Item description from the seller</h2>
          <div className="overflow-hidden rounded-sm bg-white shadow-sm" dangerouslySetInnerHTML={{ __html: description }} />
        </div>
      </section>
      <footer className="mx-auto max-w-[1440px] px-5 py-12 text-sm text-slate-600"><strong className="text-lg text-[#191919]">About this seller</strong><p className="mt-4">theflipflop_dot_shop · Twickenham, London · 100% positive feedback</p></footer>
    </div>
  );

  if (!isModal) return content;

  const searchPreview = (
    <div className="min-h-[720px] bg-white p-5 text-[#191919] sm:p-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-6 flex items-center gap-3 border-b border-slate-200 pb-5">
          <Search className="text-slate-500" />
          <h2 className="text-xl font-semibold">Gaming PC Ryzen 7 RTX</h2>
          <span className="text-sm text-slate-500">1,100+ results</span>
        </div>
        <p className="mb-5 text-sm text-slate-600">This is the first impression buyers compare against competing listings.</p>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <article className="overflow-hidden rounded-2xl border-2 border-[#3665f3] bg-white shadow-lg">
            <div className="relative aspect-square bg-[#f7f7f7]">
              {orderedImages[0] ? <img src={orderedImages[0]} alt={title} className="h-full w-full object-cover" /> : <div className="grid h-full place-items-center text-slate-400">No cover photo</div>}
              <button aria-label="Watch item" className="absolute right-3 top-3 grid h-10 w-10 place-items-center rounded-full bg-white shadow"><Heart size={20} /></button>
            </div>
            <div className="p-4">
              <h3 className="line-clamp-2 min-h-12 text-base leading-6">{title}</h3>
              <p className="mt-1 text-xs text-slate-500">{conditionLabel} · Business</p>
              <p className="mt-3 text-2xl font-bold">£{(price ?? 0).toFixed(2)}</p>
              <p className="mt-1 text-sm font-semibold text-[#067a46]">{postage}</p>
              <p className="mt-3 text-xs text-slate-500">Seller 100% positive feedback</p>
            </div>
          </article>
          {["Similar gaming PC", "RTX gaming desktop", "Custom RGB computer"].map((label) => <div key={label} className="opacity-45"><div className="aspect-square rounded-2xl bg-slate-200" /><div className="mt-3 h-5 rounded bg-slate-200" /><div className="mt-2 h-5 w-2/3 rounded bg-slate-200" /><div className="mt-4 h-7 w-1/2 rounded bg-slate-300" /></div>)}
        </div>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-[100] overflow-y-auto bg-slate-950/90 p-2 md:p-5">
      <div className="sticky top-2 z-[110] mx-auto mb-3 flex max-w-[1440px] flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-700 bg-slate-900/95 px-4 py-3 text-white shadow-2xl backdrop-blur">
        <div><div className="text-sm font-semibold">eBay listing preview</div><div className="text-xs text-slate-400">Uses the exact saved listing data and description. eBay may make minor platform layout changes.</div></div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg bg-slate-800 p-1">
            <button onClick={() => setPreviewMode("search")} className={`flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors ${previewMode === "search" ? "bg-blue-600" : "text-slate-300 hover:bg-slate-700"}`}><Search size={16} /> Search result</button>
            <button onClick={() => setPreviewMode("listing")} className={`flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors ${previewMode === "listing" ? "bg-blue-600" : "text-slate-300 hover:bg-slate-700"}`}><ListChecks size={16} /> Full listing</button>
          </div>
          <div className="hidden rounded-lg bg-slate-800 p-1 sm:flex">
            <button aria-label="Desktop preview" onClick={() => setViewport("desktop")} className={`rounded-md p-2 ${viewport === "desktop" ? "bg-blue-600" : "text-slate-400"}`}><Monitor size={18} /></button>
            <button aria-label="Mobile preview" onClick={() => setViewport("mobile")} className={`rounded-md p-2 ${viewport === "mobile" ? "bg-blue-600" : "text-slate-400"}`}><Smartphone size={18} /></button>
          </div>
          {onClose && <button onClick={onClose} className="flex items-center gap-2 rounded-lg border border-slate-600 px-3 py-2 text-sm hover:bg-slate-800"><X size={18} /><span className="hidden sm:inline">Close</span></button>}
        </div>
      </div>
      <div className="mx-auto mb-3 grid max-w-[1440px] gap-3 md:grid-cols-[170px_1fr]">
        <div className={`rounded-xl border p-4 ${qualityScore >= 80 ? "border-emerald-500/40 bg-emerald-950/70" : "border-amber-500/40 bg-amber-950/70"}`}>
          <div className="text-xs uppercase tracking-wider text-slate-300">Listing quality</div><div className="mt-1 text-3xl font-bold text-white">{qualityScore}%</div><div className="text-xs text-slate-400">{passedChecks}/{qualityChecks.length} checks passed</div>
        </div>
        <div className="grid gap-2 rounded-xl border border-slate-700 bg-slate-900/95 p-3 sm:grid-cols-2 lg:grid-cols-3">
          {qualityChecks.map((check) => <div key={check.label} className="flex gap-2 rounded-lg bg-slate-800/70 p-2.5 text-xs">{check.pass ? <CheckCircle2 className="mt-0.5 shrink-0 text-emerald-400" size={16} /> : <AlertTriangle className="mt-0.5 shrink-0 text-amber-400" size={16} />}<div><strong className="text-slate-100">{check.label}</strong><div className="mt-0.5 text-slate-400">{check.detail}</div></div></div>)}
        </div>
      </div>
      <div className={`mx-auto overflow-hidden bg-white shadow-2xl transition-[max-width] ${viewport === "mobile" ? "max-w-[430px]" : "max-w-[1440px]"}`}>{previewMode === "search" ? searchPreview : content}</div>
    </div>
  );
}
