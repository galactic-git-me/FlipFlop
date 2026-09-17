"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Row = Awaited<ReturnType<typeof api.dispatch.list>>[number];
export default function DispatchZonePage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const load = async () => { setLoading(true); try { setRows(await api.dispatch.list()); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, []);
  const schedule = async (id: number) => {
    const value = window.prompt("Collection date/time (YYYY-MM-DDTHH:mm)");
    if (!value) return;
    await api.dispatch.setCollectionDate(id, new Date(value).toISOString());
    await load();
  };
  return <div className="space-y-6">
    <div><h1 className="text-2xl font-semibold text-white">Dispatch Zone</h1><p className="mt-1 text-sm text-slate-400">Sold builds awaiting courier selection, payment, collection and delivery confirmation.</p></div>
    <div className="rounded-xl border border-slate-700/80 bg-[#0b121d]/90 p-4 text-xs text-slate-400">Quotes and insurance are fetched from the existing integrations on the build page. Booking/payment remains an explicit action because it creates a real courier charge. Use the build’s shipment panel to review the quote, confirm cover, and click <span className="text-emerald-300">Book &amp; Pay</span>.</div>
    {loading ? <p className="text-slate-400">Loading dispatch queue…</p> : rows.length === 0 ? <p className="rounded-xl border border-slate-800 p-8 text-center text-slate-500">No sold builds are awaiting dispatch.</p> : <div className="space-y-3">{rows.map((row) => <div key={row.id} className="rounded-xl border border-slate-700 bg-[#0b121d]/90 p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><a href={`/builds/${row.id}`} className="font-semibold text-white hover:text-emerald-300">{row.name}</a><p className="mt-1 text-xs text-slate-500">Build {row.id} · {row.buyer_name || "Buyer details pending"} · {row.customer_email || "customer email pending"}</p></div><span className="rounded-full border border-amber-400/30 px-2 py-1 text-[10px] uppercase tracking-wide text-amber-300">{row.dispatch_status.replaceAll("_", " ")}</span></div><div className="mt-4 flex flex-wrap items-center gap-3 text-sm"><span className="text-slate-300">Sale: £{(row.sale_price || 0).toFixed(2)}</span>{row.tracking_number && <a href={row.shipping_label_url || "#"} target="_blank" rel="noreferrer" className="text-cyan-300 hover:underline">Tracking {row.tracking_number}</a>}{row.collection_date && <span className="text-slate-400">Collection {new Date(row.collection_date).toLocaleString("en-GB")}</span>}<button onClick={() => void schedule(row.id)} className="rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-200 hover:border-emerald-400/50">{row.collection_date ? "Change collection day" : "Set collection day"}</button><a href={`/builds/${row.id}`} className="rounded bg-emerald-400 px-3 py-1.5 text-xs font-semibold text-slate-950 hover:bg-emerald-300">Open shipment booking</a></div></div>)}</div>}
  </div>;
}
