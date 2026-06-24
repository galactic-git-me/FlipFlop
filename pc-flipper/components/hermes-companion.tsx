"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { X, Send, Loader2, ExternalLink, Repeat2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useHermes, HermesMessage, ListingCard, QuickReply } from "@/components/hermes-context";
import { streamCompanion } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const GREETING: Omit<HermesMessage, "role"> = {
  content: "Hey! 👋 I'm Hermes — your FlipFlop co-pilot. What do you want to look at?",
  quickReplies: [
    { label: "⚡ Super Gems",           action: "show_super_gems" },
    { label: "💎 Gems",                 action: "show_gems" },
    { label: "📚 Playbooks",            action: "show_playbooks" },
    { label: "🔧 Suggested Builds",     action: "show_builds" },
    { label: "🧩 Best Sub-components",  action: "show_components" },
    { label: "🖥 Available Cases",      action: "show_cases" },
    { label: "✨ Best Build from Catalogue", action: "show_magic_build" },
  ],
};

// ── Listing card shown inline in chat ────────────────────────────────────────

function InlineListingCard({
  card,
  onFlip,
  flipping,
}: {
  card: ListingCard;
  onFlip: (id: number) => void;
  flipping: number | null;
}) {
  const profit = card.estimated_profit ?? 0;
  const profitColour = profit > 150 ? "text-emerald-400" : profit > 80 ? "text-amber-400" : "text-red-400";

  return (
    <div className="bg-[#0d1120] border border-[#2a2d3e] rounded-xl p-3 flex flex-col gap-2">
      {card.image_url && (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img src={card.image_url} alt="" className="w-full h-28 object-contain rounded-lg bg-[#080f1a]" />
      )}
      <p className="text-xs font-semibold text-slate-200 line-clamp-2 leading-snug">{card.title}</p>
      <div className="flex flex-wrap gap-1 text-[10px] text-slate-500">
        {card.cpu && <span>🖥 {card.cpu.slice(0, 22)}</span>}
        {card.gpu
          ? <span className="text-emerald-400">✓ {card.gpu.slice(0, 18)}</span>
          : <span className="text-red-400/70">✗ No GPU</span>}
      </div>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] text-slate-500">Buy price</p>
          <p className="text-sm font-bold text-slate-200">£{card.price.toFixed(0)}</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-slate-500">Est. profit</p>
          <p className={`text-sm font-black ${profitColour}`}>+£{profit.toFixed(0)}</p>
        </div>
      </div>
      <div className="flex gap-2">
        {card.url && (
          <a
            href={card.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 px-2 py-1.5 text-[11px] border border-slate-700 text-slate-400 rounded-lg hover:border-slate-500 transition-colors"
          >
            <ExternalLink className="w-3 h-3" /> View
          </a>
        )}
        <button
          onClick={() => onFlip(card.id)}
          disabled={flipping === card.id}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-[11px] font-bold bg-cyan-500 hover:bg-cyan-400 text-black rounded-lg transition-colors disabled:opacity-50"
        >
          {flipping === card.id
            ? <Loader2 className="w-3 h-3 animate-spin" />
            : <Repeat2 className="w-3 h-3" />}
          Flip It
        </button>
      </div>
    </div>
  );
}

// ── Single message bubble ─────────────────────────────────────────────────────

