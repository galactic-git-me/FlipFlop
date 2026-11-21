"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { api, type ManualBuildSaleAlert } from "@/lib/api";
import { getApprovalSnapshot } from "@/lib/approvals";

const POLL_INTERVAL_MS = 30_000;
const CONFETTI_COLORS = ["#fb7185", "#fbbf24", "#34d399", "#38bdf8", "#c084fc", "#f97316"];
const CONFETTI = Array.from({ length: 64 }, (_, index) => ({
  left: `${(index * 37) % 100}%`,
  delay: `${(index % 16) * 0.055}s`,
  duration: `${2.6 + (index % 9) * 0.18}s`,
  color: CONFETTI_COLORS[index % CONFETTI_COLORS.length],
  drift: `${((index * 29) % 220) - 110}px`,
  rotation: `${(index * 83) % 900}deg`,
  width: `${6 + (index % 4) * 2}px`,
  height: `${9 + (index % 5) * 2}px`,
}));

function channelName(channel: string | null) {
  if (!channel) return "Channel not recorded";
  if (channel === "ebay" || channel === "ebay_uk") return "eBay";
  if (channel === "flipflop_shop" || channel === "storefront") return "FlipFlop.shop";
  return channel.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function money(amount: number | null, currency: string) {
  if (amount == null || !Number.isFinite(amount)) return "Sale price not recorded";
  try {
    return new Intl.NumberFormat("en-GB", { style: "currency", currency }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

export function SoldBuildAlerts() {
  const pathname = usePathname();
  const [soldBuilds, setSoldBuilds] = useState<ManualBuildSaleAlert[]>([]);
  const [open, setOpen] = useState(false);
  const [celebrating, setCelebrating] = useState(false);
  const initialized = useRef(false);
  const knownBuildIds = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (pathname === "/login") return;
    let active = true;

    const refresh = async () => {
      try {
        // A protected inventory endpoint is the source of truth. Avoid
        // flashing an empty alert while the session is still being restored.
        await getApprovalSnapshot(true).catch(() => null);
        const rows = await api.manualBuilds.soldAlerts();
        if (!active) return;
        const sold = rows.filter((build) => build.status === "sold" && !["dispatched", "delivered"].includes(build.dispatch_status ?? ""));
        const newlyDetected = sold.filter((build) => !knownBuildIds.current.has(build.id));
        knownBuildIds.current = new Set(sold.map((build) => build.id));
        setSoldBuilds(sold);
        if (!initialized.current) {
          setOpen(sold.length > 0);
          setCelebrating(sold.some((build) => build.sale_channel));
        } else if (newlyDetected.length > 0) {
          setOpen(sold.length > 0);
          setCelebrating(true);
        }
        initialized.current = true;
      } catch {
        // Keep last known state while the API is unavailable or the user is signed out.
      }
    };

    void refresh();
    const timer = window.setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [pathname, soldBuilds.length]);

  useEffect(() => {
    if (!celebrating) return;
    const timer = window.setTimeout(() => setCelebrating(false), 4_000);
    return () => window.clearTimeout(timer);
  }, [celebrating]);

  useEffect(() => {
    if (soldBuilds.length === 0) {
      setOpen(false);
      setCelebrating(false);
    }
  }, [soldBuilds.length]);

  if (pathname === "/login") return null;
  const confirmedSaleCount = soldBuilds.filter((build) => build.sale_channel).length;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={`Sold builds: ${soldBuilds.length}`}
        title={`${soldBuilds.length} builds currently marked sold`}
        className={`relative inline-flex items-center rounded-md border px-2.5 py-1 text-xs font-bold transition-colors ${soldBuilds.length ? "sold-build-counter border-rose-400/50 bg-rose-500/15 text-rose-200" : "border-white/10 text-slate-400 hover:text-white"}`}
      >
        Sold
        <span className="ml-1.5 tabular-nums">{soldBuilds.length}</span>
      </button>

      {open && soldBuilds.length > 0 && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center overflow-hidden bg-black/75 p-4" role="presentation">
          {celebrating && (
            <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden="true">
              {CONFETTI.map((piece, index) => (
                <i
                  key={index}
                  className="sale-confetti-piece"
                  style={{
                    left: piece.left,
                    backgroundColor: piece.color,
                    width: piece.width,
                    height: piece.height,
                    animationDelay: piece.delay,
                    animationDuration: piece.duration,
                    "--confetti-drift": piece.drift,
                    "--confetti-rotation": piece.rotation,
                  } as CSSProperties}
                />
              ))}
            </div>
          )}
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="sold-build-alert-title"
            className="relative z-[1] max-h-[85vh] w-full max-w-2xl overflow-hidden rounded-2xl border border-rose-400/40 bg-[#0b111d] shadow-2xl shadow-rose-950/40"
          >
            <header className="border-b border-white/10 px-6 py-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-rose-300">
                {confirmedSaleCount > 0 ? "Sale confirmed" : "Sale needs review"}
              </p>
              <h2 id="sold-build-alert-title" className="mt-1 text-2xl font-semibold text-white">
                {confirmedSaleCount > 0
                  ? `Congratulations${celebrating ? "!" : ""} — ${confirmedSaleCount} confirmed ${confirmedSaleCount === 1 ? "sale" : "sales"}`
                  : `${soldBuilds.length} ${soldBuilds.length === 1 ? "build is" : "builds are"} marked sold`}
              </h2>
              <p className="mt-2 text-sm text-slate-300">
                This alert and the pulsing Sold counter stay active while these builds remain in Sold status.
              </p>
            </header>
            <ul className="max-h-[52vh] divide-y divide-white/10 overflow-y-auto">
              {soldBuilds.map((build) => (
                <li key={build.id} className="flex items-start justify-between gap-4 px-6 py-4">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-white">{build.name}</p>
                    <p className="mt-1 text-xs text-slate-400">Build #{build.id} · {build.component_count} components</p>
                    <p className="mt-2 text-sm font-semibold text-emerald-200">{money(build.sale_price, build.sale_currency || "GBP")}</p>
                    <p className="mt-1 text-xs text-rose-200">
                      Sold through {channelName(build.sale_channel)}{build.sale_account ? ` · seller ${build.sale_account}` : ""}
                    </p>
                    {build.sale_order_id && <p className="mt-1 text-[11px] text-slate-400">Order {build.sale_order_id}</p>}
                    {build.sale_confirmed_at && <p className="mt-1 text-[11px] text-slate-500">Confirmed {new Date(build.sale_confirmed_at).toLocaleString("en-GB")}</p>}
                    {!build.sale_channel && <p className="mt-1 text-xs text-amber-200">The build is marked sold, but its sale channel and order proof are not recorded.</p>}
                  </div>
                  <div className="flex shrink-0 flex-col gap-2">
                    {build.sale_listing_url && (
                      <a href={build.sale_listing_url} target="_blank" rel="noreferrer" className="rounded-md border border-sky-300/30 px-3 py-2 text-center text-xs font-semibold text-sky-200 hover:bg-sky-400/10">Open sold listing</a>
                    )}
                    <Link href={`/dispatch-zone?tab=delivery&buildId=${build.id}`} onClick={() => setOpen(false)} className="rounded-md border border-emerald-300/30 px-3 py-2 text-center text-xs font-semibold text-emerald-200 hover:bg-emerald-400/10">Open dispatch</Link>
                  </div>
                </li>
              ))}
            </ul>
            <footer className="flex justify-end border-t border-white/10 px-6 py-4">
              <button
                type="button"
                onClick={() => { setOpen(false); setCelebrating(false); }}
                className="rounded-md bg-white/10 px-4 py-2 text-sm font-medium text-white hover:bg-white/15"
              >
                Close for now
              </button>
            </footer>
          </section>
        </div>
      )}
      <style jsx global>{`
        .sold-build-counter { animation: sold-counter-pulse 1.35s ease-in-out infinite; }
        @keyframes sold-counter-pulse {
          0%, 100% { box-shadow: 0 0 0 rgba(251, 113, 133, 0); }
          50% { box-shadow: 0 0 12px rgba(251, 113, 133, .55); }
        }
        .sale-confetti-piece {
          position: absolute;
          top: -20px;
          border-radius: 2px;
          opacity: 0;
          animation-name: sale-confetti-fall;
          animation-timing-function: cubic-bezier(.15,.65,.65,.95);
          animation-fill-mode: both;
        }
        @keyframes sale-confetti-fall {
          0% { opacity: 0; transform: translate3d(0, -10vh, 0) rotate(0); }
          8% { opacity: 1; }
          100% { opacity: 0; transform: translate3d(var(--confetti-drift), 112vh, 0) rotate(var(--confetti-rotation)); }
        }
        @media (prefers-reduced-motion: reduce) {
          .sold-build-counter, .sale-confetti-piece { animation: none; }
          .sale-confetti-piece { display: none; }
        }
      `}</style>
    </>
  );
}
