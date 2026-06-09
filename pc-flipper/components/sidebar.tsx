"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  Cpu,
  Boxes,
  BookOpen,
  Store,
  ReceiptText,
  BarChart3,
  Brain,
  Settings,
  Plus,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";

const PRIMARY_NAV = [
  { href: "/", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/sources", icon: Search, label: "Sourcing" },
  { href: "/chat", icon: Cpu, label: "Build Wizard" },
  { href: "/flips", icon: Boxes, label: "Inventory" },
  { href: "/playbooks", icon: BookOpen, label: "Playbooks" },
  { href: "/parts", icon: Store, label: "Marketplace" },
  { href: "/selling", icon: ReceiptText, label: "Sold Builds" },
  { href: "/intel", icon: BarChart3, label: "Analytics" },
  { href: "/logs", icon: Brain, label: "AI Insights" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="node-sidebar">
      <div className="node-brand-wrap">
        <Image src="/pics/logo.png" alt="FlipFlop" width={240} height={120} className="h-[120px] w-auto object-contain" />
        <p className="node-version">Operational v1.0.4</p>
      </div>

      <button className="node-new-build-btn" type="button">
        <Plus className="h-4 w-4" />
        <span>NEW BUILD</span>
      </button>

      <nav className="node-nav">
        {PRIMARY_NAV.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn("node-nav-item", active && "node-nav-item-active")}
            >
              <item.icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="node-profile-wrap">
        <div className="node-profile-icon">
          <User className="h-4 w-4" />
        </div>
        <div>
          <p className="node-profile-name">Specialist Profile</p>
          <p className="node-profile-tier">Tier 3 Merchant</p>
        </div>
      </div>
    </aside>
  );
}
