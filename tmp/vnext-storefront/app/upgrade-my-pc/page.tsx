"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";

type Assessment = {
  id: number; status: string; desired_outcome: string; budget_gbp: number;
  advice: { recommendation: string; explanation: string; keep: string[]; upgrade: string[]; optional: string[]; dont_spend_here: string[]; transform: string[]; quoted_price_gbp: number | null } | null;
  approval_required: boolean; scope_revision: number;
};

export default function UpgradeMyPcPage() {
  const { token, loading, isAuthenticated } = useAuth();
  const [spec, setSpec] = useState("");
  const [outcome, setOutcome] = useState("");
  const [budget, setBudget] = useState(300);
  const [photoUrl, setPhotoUrl] = useState("");
  const [reportUrl, setReportUrl] = useState("");
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!token) return;
    fetch("/api/upgrades/mine", { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => response.ok ? response.json() : [])
      .then(setAssessments).catch(() => setError("Could not load your assessments."));
  }, [token]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    setPending(true); setError("");
    try {
      const response = await fetch("/api/upgrades", {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ submitted_spec: { description: spec }, desired_outcome: outcome,
          budget_gbp: budget, photo_urls: photoUrl ? [photoUrl] : [], system_report_url: reportUrl || null }),
      });
      if (!response.ok) throw new Error("We could not submit your assessment. Please check the details and try again.");
      const created: Assessment = await response.json();
      setAssessments((current) => [created, ...current]);
      setSpec(""); setOutcome(""); setPhotoUrl(""); setReportUrl("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Please try again."); }
    finally { setPending(false); }
  }

  async function approve(id: number) {
    if (!token) return;
    const response = await fetch(`/api/upgrades/${id}/approve`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) { setError("We could not record your approval."); return; }
    const updated: Assessment = await response.json();
    setAssessments((current) => current.map((item) => item.id === id ? updated : item));
  }

  return <main className="mx-auto max-w-4xl px-5 py-20 text-white">
    <p className="mb-4 text-sm uppercase tracking-[0.3em] text-blue-300">Upgrade & transformation</p>
    <h1 className="text-4xl font-bold sm:text-6xl" style={{ fontFamily: "var(--font-heading)" }}>Love your PC again.</h1>
    <p className="mt-6 max-w-2xl text-lg text-slate-300">You may not need a new computer. Tell us what feels limiting and we will review what to keep, what to improve, and where we would save your money.</p>
    {loading ? <p className="mt-12">Loading…</p> : !isAuthenticated ? <div className="mt-12 rounded-2xl border border-white/20 bg-slate-950/80 p-6"><p>Sign in to submit and track your assessment.</p><Link href="/login?next=/upgrade-my-pc" className="mt-5 inline-block rounded-full bg-orange-500 px-6 py-3 font-semibold text-black">Sign in</Link></div> : <>
      <form onSubmit={submit} className="mt-12 space-y-6 rounded-3xl border border-white/20 bg-slate-950/80 p-6 sm:p-10">
        <h2 className="text-2xl font-semibold">Tell us about your current PC</h2>
        <label className="block">Model or known specification<textarea required rows={4} value={spec} onChange={(event) => setSpec(event.target.value)} placeholder="For example: Ryzen 5, 16GB RAM, RTX 3060. It is fine if you are not sure." className="mt-2 w-full rounded-xl border border-white/30 bg-slate-900 p-3" /></label>
        <label className="block">What do you want it to do better?<textarea required minLength={10} rows={4} value={outcome} onChange={(event) => setOutcome(event.target.value)} className="mt-2 w-full rounded-xl border border-white/30 bg-slate-900 p-3" /></label>
        <label className="block">Budget in pounds<input required type="number" min={0} max={20000} value={budget} onChange={(event) => setBudget(Number(event.target.value))} className="mt-2 block w-40 rounded-xl border border-white/30 bg-slate-900 p-3" /></label>
        <label className="block">Photo link (optional)<input type="url" value={photoUrl} onChange={(event) => setPhotoUrl(event.target.value)} className="mt-2 w-full rounded-xl border border-white/30 bg-slate-900 p-3" /></label>
        <label className="block">System report link (optional)<input type="url" value={reportUrl} onChange={(event) => setReportUrl(event.target.value)} className="mt-2 w-full rounded-xl border border-white/30 bg-slate-900 p-3" /></label>
        <p className="text-sm text-slate-400">We will validate the actual machine before work begins. Any material change in price or scope requires your approval.</p>
        <button disabled={pending} className="rounded-full bg-orange-500 px-6 py-3 font-semibold text-black disabled:opacity-50">{pending ? "Submitting…" : "Request an assessment"}</button>
      </form>
      {error && <p role="alert" className="mt-5 text-red-300">{error}</p>}
      <section className="mt-14"><h2 className="text-2xl font-semibold">Your assessments</h2><div className="mt-5 space-y-4">{assessments.map((item) => <article key={item.id} className="rounded-2xl border border-white/20 bg-slate-950/80 p-6"><p className="text-sm uppercase tracking-widest text-blue-300">{item.status.replaceAll("_", " ")}</p><h3 className="mt-2 font-semibold">{item.desired_outcome}</h3>{item.advice && <div className="mt-4"><strong>{item.advice.recommendation.replaceAll("_", " ")}</strong><p className="mt-2 text-slate-300">{item.advice.explanation}</p>{item.advice.quoted_price_gbp !== null && <p className="mt-3">Quoted price: £{item.advice.quoted_price_gbp}</p>}{[["Keep", item.advice.keep], ["Upgrade", item.advice.upgrade], ["Optional", item.advice.optional], ["Don't spend here", item.advice.dont_spend_here], ["Transform", item.advice.transform]].map(([title, values]) => Array.isArray(values) && values.length > 0 ? <div key={title as string} className="mt-4"><h4 className="font-medium">{title}</h4><ul className="list-disc pl-6 text-slate-300">{values.map((value) => <li key={value}>{value}</li>)}</ul></div> : null)}</div>}{item.approval_required && <button onClick={() => approve(item.id)} className="mt-5 rounded-full border border-orange-400 px-5 py-2 text-orange-300">Approve revised scope and quoted price</button>}</article>)}</div></section>
    </>}
  </main>;
}
