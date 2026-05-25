"use client";

import { usePathname } from "next/navigation";
import Image from "next/image";
import { Bell, Radio, Search, UserCircle2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { PlaybookProposal } from "@/lib/types";

const PLACEHOLDERS: Record<string, string> = {
  "/": "QUERY MARKET DATA...",
  "/opportunities": "QUERY SOURCING SIGNALS...",
  "/chat": "QUERY BUILD WIZARD...",
  "/flips": "QUERY_SYSTEM_INVENTORY...",
  "/playbooks": "SEARCH PLAYBOOKS...",
  "/parts": "QUERY COMPONENT MARKET...",
  "/selling": "QUERY SOLD PIPELINE...",
  "/intel": "QUERY ANALYTICS...",
  "/logs": "QUERY AI INSIGHTS...",
  "/settings": "QUERY SETTINGS...",
};

export function TopCommandBar() {
  const pathname = usePathname();
  const placeholder = PLACEHOLDERS[pathname] ?? "QUERY MARKET DATA...";
  const [notifOpen, setNotifOpen] = useState(false);
  const [pendingProposals, setPendingProposals] = useState<PlaybookProposal[]>([]);
  const [toasts, setToasts] = useState<Array<{ id: number; text: string }>>([]);
  const seenIdsRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const rows = await api.playbooks.proposals.list("pending");
        if (!mounted) return;
        setPendingProposals(rows);
        if (seenIdsRef.current.size === 0) {
          const seeded = new Set(rows.map((r) => r.id));
          seenIdsRef.current = seeded;
          return;
        }
        const newRows = rows.filter((r) => !seenIdsRef.current.has(r.id));
        if (newRows.length > 0) {
          const newToasts = newRows.slice(0, 3).map((r) => ({
            id: r.id,
            text: `Playbook ${r.action.toLowerCase()} proposal: ${r.playbook_name ?? "Unnamed"}`,
          }));
          setToasts((prev) => [...newToasts, ...prev].slice(0, 5));
          const nextSeen = new Set([...seenIdsRef.current, ...newRows.map((r) => r.id)]);
          seenIdsRef.current = nextSeen;
          for (const t of newToasts) {
            setTimeout(() => {
              setToasts((prev) => prev.filter((x) => x.id !== t.id));
            }, 6000);
          }
        }
      } catch {
        // keep topbar resilient; no-op
      }
    };
    void load();
    const id = setInterval(() => { void load(); }, 25000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  const pendingCount = pendingProposals.length;
  const notifList = useMemo(() => pendingProposals.slice(0, 8), [pendingProposals]);

  return (
    <>
    <header className="node-topbar">
      <div className="node-search-wrap">
        <Search className="h-4 w-4 text-[var(--nf-outline)]" />
        <input className="node-search-input" placeholder={placeholder} />
      </div>

      <div className="node-topbar-right">
        <div className="node-live-chip">
          <span className="node-live-dot" />
          <Image src="/pics/logo.png" alt="FlipFlop" width={120} height={60} className="h-[60px] w-auto object-contain" />
        </div>
        <div className="node-top-icons relative">
          <Radio className="h-4 w-4" />
          <button
            type="button"
            onClick={() => setNotifOpen((v) => !v)}
            className="relative"
            aria-label="Notifications"
          >
            <Bell className="h-4 w-4" />
            {pendingCount > 0 && (
              <span className="absolute -top-1.5 -right-2 min-w-[16px] h-4 px-1 rounded-full bg-[#00dc82] text-[10px] leading-4 text-[#04120d] font-bold text-center">
                {pendingCount > 9 ? "9+" : pendingCount}
              </span>
            )}
          </button>
          <UserCircle2 className="h-5 w-5" />

          {notifOpen && (
            <div className="absolute right-0 top-7 w-[360px] max-h-[360px] overflow-auto rounded-xl border border-white/10 bg-[#0b111d]/95 backdrop-blur-md p-3 shadow-2xl z-50">
              <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">Notifications</div>
              {notifList.length === 0 ? (
                <div className="text-sm text-slate-500">No new playbook changes.</div>
              ) : (
                <div className="space-y-2">
                  {notifList.map((n) => (
                    <div key={n.id} className="rounded-lg border border-[#00dc82]/20 bg-[#00dc82]/8 p-2.5">
                      <div className="text-xs text-[#8debc2] uppercase tracking-wide">{n.action} Proposal</div>
                      <div className="text-sm text-slate-100 mt-0.5">{n.playbook_name ?? "Unnamed playbook"}</div>
                      {n.reason && <div className="text-xs text-slate-400 mt-1 line-clamp-2">{n.reason}</div>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
    {/* Toast notifications for new playbook changes */}
    <div className="fixed top-16 right-5 z-[70] space-y-2 pointer-events-none">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto rounded-lg border border-[#00dc82]/30 bg-[#062218]/95 text-[#baf6d8] px-3 py-2 text-sm shadow-xl">
          {t.text}
        </div>
      ))}
    </div>
    </>
  );
}
