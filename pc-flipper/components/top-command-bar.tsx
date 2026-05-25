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
  const [alerts, setAlerts] = useState<Array<{ id: number; code: string; message: string; created_at?: string | null }>>([]);
  const [toasts, setToasts] = useState<Array<{ id: string; text: string }>>([]);
  const [confettiPieces, setConfettiPieces] = useState<Array<{ id: string; left: number; delay: number; duration: number; size: number; color: string; drift: number }>>([]);
  const seenProposalIdsRef = useRef<Set<number>>(new Set());
  const seenAlertIdsRef = useRef<Set<number>>(new Set());

  const triggerConfetti = () => {
    const colors = ["#00dc82", "#22d3ee", "#f59e0b", "#f43f5e", "#a78bfa", "#f97316"];
    const pieces = Array.from({ length: 90 }).map((_, i) => ({
      id: `c-${Date.now()}-${i}`,
      left: Math.random() * 100,
      delay: Math.random() * 0.9,
      duration: 2.8 + Math.random() * 2.2,
      size: 6 + Math.floor(Math.random() * 7),
      color: colors[Math.floor(Math.random() * colors.length)],
      drift: (Math.random() - 0.5) * 220,
    }));
    setConfettiPieces(pieces);
    setTimeout(() => setConfettiPieces([]), 5600);
  };

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const [rows, alertRowsRaw] = await Promise.all([
          api.playbooks.proposals.list("pending"),
          api.alerts.list(100, false),
        ]);
        if (!mounted) return;
        setPendingProposals(rows);
        const alertRows = (alertRowsRaw as Array<{ id: number; code: string; message: string; created_at?: string | null }>)
          .slice(0, 25);
        setAlerts(alertRows);

        if (seenProposalIdsRef.current.size === 0) {
          const seeded = new Set(rows.map((r) => r.id));
          seenProposalIdsRef.current = seeded;
        } else {
          const newRows = rows.filter((r) => !seenProposalIdsRef.current.has(r.id));
          if (newRows.length > 0) {
            const newToasts = newRows.slice(0, 3).map((r) => ({
              id: `proposal-${r.id}`,
              text: `Playbook ${r.action.toLowerCase()} proposal: ${r.playbook_name ?? "Unnamed"}`,
            }));
            setToasts((prev) => [...newToasts, ...prev].slice(0, 8));
            const nextSeen = new Set([...seenProposalIdsRef.current, ...newRows.map((r) => r.id)]);
            seenProposalIdsRef.current = nextSeen;
            for (const t of newToasts) {
              setTimeout(() => {
                setToasts((prev) => prev.filter((x) => x.id !== t.id));
              }, 6000);
            }
          }
        }

        if (seenAlertIdsRef.current.size === 0) {
          seenAlertIdsRef.current = new Set(alertRows.map((a) => a.id));
        } else {
          const newAlerts = alertRows.filter((a) => !seenAlertIdsRef.current.has(a.id));
          if (newAlerts.length > 0) {
            const alertToasts = newAlerts.slice(0, 3).map((a) => ({
              id: `alert-${a.id}`,
              text: a.message,
            }));
            setToasts((prev) => [...alertToasts, ...prev].slice(0, 8));
            seenAlertIdsRef.current = new Set([...seenAlertIdsRef.current, ...newAlerts.map((a) => a.id)]);
            for (const a of newAlerts) {
              if (a.code === "flip_resale_detected") {
                triggerConfetti();
              }
            }
            for (const t of alertToasts) {
              setTimeout(() => {
                setToasts((prev) => prev.filter((x) => x.id !== t.id));
              }, 7000);
            }
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

  const pendingCount = pendingProposals.length + alerts.length;
  const notifList = useMemo(
    () => [
      ...pendingProposals.slice(0, 6).map((n) => ({
        key: `proposal-${n.id}`,
        kind: "proposal" as const,
        title: `${n.action} Proposal`,
        name: n.playbook_name ?? "Unnamed playbook",
        reason: n.reason ?? "",
      })),
      ...alerts.slice(0, 6).map((a) => ({
        key: `alert-${a.id}`,
        kind: "alert" as const,
        title: "Alert",
        name: a.message,
        reason: a.code,
      })),
    ].slice(0, 10),
    [pendingProposals, alerts],
  );

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
                <div className="text-sm text-slate-500">No new notifications.</div>
              ) : (
                <div className="space-y-2">
                  {notifList.map((n) => (
                    <div key={n.key} className="rounded-lg border border-[#00dc82]/20 bg-[#00dc82]/8 p-2.5">
                      <div className="text-xs text-[#8debc2] uppercase tracking-wide">{n.title}</div>
                      <div className="text-sm text-slate-100 mt-0.5">{n.name}</div>
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
    {/* Toast notifications */}
    <div className="fixed top-16 right-5 z-[70] space-y-2 pointer-events-none">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto rounded-lg border border-[#00dc82]/30 bg-[#062218]/95 text-[#baf6d8] px-3 py-2 text-sm shadow-xl">
          {t.text}
        </div>
      ))}
    </div>
    {confettiPieces.length > 0 && (
      <div className="pointer-events-none fixed inset-0 z-[80] overflow-hidden" aria-hidden="true">
        {confettiPieces.map((p) => (
          <span
            key={p.id}
            className="ff-confetti-piece"
            style={{
              left: `${p.left}%`,
              width: `${p.size}px`,
              height: `${Math.max(4, p.size * 0.56)}px`,
              backgroundColor: p.color,
              animationDelay: `${p.delay}s`,
              animationDuration: `${p.duration}s`,
              ["--ff-drift" as string]: `${p.drift}px`,
            }}
          />
        ))}
      </div>
    )}
    <style jsx global>{`
      .ff-confetti-piece {
        position: absolute;
        top: -16px;
        opacity: 0.95;
        transform: translate3d(0, 0, 0) rotate(0deg);
        animation-name: ff-confetti-fall;
        animation-timing-function: cubic-bezier(0.2, 0.7, 0.25, 1);
        animation-fill-mode: forwards;
        border-radius: 1px;
      }
      @keyframes ff-confetti-fall {
        0% { transform: translate3d(0, -10px, 0) rotate(0deg); opacity: 0.95; }
        100% { transform: translate3d(var(--ff-drift), 110vh, 0) rotate(820deg); opacity: 0.2; }
      }
    `}</style>
    </>
  );
}
