"use client";

import { usePathname } from "next/navigation";
import { Bell, Radio, Search, UserCircle2 } from "lucide-react";

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

  return (
    <header className="node-topbar">
      <div className="node-search-wrap">
        <Search className="h-4 w-4 text-[var(--nf-outline)]" />
        <input className="node-search-input" placeholder={placeholder} />
      </div>

      <div className="node-topbar-right">
        <div className="node-live-chip">
          <span className="node-live-dot" />
          <span>COMMAND_DECK</span>
        </div>
        <div className="node-top-icons">
          <Radio className="h-4 w-4" />
          <Bell className="h-4 w-4" />
          <UserCircle2 className="h-5 w-5" />
        </div>
      </div>
    </header>
  );
}
