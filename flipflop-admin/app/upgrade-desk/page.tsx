"use client";

import { useEffect, useState } from "react";

type Assessment = {
  id: number;
  status: string;
  desired_outcome: string;
  submitted_spec: Record<string, unknown>;
  budget_gbp: number;
  photo_urls: string[];
  system_report_url: string | null;
  advice: { recommendation: string; explanation: string; quoted_price_gbp: number | null } | null;
  scope_revision: number;
  approval_required: boolean;
};

const adviceOptions = ["KEEP", "UPGRADE", "OPTIONAL", "DONT_SPEND_HERE", "TRANSFORM"];

function headers(): HeadersInit {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("admin_token") : null;
  return { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

export default function UpgradeDeskPage() {
  const [items, setItems] = useState<Assessment[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [recommendation, setRecommendation] = useState("KEEP");
  const [explanation, setExplanation] = useState("");
  const [price, setPrice] = useState("");
  const [materialChange, setMaterialChange] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function load() {
    const response = await fetch("/api/admin/upgrades", { headers: headers(), cache: "no-store" });
    if (!response.ok) { setError("Could not load upgrade assessments."); return; }
    setItems(await response.json());
  }

  useEffect(() => { void load(); }, []);

  async function publish(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selected === null) return;
    setPending(true); setError("");
    try {
      const response = await fetch(`/api/admin/upgrades/${selected}/advice`, {
        method: "PUT", headers: headers(),
        body: JSON.stringify({ recommendation, explanation, quoted_price_gbp: price ? Number(price) : null,
          material_change: materialChange }),
      });
      if (!response.ok) setError("Could not publish advice. Check the explanation and quote.");
      else { await load(); setSelected(null); setExplanation(""); setPrice(""); setMaterialChange(false); }
    } catch {
      setError("Could not reach the upgrade service.");
    } finally {
      setPending(false);
    }
  }

  return <main className="mx-auto max-w-6xl space-y-6 p-6 text-white">
    <header><p className="text-sm uppercase tracking-widest text-orange-300">Customer service</p><h1 className="text-3xl font-semibold">Upgrade Desk</h1><p className="mt-2 text-slate-300">Review a customer’s existing PC and give honest advice. Physical intake must confirm the submitted specification before work begins.</p></header>
    {error && <p role="alert" className="rounded-lg border border-red-400 p-3 text-red-200">{error}</p>}
    <div className="grid gap-5 lg:grid-cols-2">{items.map((item) => <article key={item.id} className="rounded-2xl border border-white/20 bg-slate-950/70 p-5">
      <p className="text-xs uppercase tracking-widest text-blue-300">#{item.id} · {item.status.replaceAll("_", " ")}</p>
      <h2 className="mt-3 text-xl font-semibold">{item.desired_outcome}</h2>
      <p className="mt-2 text-slate-300">Budget £{item.budget_gbp}</p>
      <pre className="mt-3 overflow-auto whitespace-pre-wrap text-sm text-slate-300">{JSON.stringify(item.submitted_spec, null, 2)}</pre>
      {item.photo_urls.length > 0 && <p className="mt-3 text-sm">{item.photo_urls.map((url) => <a key={url} href={url} target="_blank" rel="noreferrer" className="mr-3 underline">Customer photo</a>)}</p>}
      {item.system_report_url && <a href={item.system_report_url} target="_blank" rel="noreferrer" className="mt-2 block text-sm underline">System report</a>}
      {item.advice && <p className="mt-4 text-sm text-slate-300">Latest: {item.advice.recommendation} — {item.advice.explanation}</p>}
      {item.approval_required && <p className="mt-3 text-orange-300">Awaiting customer approval for revision {item.scope_revision}</p>}
      <button type="button" onClick={() => { setSelected(item.id); setRecommendation(item.advice?.recommendation ?? "KEEP"); setExplanation(item.advice?.explanation ?? ""); setPrice(item.advice?.quoted_price_gbp?.toString() ?? ""); }} className="mt-5 rounded-full border border-orange-400 px-5 py-2 text-orange-300">Write advice</button>
    </article>)}</div>
    {selected !== null && <form onSubmit={publish} className="rounded-2xl border border-orange-400/50 bg-slate-950 p-6 space-y-4"><h2 className="text-xl font-semibold">Advice for assessment #{selected}</h2>
      <label className="block">Recommendation<select value={recommendation} onChange={(event) => setRecommendation(event.target.value)} className="mt-1 block rounded-lg border border-white/30 bg-slate-900 p-2">{adviceOptions.map((option) => <option key={option}>{option}</option>)}</select></label>
      <label className="block">Reason and practical benefit<textarea required minLength={20} rows={5} value={explanation} onChange={(event) => setExplanation(event.target.value)} className="mt-1 block w-full rounded-lg border border-white/30 bg-slate-900 p-3" /></label>
      <label className="block">Quoted price in pounds, if work is proposed<input type="number" min={0} value={price} onChange={(event) => setPrice(event.target.value)} className="mt-1 block rounded-lg border border-white/30 bg-slate-900 p-2" /></label>
      <label className="block"><input type="checkbox" checked={materialChange} onChange={(event) => setMaterialChange(event.target.checked)} className="mr-2" />Material scope or price change; require customer approval</label>
      <div className="flex gap-3"><button disabled={pending} className="rounded-full bg-orange-500 px-5 py-2 font-semibold text-black">Publish advice</button><button type="button" onClick={() => setSelected(null)} className="rounded-full border border-white/30 px-5 py-2">Cancel</button></div>
    </form>}
  </main>;
}
