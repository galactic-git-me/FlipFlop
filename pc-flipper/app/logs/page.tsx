"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Terminal, Pause, Play, Trash2, Download, Circle } from "lucide-react";

interface LogEntry {
  ts: string;
  level: string;
  msg: string;
  extra: Record<string, string>;
}
type LevelFilter = "ALL" | "info" | "warning" | "error" | "debug";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8088/api";

function levelColor(level: string) {
  switch (level.toLowerCase()) {
    case "error":
    case "critical": return "text-red-400";
    case "warning":
    case "warn":     return "text-yellow-400";
    case "debug":    return "text-slate-600";
    default:         return "text-emerald-400";
  }
}

function formatTs(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("en-GB", { hour12: false }) +
      "." + String(d.getMilliseconds()).padStart(3, "0");
  } catch { return iso.slice(11, 23); }
}

function fmtEntry(e: LogEntry) {
  const extras = Object.entries(e.extra).map(([k, v]) => `${k}=${v}`).join(" ");
  return extras ? `${e.msg}  ${extras}` : e.msg;
}

const LEVELS: LevelFilter[] = ["ALL", "info", "warning", "error", "debug"];

export default function LogsPage() {
  const [lines, setLines] = useState<LogEntry[]>([]);
  const [paused, setPaused] = useState(false);
  const [levelFilter, setLevelFilter] = useState<LevelFilter>("ALL");
  const [search, setSearch] = useState("");
  const [connected, setConnected] = useState(false);
  const [total, setTotal] = useState(0);

  const bottomRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(false);
  const pendingRef = useRef<LogEntry[]>([]);

  useEffect(() => { pausedRef.current = paused; }, [paused]);

  const push = useCallback((batch: LogEntry[]) => {
    setLines(prev => {
      const next = [...prev, ...batch];
      return next.length > 2000 ? next.slice(-2000) : next;
    });
    setTotal(c => c + batch.length);
  }, []);

  useEffect(() => {
    if (!paused) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines, paused]);

  useEffect(() => {
    const id = setInterval(() => {
      if (!pausedRef.current && pendingRef.current.length > 0) {
        const batch = pendingRef.current;
        pendingRef.current = [];
        push(batch);
      }
    }, 150);
    return () => clearInterval(id);
  }, [push]);

  useEffect(() => {
    const es = new EventSource(`${BASE_URL}/logs/stream`);
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (ev) => {
      try {
        const entry: LogEntry = JSON.parse(ev.data);
        if (pausedRef.current) { pendingRef.current.push(entry); }
        else { push([entry]); }
      } catch { /* skip */ }
    };
    return () => { es.close(); setConnected(false); };
  }, [push]);

  const resume = () => {
    if (pendingRef.current.length > 0) {
      push(pendingRef.current);
      pendingRef.current = [];
    }
    setPaused(false);
  };

  const handleDownload = () => {
    const text = lines
      .map(e => `[${e.ts}] [${e.level.toUpperCase().padEnd(7)}] ${fmtEntry(e)}`)
      .join("\n");
    const a = Object.assign(document.createElement("a"), {
      href: URL.createObjectURL(new Blob([text], { type: "text/plain" })),
      download: `pcflipper-${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.log`,
    });
    a.click();
  };

  const visible = lines.filter(e => {
    if (levelFilter !== "ALL" && e.level.toLowerCase() !== levelFilter) return false;
    if (search && !fmtEntry(e).toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="h-full flex flex-col bg-[#080c14] p-4 gap-3">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="flex items-center gap-2 text-base font-bold text-emerald-400 font-mono shrink-0">
          <Terminal className="w-4 h-4" /> System Logs
        </h1>
        <div className="flex items-center gap-1.5 text-[11px] font-mono">
          <Circle className={`w-2 h-2 fill-current ${connected ? "text-emerald-500 animate-pulse" : "text-red-500"}`} />
          <span className={connected ? "text-emerald-500" : "text-red-400"}>
            {connected ? "LIVE" : "OFFLINE"}
          </span>
        </div>
        <span className="text-[11px] font-mono text-slate-600">
          {total.toLocaleString()} events &middot; {visible.length} shown
        </span>
        {paused && pendingRef.current.length > 0 && (
          <span className="text-[11px] font-mono text-yellow-400 animate-pulse">
            +{pendingRef.current.length} buffered
          </span>
        )}

        {/* Level filter pills */}
        <div className="flex gap-1 ml-auto">
          {LEVELS.map(l => (
            <button key={l} onClick={() => setLevelFilter(l)}
              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase transition-colors ${
                levelFilter === l
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                  : "text-slate-600 hover:text-slate-400 border border-transparent"
              }`}>{l}</button>
          ))}
        </div>

        <input type="text" placeholder="filter..." value={search}
          onChange={e => setSearch(e.target.value)}
          className="bg-black/60 border border-[#1e2d45] rounded px-2.5 py-1 text-[11px] font-mono text-emerald-300 placeholder-slate-700 outline-none focus:border-emerald-500/40 w-36" />

        <button onClick={paused ? resume : () => setPaused(true)} title={paused ? "Resume" : "Pause"}
          className="p-1.5 rounded border border-[#1e2d45] text-slate-500 hover:text-slate-200 transition-colors">
          {paused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
        </button>
        <button onClick={() => { setLines([]); setTotal(0); }} title="Clear"
          className="p-1.5 rounded border border-[#1e2d45] text-slate-500 hover:text-red-400 transition-colors">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
        <button onClick={handleDownload} title="Download .log"
          className="p-1.5 rounded border border-[#1e2d45] text-slate-500 hover:text-emerald-400 transition-colors">
          <Download className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* ── Terminal window ─────────────────────────────────────────────────── */}
      <div className="flex-1 rounded-lg border border-[#1e2d45] overflow-hidden flex flex-col"
        style={{ background: "#000" }}>

        {/* macOS title bar */}
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-[#1e2d45] bg-[#0a0e17]">
          <div className="flex gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/70" />
          </div>
          <span className="text-[10px] font-mono text-slate-600 ml-1">
            pc-flipper-api &mdash; log stream
          </span>
        </div>

        {/* Log output with CRT scanline overlay */}
        <div className="flex-1 overflow-y-auto px-3 py-2 font-mono text-[11px] leading-[1.7]"
          style={{
            backgroundImage:
              "repeating-linear-gradient(0deg,rgba(0,220,130,0.015) 0px,rgba(0,220,130,0.015) 1px,transparent 1px,transparent 3.4px)",
          }}>
          {visible.length === 0 ? (
            <div className="text-slate-700 mt-4 ml-1">
              {connected
                ? "$ waiting for events…_"
                : "$ backend offline — start the API server_"}
            </div>
          ) : (
            visible.map((entry, i) => (
              <div key={i} className="flex gap-2 hover:bg-white/[0.025] rounded px-1 -mx-1">
                <span className="text-slate-700 shrink-0 select-none w-[92px]">
                  {formatTs(entry.ts)}
                </span>
                <span className={`shrink-0 w-14 uppercase font-bold ${levelColor(entry.level)}`}>
                  [{entry.level.toUpperCase().slice(0, 4)}]
                </span>
                <span className={`flex-1 break-all ${levelColor(entry.level)}`}>
                  {fmtEntry(entry)}
                </span>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>

        {/* Status bar */}
        <div className="flex items-center gap-3 px-3 py-1 border-t border-[#0d1520] bg-[#060a10] text-[9px] font-mono">
          <span className={connected ? "text-emerald-600" : "text-red-700"}>
            {connected ? "● connected" : "● disconnected"}
          </span>
          <span className="ml-auto">
            {paused
              ? <span className="text-yellow-600">● PAUSED</span>
              : <span className="text-emerald-700">● streaming</span>}
          </span>
          <span className="text-slate-800">|</span>
          <span className="text-slate-700">utf-8</span>
        </div>
      </div>
    </div>
  );
}