function MessageBubble({
  msg,
  onQuickReply,
  onFlip,
  flipping,
}: {
  msg: HermesMessage;
  onQuickReply: (qr: QuickReply) => void;
  onFlip: (id: number) => void;
  flipping: number | null;
}) {
  const isUser = msg.role === "user";

  return (
    <div className={cn("flex flex-col gap-2", isUser && "items-end")}>
      {/* Listing cards */}
      {msg.listingCards && msg.listingCards.length > 0 && (
        <div className="grid grid-cols-2 gap-2 w-full">
          {msg.listingCards.map(card => (
            <InlineListingCard key={card.id} card={card} onFlip={onFlip} flipping={flipping} />
          ))}
        </div>
      )}

      {/* Text bubble */}
      {(msg.content || msg.isStreaming) && (
        <div className={cn(
          "max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-[#7c85ff]/20 border border-[#7c85ff]/30 text-slate-200 rounded-tr-sm"
            : "bg-[#1a1d2e] text-slate-200 rounded-tl-sm"
        )}>
          {msg.content}
          {msg.isStreaming && !msg.content && (
            <span className="inline-flex gap-0.5 ml-1">
              <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </span>
          )}
        </div>
      )}

      {/* Quick reply chips */}
      {msg.quickReplies && msg.quickReplies.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-1">
          {msg.quickReplies.map((qr, i) => (
            <button
              key={i}
              onClick={() => onQuickReply(qr)}
              className="px-3 py-1.5 text-xs font-semibold rounded-full border border-[#7c85ff]/40 text-[#a0aaff] hover:bg-[#7c85ff]/15 hover:border-[#7c85ff]/70 transition-all"
            >
              {qr.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main companion component ──────────────────────────────────────────────────

export function HermesCompanion() {
  const {
    isOpen, setOpen,
    hasGreeted, setHasGreeted,
    messages,
    addUserMessage, addAssistantMessage,
    startAssistantMessage, appendToken, appendSearchResults, finaliseAssistantMessage,
  } = useHermes();

  const router = useRouter();
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [flipping, setFlipping] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Greet on first open
  useEffect(() => {
    if (isOpen && !hasGreeted) {
      setHasGreeted(true);
      setTimeout(() => addAssistantMessage(GREETING), 400);
    }
  }, [isOpen, hasGreeted, setHasGreeted, addAssistantMessage]);

  // ── Free-text send via LLM stream ──────────────────────────────────────────

  const send = useCallback(async (overrideText?: string) => {
    const text = (overrideText ?? input).trim();
    if (!text || isSending) return;
    setInput("");
    setIsSending(true);

    addUserMessage(text);
    startAssistantMessage();

    const history = messages
      .filter(m => !m.isStreaming)
      .map(m => ({ role: m.role as "user" | "assistant", content: m.content }));

    abortRef.current = new AbortController();
    try {
      await streamCompanion(text, history, "general", (event) => {
        if (event.type === "token" && event.content) appendToken(event.content);
        if (event.type === "search_results" && event.results) appendSearchResults(event.results);
        if (event.type === "done") finaliseAssistantMessage();
      }, abortRef.current.signal);
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        appendToken("Something went wrong. Try again.");
        finaliseAssistantMessage();
      }
    } finally {
      setIsSending(false);
    }
  }, [input, isSending, messages, addUserMessage, startAssistantMessage, appendToken, appendSearchResults, finaliseAssistantMessage]);

  // ── Flip a listing from chat ────────────────────────────────────────────────

  const handleFlip = useCallback(async (listingId: number) => {
    setFlipping(listingId);
    try {
      const res = await fetch(`${API_BASE}/api/flips/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ listing_id: listingId }),
      });
      if (!res.ok) {
        addAssistantMessage({ content: "Couldn't start that flip — it may already be in progress." });
        return;
      }
      const flip = await res.json() as { id: number };
      addAssistantMessage({
        content: `Flip started! Taking you to the builder now. Pick a playbook and choose your upgrade components to see the full P&L.`,
      });
      setOpen(false);
      router.push(`/flips/${flip.id}`);
    } finally {
      setFlipping(null);
    }
  }, [addAssistantMessage, router, setOpen]);

  // ── Quick reply handler ─────────────────────────────────────────────────────

  const handleQuickReply = useCallback(async (qr: QuickReply) => {
    if (qr.action === "flip_listing" && qr.payload) {
      await handleFlip(Number(qr.payload));
      return;
    }

    if (qr.action === "free_text" && qr.payload) {
      void send(String(qr.payload));
      return;
    }

    if (qr.action === "keep_looking") {
      addUserMessage("Keep looking");
      addAssistantMessage({ content: GREETING.content, quickReplies: GREETING.quickReplies });
      return;
    }

    // Navigation actions — fetch data, navigate, summarise
    const labelMap: Record<string, string> = {
      show_super_gems:    "Show me the Super Gems",
      show_gems:          "Show me the Gems",
      show_playbooks:     "Show me the Playbooks",
      show_builds:        "Show me Suggested Builds",
      show_components:    "Show me the best sub-components",
      show_cases:         "Show me available cases",
      show_magic_build:   "Build the best PC from the catalogue",
      build_for_playbook: `Build from: ${qr.payload ?? "playbook"}`,
    };
    addUserMessage(labelMap[qr.action] ?? qr.label);
    setIsSending(true);

    try {
      if (qr.action === "show_super_gems") {
        router.push("/super-gems");
        const res = await fetch(`${API_BASE}/api/listings/?claude_verdict=GEM&limit=6&sort_by=gem_score`);
        const data = await res.json() as Record<string, unknown>[];
        const items = Array.isArray(data) ? data : (data as { items?: Record<string, unknown>[] }).items ?? [];
        const cards: ListingCard[] = (items as Array<{
          id: number; title: string; price: number;
          claude_expected_profit?: number; estimated_profit?: number;
          cpu?: string; gpu?: string; url?: string; image_urls?: string[];
        }>).slice(0, 4).map(l => ({
          id: l.id,
          title: l.title,
          price: l.price,
          estimated_profit: l.claude_expected_profit ?? l.estimated_profit ?? 0,
          cpu: l.cpu,
          gpu: l.gpu,
          url: l.url,
          image_url: l.image_urls?.[0],
        }));

        if (cards.length === 0) {
          addAssistantMessage({
            content: "No Super Gems right now — the scanner hasn't found any that pass the AI check yet. Check back later or run a manual scan from Settings.",
            quickReplies: [
              { label: "💎 Show Gems instead", action: "show_gems" },
              { label: "📚 See Playbooks", action: "show_playbooks" },
            ],
          });
        } else {
          const best = cards[0];
          addAssistantMessage({
            content: `Found ${items.length} Super Gem${items.length !== 1 ? "s" : ""}! These are the ones with the highest AI-confirmed profit potential. The top pick is the ${best.cpu ?? "system"} at £${best.price.toFixed(0)} with an estimated +£${best.estimated_profit.toFixed(0)} profit.\n\nWant to flip one? Hit "Flip It" on any card below — I'll open the build planner. Or keep looking at Gems.`,
            listingCards: cards,
            quickReplies: [
              { label: "💎 Show Gems too", action: "show_gems" },
              { label: "🔄 Keep looking", action: "keep_looking" },
            ],
          });
        }
      }

      else if (qr.action === "show_gems") {
        router.push("/");
        const res = await fetch(`${API_BASE}/api/listings/?gem_only=true&limit=8&sort_by=gem_score`);
        const data = await res.json() as Record<string, unknown>[];
        const items = Array.isArray(data) ? data : (data as { items?: Record<string, unknown>[] }).items ?? [];
        const cards: ListingCard[] = (items as Array<{
          id: number; title: string; price: number;
          claude_expected_profit?: number; estimated_profit?: number;
          cpu?: string; gpu?: string; url?: string; image_urls?: string[];
        }>).slice(0, 4).map(l => ({
          id: l.id,
          title: l.title,
          price: l.price,
          estimated_profit: l.claude_expected_profit ?? l.estimated_profit ?? 0,
          cpu: l.cpu,
          gpu: l.gpu,
          url: l.url,
          image_url: l.image_urls?.[0],
        }));

        if (cards.length === 0) {
          addAssistantMessage({
            content: "No gems right now. The scanner is probably still working through new listings. Try again in a bit.",
            quickReplies: [{ label: "🔄 Back to start", action: "keep_looking" }],
          });
        } else {
          addAssistantMessage({
            content: `${items.length} gem${items.length !== 1 ? "s" : ""} in the pipeline right now. These are rule-based picks — good profit potential but not yet AI-verified. Best ones below. You can flip any of them or keep browsing.`,
            listingCards: cards,
            quickReplies: [
              { label: "⚡ Super Gems only", action: "show_super_gems" },
              { label: "🔄 Keep looking", action: "keep_looking" },
            ],
          });
        }
      }

      else if (qr.action === "show_playbooks") {
        router.push("/playbooks");
        const res = await fetch(`${API_BASE}/api/build-wizard/playbooks`);
        const playbooks = await res.json() as Array<{ id: number; name: string; emoji: string; profit_strategy?: { target_profit_gbp?: number } }>;

        if (!playbooks.length) {
          addAssistantMessage({ content: "No playbooks found. Check the Playbooks page to seed them.", quickReplies: [{ label: "🔄 Back", action: "keep_looking" }] });
        } else {
          const list = playbooks.slice(0, 6).map(p =>
            `${p.emoji} **${p.name}** — target +£${p.profit_strategy?.target_profit_gbp ?? "?"}`
          ).join("\n");
          addAssistantMessage({
            content: `Here are your active playbooks — each one defines which base PCs to buy, what to upgrade, and what to sell for:\n\n${list}\n\nEach playbook drives the upgrade suggestions when you start a flip. Want to see some gems that match one of these?`,
            quickReplies: [
              { label: "⚡ Find Super Gems", action: "show_super_gems" },
              { label: "💎 Find Gems", action: "show_gems" },
              { label: "🔄 Back", action: "keep_looking" },
            ],
          });
        }
      }

      else if (qr.action === "show_builds") {
        router.push("/opportunities");
        const res = await fetch(`${API_BASE}/api/listings/?gem_only=true&limit=4&sort_by=gem_score`);
        const data = await res.json() as Record<string, unknown>[];
        const items = Array.isArray(data) ? data : (data as { items?: Record<string, unknown>[] }).items ?? [];
        const cards: ListingCard[] = (items as Array<{
          id: number; title: string; price: number;
          claude_expected_profit?: number; estimated_profit?: number;
          cpu?: string; gpu?: string; url?: string; image_urls?: string[];
        }>).slice(0, 4).map(l => ({
          id: l.id,
          title: l.title,
          price: l.price,
          estimated_profit: l.claude_expected_profit ?? l.estimated_profit ?? 0,
          cpu: l.cpu,
          gpu: l.gpu,
          url: l.url,
          image_url: l.image_urls?.[0],
        }));

        addAssistantMessage({
          content: `Here are the top resell opportunities right now based on your playbooks. Buy the base PC, follow the playbook upgrades, and list it. The ones below are the highest-margin options available today.`,
          listingCards: cards,
          quickReplies: [
            { label: "⚡ Super Gems only", action: "show_super_gems" },
            { label: "📚 View Playbooks", action: "show_playbooks" },
            { label: "🔄 Keep looking", action: "keep_looking" },
          ],
        });
      }

      else if (qr.action === "show_components") {
        router.push("/parts");
        const categories = [
          { key: "gpu", label: "GPU", minPrice: 50 },
          { key: "ram", label: "RAM", minPrice: 15 },
          { key: "ssd", label: "SSD", minPrice: 15 },
          { key: "psu", label: "PSU", minPrice: 20 },
        ];
        const goodSources = ["eBay UK", "Gumtree", "Amazon"];
        const results = await Promise.all(
          categories.map(async (cat) => {
            const res = await fetch(`${API_BASE}/api/parts/?category=${cat.key}&limit=100`);
            const data = await res.json() as Array<{ id: number; name: string; price: number; source_site: string; source_url?: string }>;
            const items = Array.isArray(data) ? data : [];
            const good = items
              .filter(p => goodSources.includes(p.source_site) && (p.price ?? 0) >= cat.minPrice)
              .sort((a, b) => a.price - b.price);
            return { ...cat, count: good.length, cheapest: good[0] ?? null };
          })
        );

        const lines = results
          .filter(r => r.cheapest)
          .map(r => `• **${r.label}** — ${r.count} in catalogue, cheapest at £${r.cheapest!.price.toFixed(0)} (${r.cheapest!.name.slice(0, 40)}…)`)
          .join("\n");

        addAssistantMessage({
          content: `Here's a snapshot of the best-value upgrade components available right now from eBay UK, Gumtree, and Amazon:\n\n${lines}\n\nHead to the Parts page to browse by category, filter by price, and pick specific parts to attach to a flip.`,
          quickReplies: [
            { label: "⚡ Show Super Gems", action: "show_super_gems" },
            { label: "🖥 View Cases",      action: "show_cases" },
            { label: "🔄 Back",            action: "keep_looking" },
          ],
        });
      }

      else if (qr.action === "show_magic_build") {
        // Fetch all playbooks and present them as chips for the user to pick
        const res = await fetch(`${API_BASE}/api/build-wizard/playbooks`);
        const playbooks = await res.json() as Array<{
          id: number; name: string; emoji: string;
          profit_strategy?: { target_profit_gbp?: number; target_sell_price_gbp?: number };
          search_strategy?: { price_min?: number; price_max?: number };
        }>;

        if (!playbooks.length) {
          addAssistantMessage({
            content: "No playbooks found — head to the Playbooks page to set them up first.",
            quickReplies: [{ label: "📚 Go to Playbooks", action: "show_playbooks" }],
          });
        } else {
          addAssistantMessage({
            content: "Which playbook should I build from? I'll find the best base PC and cheapest upgrade components from the catalogue for it.",
            quickReplies: playbooks.slice(0, 8).map(p => ({
              label: `${p.emoji} ${p.name}`,
              action: "build_for_playbook" as const,
              payload: p.id,
            })),
          });
        }
      }

      else if (qr.action === "build_for_playbook" && qr.payload) {
        const playbookId = Number(qr.payload);

        // Fetch the selected playbook's details
        const pbRes = await fetch(`${API_BASE}/api/build-wizard/playbooks`);
        const allPlaybooks = await pbRes.json() as Array<{
          id: number; name: string; emoji: string;
          upgrade_strategy?: {
            required?: Array<{ component: string; max_cost: number; target?: string }>;
            optional?: Array<{ component: string; max_cost: number; target?: string }>;
          };
          profit_strategy?: { target_profit_gbp?: number; target_sell_price_gbp?: number };
          search_strategy?: { price_min?: number; price_max?: number };
        }>;
        const pb = allPlaybooks.find(p => p.id === playbookId);

        if (!pb) {
          addAssistantMessage({ content: "Couldn't find that playbook. Try picking another.", quickReplies: [{ label: "✨ Pick again", action: "show_magic_build" }] });
          return;
        }

        const requiredSlots = pb.upgrade_strategy?.required ?? [];
        const catMap: Record<string, string> = {
          GPU: "gpu", RAM: "ram", SSD: "ssd", CPU: "cpu", PSU: "psu", Motherboard: "motherboard",
        };
        const goodSources = ["eBay UK", "Gumtree", "Amazon"];

        // Fetch best part for each required slot + cheapest base listing in parallel
        const [partResults, baseRes] = await Promise.all([
          Promise.all(requiredSlots.map(async (slot) => {
            const cat = catMap[slot.component] ?? slot.component.toLowerCase();
            const r = await fetch(`${API_BASE}/api/parts/?category=${cat}&limit=200`);
            const parts = await r.json() as Array<{ id: number; name: string; price: number; source_site: string }>;
            const items = Array.isArray(parts) ? parts : [];
            const good = items
              .filter(p => goodSources.includes(p.source_site) && (p.price ?? 0) >= 5 && (p.price ?? 0) <= (slot.max_cost ?? 9999))
              .sort((a, b) => a.price - b.price);
            return { slot, best: good[0] ?? null, count: good.length };
          })),
          fetch(`${API_BASE}/api/listings/?gem_only=true&sort_by=price&limit=10`),
        ]);

        const baseData = await baseRes.json() as Record<string, unknown>[];
        const baseItems = (Array.isArray(baseData) ? baseData : (baseData as { items?: Record<string, unknown>[] }).items ?? []) as Array<{
          id: number; title: string; price: number; cpu?: string; gpu?: string;
          claude_expected_profit?: number; estimated_profit?: number; url?: string; image_urls?: string[];
        }>;

        // Find cheapest base PC within playbook price range
        const priceMin = pb.search_strategy?.price_min ?? 0;
        const priceMax = pb.search_strategy?.price_max ?? 9999;
        const basePC = baseItems.find(l => l.price >= priceMin && l.price <= priceMax) ?? baseItems[0] ?? null;

        // Compute totals
        const baseCost = basePC?.price ?? 0;
        const upgradeLines = partResults
          .filter(r => r.best)
          .map(r => `• **${r.slot.component}** — ${r.best!.name.slice(0, 40)} · £${r.best!.price.toFixed(0)} (${r.count} options available)`);
        const upgradeCost = partResults.reduce((sum, r) => sum + (r.best?.price ?? 0), 0);
        const totalIn = baseCost + upgradeCost;
        const targetSell = pb.profit_strategy?.target_sell_price_gbp ?? (totalIn + (pb.profit_strategy?.target_profit_gbp ?? 150));
        const estProfit = targetSell - totalIn;

        const intro = basePC
          ? `Here's the best **${pb.emoji} ${pb.name}** build I can assemble from the catalogue right now:`
          : `No matching base PC found in the current price range (£${priceMin}–£${priceMax}). Here's the upgrade component breakdown anyway:`;

        const baseSection = basePC
          ? `\n🖥 **Base PC** — ${basePC.title.slice(0, 55)} · £${baseCost.toFixed(0)}`
          : "";

        const upgradeSection = upgradeLines.length
          ? `\n\n🔧 **Upgrades:**\n${upgradeLines.join("\n")}`
          : "\n\n⚠️ No catalogue parts found within the playbook budget limits.";

        const plSection = `\n\n💰 **Total cost in:** £${totalIn.toFixed(0)}\n📈 **Target sell:** £${targetSell.toFixed(0)}\n✅ **Estimated profit:** +£${estProfit.toFixed(0)}`;

        addAssistantMessage({
          listingCards: basePC ? [{
            id: basePC.id,
            title: basePC.title,
            price: basePC.price,
            estimated_profit: estProfit,
            cpu: basePC.cpu,
            gpu: basePC.gpu,
            url: basePC.url,
            image_url: basePC.image_urls?.[0],
          }] : undefined,
          content: `${intro}${baseSection}${upgradeSection}${plSection}`,
          quickReplies: [
            ...(basePC ? [{ label: "⚡ Flip It", action: "flip_listing" as const, payload: basePC.id }] : []),
            { label: "✨ Try another playbook", action: "show_magic_build" as const },
            { label: "🔄 Back", action: "keep_looking" as const },
          ],
        });
      }

      else if (qr.action === "show_cases") {
        router.push("/cases");
        const res = await fetch(`${API_BASE}/api/parts/cases?limit=200`);
        const data = await res.json() as Array<{ id: number; name: string; price: number; source_site: string; theme?: string; image_url?: string; source_url?: string }>;
        const items = Array.isArray(data) ? data : [];
        const pcThemes = new Set(["Content Creator Case","Mid-level Gamer Case","Family PC Case","RGB / Gamer Bait","Airflow / Performance Style","AI Workstation Case","Student Build Case"]);
        const pcCases = items.filter(c => c.theme && pcThemes.has(c.theme) && (c.price ?? 0) > 10);

        // Group by theme
        const byTheme: Record<string, typeof pcCases> = {};
        for (const c of pcCases) {
          const t = c.theme!;
          if (!byTheme[t]) byTheme[t] = [];
          byTheme[t].push(c);
        }

        const summary = Object.entries(byTheme)
          .sort((a, b) => b[1].length - a[1].length)
          .slice(0, 6)
          .map(([theme, cases]) => {
            const cheapest = cases.sort((a,b) => a.price - b.price)[0];
            return `• **${theme}** — ${cases.length} available, from £${cheapest.price.toFixed(0)}`;
          })
          .join("\n");

        addAssistantMessage({
          content: `Found ${pcCases.length} PC cases across ${Object.keys(byTheme).length} styles:\n\n${summary}\n\nThe Cases page has full filtering by theme, source, and price. Each case can be attached to a build when you're setting up a flip.`,
          quickReplies: [
            { label: "🧩 Best Sub-components", action: "show_components" },
            { label: "⚡ Show Super Gems",     action: "show_super_gems" },
            { label: "🔄 Back",                action: "keep_looking" },
          ],
        });
      }
    } catch {
      addAssistantMessage({
        content: "Couldn't fetch the data right now — the backend might be warming up. Try again in a moment.",
        quickReplies: [{ ...qr, label: "🔄 Try again" }],
      });
    } finally {
      setIsSending(false);
    }
  }, [addUserMessage, addAssistantMessage, handleFlip, router, send]);

  return (
    <>
      {/* ── Chat panel ─────────────────────────────────────────────────────── */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 z-50 flex flex-col bg-[#12151f] border border-[#2a2d3e] rounded-2xl shadow-2xl shadow-black/70 overflow-hidden"
          style={{ width: "min(860px, calc(100vw - 3rem))", height: "calc(100vh - 5rem)" }}>

          {/* Header */}
          <div className="flex items-center gap-3 px-4 py-3 bg-[#1a1d2e] border-b border-[#2a2d3e] flex-shrink-0">
            <div className="relative w-12 h-12 rounded-full overflow-hidden border-2 border-[#7c85ff]/50 flex-shrink-0">
              <Image src="/pics/hermes.gif" alt="Hermes" fill sizes="48px" className="object-cover" unoptimized />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-bold text-slate-100">Hermes</p>
              <p className="text-[11px] text-emerald-400">● online · your FlipFlop co-pilot</p>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="ml-auto text-slate-500 hover:text-slate-300 transition-colors p-1"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 flex flex-col gap-4 p-4 overflow-y-auto">
            {messages.map((msg, i) => (
              <MessageBubble
                key={i}
                msg={msg}
                onQuickReply={handleQuickReply}
                onFlip={handleFlip}
                flipping={flipping}
              />
            ))}
            {isSending && messages[messages.length - 1]?.role !== "assistant" && (
              <div className="flex gap-1.5 px-4 py-3 bg-[#1a1d2e] rounded-2xl rounded-tl-sm w-fit">
                <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="flex items-center gap-2.5 p-3 border-t border-[#2a2d3e] flex-shrink-0">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); } }}
              placeholder="Ask anything…"
              disabled={isSending}
              className="flex-1 bg-[#1a1d2e] border border-[#2a2d3e] rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-[#7c85ff]/50 disabled:opacity-50"
            />
            <button
              onClick={() => void send()}
              disabled={isSending || !input.trim()}
              className="flex-shrink-0 w-11 h-11 bg-[#7c85ff] hover:bg-[#9099ff] disabled:opacity-40 disabled:cursor-not-allowed rounded-xl flex items-center justify-center transition-colors"
            >
              {isSending
                ? <Loader2 className="w-4 h-4 text-white animate-spin" />
                : <Send className="w-4 h-4 text-white" />}
            </button>
          </div>
        </div>
      )}

      {/* ── Floating avatar button ──────────────────────────────────────────── */}
      <button
        onClick={() => setOpen(!isOpen)}
        className={cn(
          "fixed bottom-6 right-6 z-50 w-24 h-24 rounded-full overflow-hidden",
          "border-4 shadow-xl shadow-[#7c85ff]/30 transition-all duration-200",
          "hover:scale-110 hover:shadow-[#7c85ff]/50",
          isOpen ? "opacity-0 pointer-events-none" : "border-[#7c85ff]/60 scale-100",
        )}
        title="Chat with Hermes"
      >
        <Image src="/pics/hermes.gif" alt="Hermes" fill sizes="96px" className="object-cover" unoptimized />
      </button>
    </>
  );
}
