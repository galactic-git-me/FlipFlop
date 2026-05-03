"use client";

import { useRef, useState } from "react";
import { CheckCircle2, XCircle, Loader2, Clock, Gem, Search } from "lucide-react";
import { ScanStatus, ScanSite } from "@/lib/api";

interface Props {
  status: ScanStatus;
}

export function ScanOverlay({ status }: Props) {
  const { total, completed, sites, total_found, total_gems } = status;
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#080c14]/96 backdrop-blur-sm overflow-auto py-8">
      {/* Header */}
      <div className="mb-8 text-center">
        <div className="flex items-center justify-center gap-3 mb-3">
          <div className="relative">
            <Search className="w-6 h-6 text-[#00dc82]" />
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-[#00dc82] rounded-full animate-ping" />
          </div>
          <h2 className="text-xl font-bold text-slate-100 tracking-wide">Scanning Markets</h2>
        </div>

        {/* Laser progress bar */}
        <div className="w-80 mx-auto">
          <div className="flex justify-between text-xs text-slate-500 mb-1.5">
            <span>{completed} of {total} sources</span>
            <span className="font-mono text-[#00dc82]">{pct}%</span>
          </div>
          <div className="h-1 bg-[#1e2d45] rounded-full overflow-hidden relative">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${pct}%`,
                background: "linear-gradient(90deg, #00dc82, #00b8ff)",
                boxShadow: "0 0 12px rgba(0,220,130,0.8)",
              }}
            />
            {/* Laser tip glow */}
            {pct > 0 && pct < 100 && (
              <div
                className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full"
                style={{
                  left: `calc(${pct}% - 6px)`,
                  background: "#00dc82",
                  boxShadow: "0 0 8px 4px rgba(0,220,130,0.6)",
                }}
              />
            )}
          </div>
        </div>
      </div>

      {/* 3D Source Cards grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 px-6 max-w-6xl w-full">
        {sites.map(site => (
          <SourceCard key={site.name} site={site} />
        ))}
      </div>

      {/* Bottom stats */}
      <div className="mt-8 flex items-center gap-10 text-center">
        <Stat label="Listings Found" value={total_found} color="text-slate-200" />
        <Stat label="New Gems" value={total_gems} color="text-[#00dc82]" gem />
        <Stat label="Completed" value={`${pct}%`} color="text-slate-200" />
      </div>
    </div>
  );
}

function Stat({ label, value, color, gem }: { label: string; value: number | string; color: string; gem?: boolean }) {
  return (
    <div>
      <div className={`text-2xl font-black ${color} flex items-center gap-1.5 justify-center`}>
        {gem && <Gem className="w-5 h-5" />}{value}
      </div>
      <div className="text-xs text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}

function SourceCard({ site }: { site: ScanSite }) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState("");
  const [glowPos, setGlowPos] = useState({ x: 50, y: 50 });

  const domain = (() => {
    try { return new URL(site.url).hostname.replace("www.", ""); } catch { return site.name.toLowerCase() + ".co.uk"; }
  })();

  const logoUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=128`;

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const card = cardRef.current;
    if (!card) return;
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    const rotX = ((y - cy) / cy) * -12;
    const rotY = ((x - cx) / cx) * 12;
    setTransform(`perspective(800px) rotateX(${rotX}deg) rotateY(${rotY}deg) scale3d(1.03,1.03,1.03)`);
    setGlowPos({ x: (x / rect.width) * 100, y: (y / rect.height) * 100 });
  };

  const handleMouseLeave = () => {
    setTransform("perspective(800px) rotateX(0deg) rotateY(0deg) scale3d(1,1,1)");
  };

  const isScanning = site.status === "scanning";
  const isDone = site.status === "done";
  const isError = site.status === "error";

  const borderColor = isDone
    ? "rgba(0,220,130,0.5)"
    : isScanning
    ? "rgba(0,220,130,0.8)"
    : isError
    ? "rgba(239,68,68,0.4)"
    : "rgba(30,45,69,0.8)";

  const bgGlow = isScanning
    ? "rgba(0,220,130,0.07)"
    : isDone
    ? "rgba(0,220,130,0.04)"
    : "rgba(10,17,25,0.95)";

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        transform,
        transition: transform.includes("scale3d(1,")
          ? "transform 0.6s cubic-bezier(0.23,1,0.32,1), box-shadow 0.3s ease, border-color 0.3s ease"
          : "transform 0.1s ease-out, box-shadow 0.3s ease, border-color 0.3s ease",
        transformStyle: "preserve-3d",
        borderRadius: "16px",
        border: `1px solid ${borderColor}`,
        background: bgGlow,
        position: "relative",
        overflow: "hidden",
        cursor: "default",
        boxShadow: isScanning
          ? "0 0 30px rgba(0,220,130,0.2), 0 8px 32px rgba(0,0,0,0.4)"
          : "0 8px 32px rgba(0,0,0,0.3)",
      }}
    >
      {/* Mouse-follow glow */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(circle at ${glowPos.x}% ${glowPos.y}%, rgba(0,220,130,0.12) 0%, transparent 60%)`,
          pointerEvents: "none",
        }}
      />

      {/* Source logo watermark */}
      <div
        style={{
          position: "absolute",
          right: -10,
          bottom: -10,
          width: 90,
          height: 90,
          opacity: isDone ? 0.12 : isScanning ? 0.18 : 0.07,
          transition: "opacity 0.5s ease",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={logoUrl}
          alt=""
          style={{ width: "100%", height: "100%", objectFit: "contain", imageRendering: "crisp-edges" }}
          onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
        />
      </div>

      {/* Scanning laser beam */}
      {isScanning && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            overflow: "hidden",
            borderRadius: "16px",
            pointerEvents: "none",
          }}
        >
          <div className="card-laser" />
        </div>
      )}

      {/* Card content */}
      <div style={{ padding: "16px", position: "relative", zIndex: 1, transformStyle: "preserve-3d" }}>
        {/* Status icon + name */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <div style={{ transform: "translateZ(20px)" }}>
            {isScanning ? (
              <Loader2 className="w-5 h-5 text-[#00dc82] animate-spin" />
            ) : isDone ? (
              <CheckCircle2 className="w-5 h-5 text-[#00dc82]" />
            ) : isError ? (
              <XCircle className="w-5 h-5 text-red-400" />
            ) : (
              <Clock className="w-5 h-5 text-slate-600" />
            )}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ color: isDone ? "#00dc82" : isScanning ? "#e2e8f0" : "#64748b", fontWeight: 600, fontSize: 14, transform: "translateZ(20px)" }}>
              {site.name}
            </div>
            <div style={{ color: "#475569", fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {domain}
            </div>
          </div>
        </div>

        {/* Status label */}
        <div style={{ transform: "translateZ(15px)" }}>
          {isScanning && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#00dc82", fontSize: 12 }}>
              <span className="inline-block w-1.5 h-1.5 bg-[#00dc82] rounded-full animate-pulse" />
              Scanning…
            </div>
          )}

          {isDone && (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "#64748b", fontSize: 12 }}>{site.found} listings</span>
              {site.gems > 0 && (
                <span style={{ color: "#00dc82", fontSize: 12, fontWeight: 700, display: "flex", alignItems: "center", gap: 4 }}>
                  <Gem className="w-3.5 h-3.5" /> {site.gems} gem{site.gems !== 1 ? "s" : ""}
                </span>
              )}
              {site.gems === 0 && (
                <span style={{ color: "#374151", fontSize: 12 }}>No gems</span>
              )}
            </div>
          )}

          {isError && (
            <div style={{ color: "#f87171", fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {site.error || "Scan failed"}
            </div>
          )}

          {site.status === "pending" && (
            <span style={{ color: "#374151", fontSize: 12 }}>Queued…</span>
          )}
        </div>
      </div>

      <style>{`
        @keyframes cardLaser {
          0%   { top: -2px; opacity: 1; }
          48%  { top: calc(100% + 2px); opacity: 0.5; }
          49%  { top: -2px; opacity: 0; }
          50%  { opacity: 1; }
          100% { top: calc(100% + 2px); opacity: 0.8; }
        }
        .card-laser {
          position: absolute;
          left: 0; right: 0;
          height: 2px;
          background: linear-gradient(90deg, transparent, #00dc82, #00ffbb, #00dc82, transparent);
          box-shadow: 0 0 8px 2px rgba(0,220,130,0.8);
          animation: cardLaser 1.8s linear infinite;
        }
      `}</style>
    </div>
  );
}
