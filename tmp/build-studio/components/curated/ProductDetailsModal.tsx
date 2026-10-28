'use client';

import { useEffect, useState } from 'react';
import { request, money, type Chassis, type Product } from '@/lib/studio';

type Copy = { headline: string; summary: string; benefits: { title: string; description: string }[]; key_details: { label: string; value: string }[] };
type CopyResponse = { copy: Copy; context: string; generated: boolean };
type Detail = {
  product?: Product;
  caseItem?: Chassis;
  baselineVariantId?: number;
  curatedBuildId?: string;
  candidateIndex?: number;
};

export default function ProductDetailsModal({ detail, onClose }: { detail: Detail | null; onClose: () => void }) {
  const [response, setResponse] = useState<CopyResponse | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!detail) return;
    const body = detail.caseItem
      ? { case_id: detail.caseItem.id }
      : { variant_id: detail.product?.id, baseline_variant_id: detail.baselineVariantId,
          curated_build_id: detail.curatedBuildId, candidate_index: detail.candidateIndex };
    const controller = new AbortController();
    setResponse(null); setError('');
    request<CopyResponse>('product-copy', controller.signal, body)
      .then(setResponse).catch(cause => { if (cause.name !== 'AbortError') setError(cause.message); });
    return () => controller.abort();
  }, [detail]);
  useEffect(() => {
    if (!detail) return;
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKeyDown);
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { window.removeEventListener('keydown', onKeyDown); document.body.style.overflow = oldOverflow; };
  }, [detail, onClose]);
  if (!detail) return null;
  const item = detail.product;
  const caseItem = detail.caseItem;
  const title = item?.title ?? `${caseItem?.brand ?? ''} ${caseItem?.name ?? ''}`.trim();
  const image = item?.images?.[0] ?? caseItem?.images?.[0];
  const fallback = item?.description?.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
  const copy = response?.copy;
  return <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/85 p-3 backdrop-blur-md sm:p-6" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section role="dialog" aria-modal="true" aria-labelledby="product-detail-title" className="grid max-h-[92vh] w-full max-w-5xl overflow-hidden rounded-3xl border border-cyan-200/20 bg-[#08111d] shadow-[0_25px_100px_rgba(0,0,0,.65)] lg:grid-cols-[1.05fr_.95fr]">
      <div className="relative flex min-h-64 items-center justify-center bg-white p-7 sm:min-h-[480px]">
        {image ? <img src={image} alt={title} className="max-h-[68vh] w-full object-contain" /> : <div className="p-10 text-center text-slate-600">No product image is available.</div>}
        <span className="absolute bottom-4 left-4 rounded-full bg-slate-950/75 px-3 py-1 text-[10px] font-medium uppercase tracking-wider text-white">{item ? 'Component' : 'PC case'}</span>
      </div>
      <div className="flex min-h-0 flex-col overflow-y-auto p-6 sm:p-8">
        <div className="flex items-start justify-between gap-4"><div><p className="text-[10px] font-semibold uppercase tracking-[.22em] text-cyan-300">A closer look</p><h2 id="product-detail-title" className="mt-2 text-2xl font-bold text-white sm:text-3xl">{title}</h2></div><button type="button" onClick={onClose} aria-label="Close product details" className="rounded-full border border-white/15 px-3 py-2 text-sm text-slate-200 hover:bg-white/10">Close</button></div>
        {(item || caseItem) && <p className="mt-3 text-lg font-semibold text-cyan-200">{money(item?.display_price ?? caseItem!.rrp_gbp)}</p>}
        {copy ? <>
          <p className="mt-5 text-lg font-semibold leading-snug text-white">{copy.headline}</p>
          <p className="mt-2 text-sm leading-6 text-slate-300">{copy.summary}</p>
          {copy.benefits.length > 0 && <div className="mt-6"><h3 className="text-xs font-semibold uppercase tracking-wider text-lime-300">What it brings to your build</h3><ul className="mt-3 space-y-3">{copy.benefits.map((benefit, index) => <li key={`${benefit.title}-${index}`} className="rounded-xl border border-white/10 bg-white/[.035] p-3"><h4 className="text-sm font-semibold text-white">{benefit.title}</h4><p className="mt-1 text-xs leading-5 text-slate-300">{benefit.description}</p></li>)}</ul></div>}
          {copy.key_details.length > 0 && <div className="mt-5"><h3 className="text-xs font-semibold uppercase tracking-wider text-cyan-200">Useful details</h3><dl className="mt-2 divide-y divide-white/10">{copy.key_details.map((detailRow, index) => <div key={`${detailRow.label}-${index}`} className="flex justify-between gap-4 py-2 text-xs"><dt className="text-slate-400">{detailRow.label}</dt><dd className="text-right text-slate-200">{detailRow.value}</dd></div>)}</dl></div>}
        </> : <div className="mt-5 rounded-xl border border-cyan-300/15 bg-cyan-300/[.04] p-4 text-sm leading-6 text-slate-300" aria-live="polite">{error ? (fallback || 'A fuller product guide is not available right now. You can still review the product image and listed price.') : 'Putting together a clear, evidence-based product guide…'}</div>}
        {error && fallback && <details className="mt-4 text-xs text-slate-400"><summary className="cursor-pointer">View supplier description</summary><p className="mt-2 leading-5">{fallback}</p></details>}
        <p className="mt-auto pt-6 text-[10px] leading-4 text-slate-500">Product details are written from the supplier listing and verified catalogue facts. Check the listed specifications for exact compatibility.</p>
      </div>
    </section>
  </div>;
}
