"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Gem,
  Zap,
  Package,
  Box,
  Brain,
  Tag,
  MessageSquare,
  Database,
  Search,
  Settings,
  TrendingUp,
  Terminal,
  CalendarClock,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", icon: LayoutDashboard, label: "Dashboard", color: "" },
  { href: "/opportunities", icon: Gem, label: "Opportunities", color: "" },
  { href: "/flips", icon: Zap, label: "Active Flips", color: "" },
  { href: "/parts", icon: Package, label: "Parts Pricing", color: "" },
  { href: "/cases", icon: Box, label: "Cases Catalogue", color: "text-purple-400" },
  { href: "/selling", icon: Tag, label: "Selling Toolkit", color: "" },
  { href: "/intel", icon: Brain, label: "Intelligence", color: "text-cyan-400" },
  { href: "/chat", icon: MessageSquare, label: "Hermes AI", color: "" },
];

const CONFIG_ITEMS = [
  { href: "/sources", icon: Database, label: "Data Sources" },
  { href: "/search-config", icon: Search, label: "Search Config" },
  { href: "/schedule", icon: CalendarClock, label: "Scheduler", color: "text-[#00dc82]" },
  { href: "/logs", icon: Terminal, label: "Logs", color: "text-emerald-500" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 flex-shrink-0 flex flex-col glass-sidebar">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-[#1e2d45]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#00dc82]/15 flex items-center justify-center border border-[#00dc82]/25">
            <TrendingUp className="w-4 h-4 text-[#00dc82]" />
          </div>
          <div>
            <div className="text-sm font-bold text-slate-100 leading-tight">PC Flipper</div>
            <div className="text-[10px] text-[#00dc82] font-medium tracking-wider uppercase">Pro</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150",
                active
                  ? "bg-[#00dc82]/10 text-[#00dc82] border border-[#00dc82]/20"
                  : "text-slate-500 hover:text-slate-200 hover:bg-white/5"
              )}
            >
              <item.icon
                className={cn(
                  "w-4 h-4 flex-shrink-0",
                  active ? "text-[#00dc82]" : item.color || "text-slate-500"
                )}
              />
              <span className="font-medium">{item.label}</span>
              {item.href === "/chat" && (
                <span className="ml-auto">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#00dc82] animate-pulse block" />
                </span>
              )}
            </Link>
          );
        })}

        <div className="pt-4 pb-1 px-3">
          <div className="text-[10px] uppercase tracking-widest text-slate-600 font-semibold">Config</div>
        </div>

        {CONFIG_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150",
                active
                  ? "bg-[#00dc82]/10 text-[#00dc82] border border-[#00dc82]/20"
                  : "text-slate-500 hover:text-slate-200 hover:bg-white/5"
              )}
            >
              <item.icon className={cn("w-4 h-4 flex-shrink-0", active ? "text-[#00dc82]" : (item as { color?: string }).color || "")} />
              <span className="font-medium">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-[#1e2d45]">
        <div className="flex items-center gap-2 text-xs text-slate-600">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>Swarms active</span>
          <span className="ml-auto text-slate-700">v5.0</span>
        </div>
      </div>
    </aside>
  );
}
