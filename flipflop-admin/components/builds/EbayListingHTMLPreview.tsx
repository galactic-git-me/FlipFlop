"use client";
/* eslint-disable @next/next/no-img-element */

import { ChevronLeft, ChevronRight, Heart, Monitor, Smartphone, X } from "lucide-react";
import { useState } from "react";

interface EbayListingHTMLPreviewProps {
  title: string;
  description: string;
  images: string[];
  aspects?: Record<string, string[]> | null;
  price?: number;
  condition?: string;
  shippingCost?: number | null;
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
  onClose,
  isModal = false,
}: EbayListingHTMLPreviewProps) {
  const [selectedImageIdx, setSelectedImageIdx] = useState(0);
  const [viewport, setViewport] = useState<"desktop" | "mobile">("desktop");
  const specifics = Object.entries(aspects ?? {}).filter(([, values]) => values?.length);
  const conditionLabel = CONDITION_LABELS[condition ?? ""] ?? condition ?? "Used";
  const postage = shippingCost && shippingCost > 0 ? `£${shippingCost.toFixed(2)} delivery` : "Free delivery";
  const selectedImage = images[selectedImageIdx];

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
                {images.map((image, index) => (
                  <button key={`${image}-${index}`} onClick={() => setSelectedImageIdx(index)} className={`h-[70px] w-[70px] shrink-0 overflow-hidden rounded-xl border bg-[#f7f7f7] ${selectedImageIdx === index ? "border-2 border-[#191919]" : "border-slate-300"}`}>
                    <img src={image} alt={`Product view ${index + 1}`} className="h-full w-full object-cover" />
                  </button>
                ))}
              </div>
              <div className="order-1 relative flex min-h-[430px] items-center justify-center overflow-hidden rounded-2xl bg-[#f7f7f7] sm:order-2 lg:min-h-[610px]">
                {selectedImage ? <img src={selectedImage} alt={title} className="max-h-[680px] w-full object-contain" /> : <span className="text-slate-400">No product images</span>}
                {images.length > 1 && <>
                  <button aria-label="Previous image" onClick={() => setSelectedImageIdx((selectedImageIdx - 1 + images.length) % images.length)} className="absolute left-4 top-1/2 grid h-12 w-12 -translate-y-1/2 place-items-center rounded-full border border-slate-300 bg-white shadow"><ChevronLeft /></button>
                  <button aria-label="Next image" onClick={() => setSelectedImageIdx((selectedImageIdx + 1) % images.length)} className="absolute right-4 top-1/2 grid h-12 w-12 -translate-y-1/2 place-items-center rounded-full border border-slate-300 bg-white shadow"><ChevronRight /></button>
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

  return (
    <div className="fixed inset-0 z-[100] overflow-y-auto bg-slate-950/90 p-2 md:p-5">
      <div className="sticky top-2 z-[110] mx-auto mb-3 flex max-w-[1440px] items-center justify-between rounded-xl border border-slate-700 bg-slate-900/95 px-4 py-3 text-white shadow-2xl backdrop-blur">
        <div><div className="text-sm font-semibold">eBay listing preview</div><div className="text-xs text-slate-400">Uses the exact saved listing data and description. eBay may make minor platform layout changes.</div></div>
        <div className="flex items-center gap-2">
          <div className="hidden rounded-lg bg-slate-800 p-1 sm:flex">
            <button aria-label="Desktop preview" onClick={() => setViewport("desktop")} className={`rounded-md p-2 ${viewport === "desktop" ? "bg-blue-600" : "text-slate-400"}`}><Monitor size={18} /></button>
            <button aria-label="Mobile preview" onClick={() => setViewport("mobile")} className={`rounded-md p-2 ${viewport === "mobile" ? "bg-blue-600" : "text-slate-400"}`}><Smartphone size={18} /></button>
          </div>
          {onClose && <button onClick={onClose} className="flex items-center gap-2 rounded-lg border border-slate-600 px-3 py-2 text-sm hover:bg-slate-800"><X size={18} /><span className="hidden sm:inline">Close</span></button>}
        </div>
      </div>
      <div className={`mx-auto overflow-hidden bg-white shadow-2xl transition-[max-width] ${viewport === "mobile" ? "max-w-[430px]" : "max-w-[1440px]"}`}>{content}</div>
    </div>
  );
}
