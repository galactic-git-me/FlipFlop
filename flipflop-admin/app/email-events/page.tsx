"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
type Event = Awaited<ReturnType<typeof api.emailEvents.list>>[number];
export default function EmailEventsPage() {
  const [events, setEvents] = useState<Event[]>([]);
  useEffect(() => { void api.emailEvents.list().then(setEvents).catch(() => setEvents([])); }, []);
  return <div className="space-y-6"><div><h1 className="text-2xl font-semibold text-white">Email Events</h1><p className="mt-1 text-sm text-slate-400">Listing and delivery emails retained by the IMAP monitor.</p></div><div className="space-y-2">{events.map((event) => <a key={event.id} href={`/email-events/${event.id}`} className="block rounded-xl border border-slate-700 bg-[#0b121d]/90 p-4 hover:border-emerald-400/50"><div className="flex justify-between gap-4"><span className="font-medium text-white">{event.subject || "(no subject)"}</span><span className="text-xs text-slate-500">{event.received_at ? new Date(event.received_at).toLocaleString("en-GB") : ""}</span></div><p className="mt-1 text-xs text-slate-400">{event.summary}</p><p className="mt-2 text-[11px] text-slate-500">{event.marketplace || "unknown marketplace"} · {event.sender}</p></a>)}{events.length === 0 && <p className="rounded-xl border border-slate-800 p-8 text-center text-slate-500">No email events recorded yet.</p>}</div></div>;
}
