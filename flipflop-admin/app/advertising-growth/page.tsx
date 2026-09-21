"use client";

import { FormEvent, useEffect, useState } from "react";
import { Check, Clock3, Megaphone, Plus, RefreshCw, Send, ShieldCheck } from "lucide-react";
import { apiUrl } from "@/lib/api";

type Post = { id: number; status: string; platforms: string[]; scheduled_for: string | null; needs_attention: string; revision?: { copy: string } };
type Centre = { approvals_pending: number; drafts: number; scheduled_today: number; published_today: number; accounts: Array<{ platform: string; health: string; capability: string }>; analytics: { website_sessions: number; utm_visits: number; freshness: string | null } };

async function growth<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(`/growth${path}`), { headers: { "Content-Type": "application/json" }, ...init });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || "Growth Engine request failed");
  return response.json();
}

export default function AdvertisingGrowthPage() {
  const [centre, setCentre] = useState<Centre | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [copy, setCopy] = useState("");
  const [platform, setPlatform] = useState("instagram");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [dashboard, postRows] = await Promise.all([growth<Centre>("/command-centre"), growth<{ items: Post[] }>("/social/posts")]);
      setCentre(dashboard); setPosts(postRows.items);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load Growth Engine"); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  async function createDraft(event: FormEvent) {
    event.preventDefault();
    if (!copy.trim()) return;
    try {
      await growth("/social/posts", { method: "POST", body: JSON.stringify({ platforms: [platform], copy: copy.trim() }) });
      setCopy(""); setMessage("Draft created. Submit it for validation and approval before publishing."); await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not create draft"); }
  }
  async function action(post: Post, endpoint: string, body?: object) {
    try { await growth(`/social/posts/${post.id}/${endpoint}`, { method: "POST", body: JSON.stringify(body ?? {}) }); await load(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Action failed"); }
  }

  const cards = centre ? [
    ["Awaiting approval", centre.approvals_pending], ["Drafts", centre.drafts], ["Scheduled today", centre.scheduled_today], ["Published today", centre.published_today], ["Website sessions", centre.analytics.website_sessions], ["UTM visits", centre.analytics.utm_visits],
  ] : [];
  return <main className="p-6 space-y-6 max-w-7xl text-slate-100">
    <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div><div className="flex items-center gap-2"><Megaphone className="w-6 h-6 text-cyan-300" /><h1 className="text-2xl font-bold">Advertising &amp; Growth</h1></div><p className="mt-1 text-sm text-slate-400">Marketing MVP: reviewed social publishing and observed website analytics.</p></div>
      <button onClick={() => void load()} className="inline-flex w-fit items-center gap-2 rounded-md border border-cyan-300/25 px-3 py-2 text-sm text-cyan-100 transition-colors hover:bg-cyan-300/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</button>
    </section>
    {message && <p role="status" className="rounded-md border border-cyan-300/20 bg-cyan-300/5 px-3 py-2 text-sm text-cyan-100">{message}</p>}
    <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">{cards.map(([label, value]) => <div key={String(label)} className="rounded-xl border border-white/10 bg-slate-950/70 p-4"><p className="text-xs text-slate-400">{label}</p><p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p></div>)}</section>
    <section className="grid gap-6 xl:grid-cols-[.85fr_1.15fr]">
      <form onSubmit={createDraft} className="rounded-xl border border-white/10 bg-slate-950/70 p-5 space-y-4"><h2 className="flex items-center gap-2 font-semibold"><Plus className="h-4 w-4 text-cyan-300" />New social draft</h2><label className="block text-sm">Platform<select value={platform} onChange={e => setPlatform(e.target.value)} className="mt-1 w-full rounded-md border border-white/15 bg-slate-900 px-3 py-2"><option value="instagram">Instagram</option><option value="facebook">Facebook</option><option value="x">X</option></select></label><label className="block text-sm">Post copy<textarea value={copy} onChange={e => setCopy(e.target.value)} required rows={5} className="mt-1 w-full rounded-md border border-white/15 bg-slate-900 px-3 py-2" placeholder="Write a factual, on-brand post…" /></label><button className="inline-flex items-center gap-2 rounded-md bg-cyan-300 px-3 py-2 text-sm font-medium text-slate-950 transition-colors hover:bg-cyan-200"><Plus className="h-4 w-4" />Create draft</button></form>
      <div className="rounded-xl border border-white/10 bg-slate-950/70 p-5"><h2 className="mb-4 flex items-center gap-2 font-semibold"><Clock3 className="h-4 w-4 text-cyan-300" />Content calendar</h2><div className="space-y-3">{posts.length === 0 ? <p className="text-sm text-slate-400">No social posts yet.</p> : posts.map(post => <article key={post.id} className="rounded-lg border border-white/10 bg-slate-900/60 p-3"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="text-sm text-slate-200">{post.revision?.copy || "Untitled draft"}</p><p className="mt-1 text-xs text-slate-400">{post.platforms.join(", ")} · {post.status}{post.scheduled_for ? ` · ${new Date(post.scheduled_for).toLocaleString()}` : ""}</p>{post.needs_attention && <p className="mt-1 text-xs text-amber-200">{post.needs_attention}</p>}</div><div className="flex gap-2">{["draft", "validation_failed"].includes(post.status) && <button onClick={() => void action(post, "submit")} className="rounded border border-white/15 px-2 py-1 text-xs hover:bg-white/10">Submit</button>}{post.status === "review" && <button onClick={() => void action(post, "approval", { approve: true })} className="inline-flex items-center gap-1 rounded border border-emerald-300/30 px-2 py-1 text-xs text-emerald-100 hover:bg-emerald-300/10"><Check className="h-3 w-3" />Approve</button>}{post.status === "approved" && <button onClick={() => void action(post, "execute")} className="inline-flex items-center gap-1 rounded border border-cyan-300/30 px-2 py-1 text-xs text-cyan-100 hover:bg-cyan-300/10"><Send className="h-3 w-3" />Publish</button>}</div></div></article>)}</div></div>
    </section>
    <section className="rounded-xl border border-white/10 bg-slate-950/70 p-5"><h2 className="flex items-center gap-2 font-semibold"><ShieldCheck className="h-4 w-4 text-cyan-300" />Roadmap controls</h2><p className="mt-2 text-sm text-slate-400">Blog publishing, newsletters, offers, loyalty, paid advertising, attribution, and automated optimisation are unavailable until their release gates and connector contracts are approved.</p></section>
  </main>;
}
