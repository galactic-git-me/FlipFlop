"use client";

import { usePathname, useRouter } from "next/navigation";
import Image from "next/image";
import { Bell, BellRing, Heart, Radio, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { PlaybookProposal } from "@/lib/types";
import { FavouritesModal } from "./FavouritesModal";

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
  "/price-alerts": "QUERY PRICE ALERTS...",
  "/community": "SEARCH COMMUNITY POSTS...",
};

export function TopCommandBar() {
  const pathname = usePathname();
  const router = useRouter();
  const placeholder = PLACEHOLDERS[pathname] ?? "QUERY MARKET DATA...";
  const [notifOpen, setNotifOpen] = useState(false);
  const [favouritesOpen, setFavouritesOpen] = useState(false);
  const [pendingProposals, setPendingProposals] = useState<PlaybookProposal[]>([]);
  const [alerts, setAlerts] = useState<Array<{ id: number; code: string; message: string; link_url?: string | null; created_at?: string | null }>>([]);
  const [priceAlertCount, setPriceAlertCount] = useState(0);
  const [toasts, setToasts] = useState<Array<{ id: string; text: string; linkUrl?: string | null; persistent?: boolean }>>([]);
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
        const [rows, alertRowsRaw, priceAlertRows] = await Promise.all([
          api.playbooks.proposals.list("pending"),
          api.alerts.list(100, false),
          api.priceAlerts.list().catch(() => ({ items: [], active_count: 0, triggered_count: 0 })),
        ]);
        if (!mounted) return;
        setPendingProposals(rows);
        const alertRows = (alertRowsRaw as Array<{ id: number; code: string; message: string; link_url?: string | null; created_at?: string | null }>)
          .slice(0, 25);
        setAlerts(alertRows);
        setPriceAlertCount(priceAlertRows.active_count);

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
              linkUrl: a.link_url ?? null,
              // Favourite gem matches must be manually dismissed (clicking
              // navigates to the listing) rather than auto-expiring like
              // other alert toasts.
              persistent: a.code === "favourite_gem_match",
            }));
            setToasts((prev) => [...alertToasts, ...prev].slice(0, 8));
            seenAlertIdsRef.current = new Set([...seenAlertIdsRef.current, ...newAlerts.map((a) => a.id)]);
            for (const a of newAlerts) {
              if (a.code === "flip_resale_detected") {
                triggerConfetti();
              }
            }
            for (const t of alertToasts) {
              if (t.persistent) continue;
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

  const [notifTab, setNotifTab] = useState<"all" | "errors" | "flips" | "proposals" | "favourites" | "system">("all");
  const [clearing, setClearing] = useState(false);

  const clearAll = async () => {
    setClearing(true);
    try {
      await Promise.all(alerts.map((a) => api.alerts.ack(a.id).catch(() => {})));
      setAlerts([]);
      seenAlertIdsRef.current = new Set();
    } finally {
      setClearing(false);
    }
  };

  const allNotifs = useMemo(
    () => [
      ...pendingProposals.map((n) => ({
        key: `proposal-${n.id}`,
        kind: "proposal" as const,
        tab: "proposals" as const,
        title: `${n.action} Proposal`,
        name: n.playbook_name ?? "Unnamed playbook",
        reason: n.reason ?? "",
      })),
      ...alerts.map((a) => {
        const code = (a.code ?? "").toLowerCase();
        const msg  = (a.message ?? "").toLowerCase();
        const tab =
          code === "favourite_gem_match"
            ? ("favourites" as const)
            : code.includes("fail") || code.includes("error") || msg.includes("failed") || msg.includes("error")
            ? ("errors" as const)
            : code.includes("flip") || code.includes("resale") || code.includes("sale") || code.includes("sold")
            ? ("flips" as const)
            : ("system" as const);
        return {
          key: `alert-${a.id}`,
          kind: "alert" as const,
          tab,
          title: tab === "errors" ? "Error" : tab === "flips" ? "Flip Alert" : tab === "favourites" ? "Favourite Match" : "System",
          name: a.message,
          reason: a.code,
          createdAt: a.created_at,
          linkUrl: a.link_url ?? null,
        };
      }),
    ],
    [pendingProposals, alerts],
  );

  const tabCounts = useMemo(() => ({
    all:        allNotifs.length,
    errors:     allNotifs.filter(n => n.tab === "errors").length,
    flips:      allNotifs.filter(n => n.tab === "flips").length,
    proposals:  allNotifs.filter(n => n.tab === "proposals").length,
    favourites: allNotifs.filter(n => n.tab === "favourites").length,
    system:     allNotifs.filter(n => n.tab === "system").length,
  }), [allNotifs]);

  const notifList = useMemo(
    () => (notifTab === "all" ? allNotifs : allNotifs.filter(n => n.tab === notifTab)).slice(0, 20),
    [allNotifs, notifTab],
  );

  const pendingCount = pendingProposals.length + alerts.length;

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
          <Image src="/pics/logo_simple_no_bg.png" alt="FlipFlop" width={240} height={120} className="h-[120px] w-auto object-contain" />
        </div>
        <div className="node-top-icons relative">
          <button
            type="button"
            onClick={() => router.push("/sources")}
            aria-label="Source activity"
            title="Source activity"
          >
            <Radio className="h-4 w-4 transition-colors hover:text-cyan-300" />
          </button>
          <button
            type="button"
            onClick={() => setFavouritesOpen(true)}
            aria-label="Favourites"
          >
            <Heart className="h-4 w-4 hover:text-rose-400 transition-colors" />
          </button>
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
          <button
            type="button"
            onClick={() => router.push("/price-alerts")}
            className="relative cursor-pointer"
            aria-label={`Price alerts${priceAlertCount ? ` (${priceAlertCount} active)` : ""}`}
            title="Price alerts"
          >
            <BellRing className="h-4 w-4 transition-colors hover:text-amber-300" />
            {priceAlertCount > 0 && (
              <span className="absolute -top-1.5 -right-2 min-w-[16px] h-4 px-1 rounded-full bg-amber-400 text-[10px] leading-4 text-[#1b1200] font-bold text-center">
                {priceAlertCount > 99 ? "99+" : priceAlertCount}
              </span>
            )}
          </button>
          {notifOpen && (
            <div className="absolute right-0 top-7 w-[400px] rounded-xl border border-white/10 bg-[#0b111d]/98 backdrop-blur-md shadow-2xl z-50 flex flex-col" style={{ maxHeight: "480px" }}>

              {/* Header */}
              <div className="flex items-center justify-between px-3 pt-3 pb-2 border-b border-white/8 shrink-0">
                <span className="text-xs uppercase tracking-wider text-slate-300 font-semibold">Notifications</span>
                <button
                  onClick={clearAll}
                  disabled={clearing || alerts.length === 0}
                  className="text-[10px] px-2 py-0.5 rounded border border-red-500/30 text-red-400 hover:bg-red-500/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  {clearing ? "Clearing…" : "Clear All"}
                </button>
              </div>

              {/* Tabs */}
              <div className="flex gap-0 border-b border-white/8 shrink-0">
                {(["all", "errors", "flips", "proposals", "favourites", "system"] as const).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setNotifTab(tab)}
                    className={`flex-1 py-1.5 text-[10px] uppercase tracking-wide font-medium transition-colors relative ${
                      notifTab === tab
                        ? "text-[#00dc82]"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {tab}
                    {tabCounts[tab] > 0 && (
                      <span className={`ml-1 px-1 rounded-full text-[9px] font-bold ${
                        tab === "errors"     ? "bg-red-500/20 text-red-400" :
                        tab === "flips"      ? "bg-[#00dc82]/20 text-[#00dc82]" :
                        tab === "favourites" ? "bg-rose-500/20 text-rose-400" :
                        "bg-slate-700 text-slate-400"
                      }`}>
                        {tabCounts[tab]}
                      </span>
                    )}
                    {notifTab === tab && (
                      <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#00dc82] rounded-full" />
                    )}
                  </button>
                ))}
              </div>

              {/* Notification list */}
              <div className="overflow-y-auto flex-1 p-2 space-y-1.5">
                {notifList.length === 0 ? (
                  <div className="text-sm text-slate-500 text-center py-6">No notifications in this category.</div>
                ) : (
                  notifList.map((n) => {
                    const borderColor =
                      n.tab === "errors"     ? "border-red-500/30 bg-red-500/5" :
                      n.tab === "flips"      ? "border-[#00dc82]/25 bg-[#00dc82]/5" :
                      n.tab === "proposals"  ? "border-cyan-500/25 bg-cyan-500/5" :
                      n.tab === "favourites" ? "border-rose-500/25 bg-rose-500/5" :
                                              "border-white/8 bg-white/3";
                    const titleColor =
                      n.tab === "errors"     ? "text-red-400" :
                      n.tab === "flips"      ? "text-[#00dc82]" :
                      n.tab === "proposals"  ? "text-cyan-400" :
                      n.tab === "favourites" ? "text-rose-400" :
                                              "text-slate-400";
                    const linkUrl = "linkUrl" in n ? n.linkUrl : null;
                    return (
                      <div
                        key={n.key}
                        onClick={linkUrl ? () => { setNotifOpen(false); router.push(linkUrl); } : undefined}
                        className={`rounded-lg border p-2.5 ${borderColor} ${linkUrl ? "cursor-pointer hover:brightness-110" : ""}`}
                      >
                        <div className={`text-[10px] uppercase tracking-wide font-semibold ${titleColor}`}>{n.title}</div>
                        <div className="text-xs text-slate-100 mt-0.5 leading-snug">{n.name}</div>
                        {n.reason && <div className="text-[10px] text-slate-500 mt-1 font-mono line-clamp-1">{n.reason}</div>}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
    {/* Toast notifications */}
    <div className="fixed top-16 right-5 z-[70] space-y-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          onClick={() => {
            setToasts((prev) => prev.filter((x) => x.id !== t.id));
            if (t.linkUrl) router.push(t.linkUrl);
          }}
          className={`pointer-events-auto rounded-lg border px-3 py-2 text-sm shadow-xl transition ${
            t.persistent
              ? "border-rose-400/40 bg-[#22081a]/95 text-rose-100 cursor-pointer hover:brightness-110"
              : "border-[#00dc82]/30 bg-[#062218]/95 text-[#baf6d8]"
          } ${t.linkUrl && !t.persistent ? "cursor-pointer hover:brightness-110" : ""}`}
        >
          {t.text}
          {t.persistent && <div className="text-[10px] text-rose-300/70 mt-1">Click to view listing & dismiss</div>}
        </div>
      ))}
    </div>
    <FavouritesModal open={favouritesOpen} onClose={() => setFavouritesOpen(false)} />
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
