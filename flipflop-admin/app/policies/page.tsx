"use client";

import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { api } from "@/lib/api";

const TABS = ["delivery", "returns", "warranty", "payments", "cancellations", "faults", "delivery-damage"] as const;
type Policy = { title: string; content: string };
type PolicySet = { policies: Record<string, Policy> };

export default function PoliciesPage() {
  const [data, setData] = useState<PolicySet>({ policies: {} });
  const [tab, setTab] = useState<string>(TABS[0]);
  const [status, setStatus] = useState("Loading policy copy…");
  const [saving, setSaving] = useState(false);
  useEffect(() => { api.getStorefrontPolicies().then((value) => { setData(value); setStatus(value.policies[tab] ? "Draft copy loaded" : "No saved copy yet. Add the reviewed wording before publishing."); }).catch((error) => setStatus(String(error))); }, []);
  const current = data.policies[tab] ?? { title: tab.replaceAll("-", " ").replace(/\b\w/g, (char) => char.toUpperCase()), content: "" };
  const update = (patch: Partial<Policy>) => setData((old) => ({ ...old, policies: { ...old.policies, [tab]: { ...current, ...patch } } }));
  async function save() { setSaving(true); setStatus("Saving…"); try { setData(await api.saveStorefrontPolicies(data)); setStatus("Saved. Storefront policy pages now serve this copy."); } catch (error) { setStatus(String(error)); } finally { setSaving(false); } }
  return <div className="mx-auto max-w-5xl space-y-6 p-6 text-slate-100">
    <header><p className="text-xs uppercase tracking-[.2em] text-emerald-400">Storefront content</p><h1 className="mt-2 text-3xl font-semibold">Customer Policies</h1><p className="mt-2 text-sm text-slate-400">Edit each public policy page. Source baseline: docs/product/customer-policies.md. Copy needs final legal and operational review before publication.</p></header>
    <div className="flex flex-wrap gap-2">{TABS.map((name) => <button key={name} onClick={() => setTab(name)} className={`rounded-lg border px-3 py-2 text-sm capitalize ${name === tab ? "border-emerald-400 bg-emerald-950 text-emerald-200" : "border-slate-700 text-slate-300"}`}>{name.replaceAll("-", " ")}</button>)}</div>
    <section className="space-y-4 rounded-xl border border-slate-700 bg-slate-950/60 p-5"><label className="block text-sm">Page title<input value={current.title} onChange={(event) => update({ title: event.target.value })} className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 p-3" /></label><label className="block text-sm">Customer-facing copy<textarea value={current.content} onChange={(event) => update({ content: event.target.value })} rows={18} placeholder="Paste reviewed policy copy here. Plain text; separate paragraphs with blank lines." className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-900 p-3 leading-6" /></label><div className="flex items-center justify-between gap-4"><p className="text-sm text-amber-300">{status}</p><button disabled={saving} onClick={save} className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 font-medium text-slate-950 disabled:opacity-50"><Save size={16}/>{saving ? "Saving…" : "Save policy"}</button></div></section>
  </div>;
}
