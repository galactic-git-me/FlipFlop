"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Cpu, TrendingUp, Lightbulb, Wifi, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  model?: string;
  timestamp: Date;
}

const SUGGESTIONS = [
  "What are today's best gems and why?",
  "Evaluate listing: i5-8400 16GB DDR4 no GPU no HDD £45 Birmingham",
  "What upgrades maximise profit on an i7-7700 base unit?",
  "Which selling platform gives the best net profit right now?",
  "Is a Star Trek themed case worth the premium on resale?",
];

function formatContent(content: string) {
  const lines = content.split("\n");
  return lines.map((line, i) => {
    if (line.startsWith("**") && line.endsWith("**")) {
      return <p key={i} className="font-semibold text-slate-200 mt-2">{line.replace(/\*\*/g, "")}</p>;
    }
    if (line.startsWith("- ") || line.startsWith("* ")) {
      return <li key={i} className="text-slate-300 ml-4 list-disc">{formatInline(line.slice(2))}</li>;
    }
    if (/^\d+\.\s/.test(line)) {
      return <li key={i} className="text-slate-300 ml-4 list-decimal">{formatInline(line.replace(/^\d+\.\s/, ""))}</li>;
    }
    if (line.startsWith("# ")) {
      return <p key={i} className="font-bold text-slate-100 text-base mt-3">{line.slice(2)}</p>;
    }
    if (line.startsWith("## ")) {
      return <p key={i} className="font-semibold text-slate-200 mt-2">{line.slice(3)}</p>;
    }
    if (line === "") return <div key={i} className="h-1" />;
    return <p key={i} className="text-slate-300">{formatInline(line)}</p>;
  });
}

function formatInline(text: string) {
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**")) return <strong key={i} className="text-slate-200 font-semibold">{part.replace(/\*\*/g, "")}</strong>;
    if (part.startsWith("`")) return <code key={i} className="bg-[#1e2d45] text-[#00dc82] px-1 rounded text-xs font-mono">{part.replace(/`/g, "")}</code>;
    return part;
  });
}

function ModelBadge({ model }: { model?: string }) {
  if (!model || model === "none") return null;
  const isOllama = model.includes("gemma") || model.includes("llama") || model.includes("mistral") || model === "local";
  const isClaude = model.includes("claude");
  const color = isOllama ? "text-cyan-400 border-cyan-400/30 bg-cyan-400/8" : isClaude ? "text-purple-400 border-purple-400/30 bg-purple-400/8" : "text-slate-400 border-slate-700/50 bg-slate-800/50";
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${color}`}>{model}</span>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "0",
      role: "assistant",
      content: "Hermes online. I've already scanned today's listings — there's a few things worth your attention.\n\nWhat do you need? Listing evaluation, upgrade recommendations, profit analysis, or just here to watch the numbers?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [modelUsed, setModelUsed] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    setInput("");

    const userMsg: Message = { id: Date.now().toString(), role: "user", content: msg, timestamp: new Date() };
    const history = messages
      .filter(m => m.id !== "0")
      .map(m => ({ role: m.role, content: m.content }));

    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const { response, model_used } = await api.chat.send(msg, history);
      setModelUsed(model_used);
      setOffline(model_used === "none");
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: response,
        model: model_used,
        timestamp: new Date(),
      }]);
    } catch {
      setOffline(true);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "API unreachable. Is the backend running on port 8000?",
        timestamp: new Date(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col" style={{ height: "calc(100vh - 0px)" }}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#1e2d45] flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#00dc82]/15 border border-[#00dc82]/25 flex items-center justify-center">
            <Bot className="w-5 h-5 text-[#00dc82]" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-100">Hermes</h1>
            <div className="flex items-center gap-2 text-xs">
              {offline ? (
                <span className="flex items-center gap-1 text-red-400">
                  <WifiOff className="w-3 h-3" /> Offline — check backend
                </span>
              ) : (
                <span className="flex items-center gap-1 text-[#00dc82]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#00dc82] animate-pulse" />
                  Online
                  {modelUsed && <ModelBadge model={modelUsed} />}
                  {!modelUsed && <ModelBadge model="gemma3:4b" />}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-[#0d1320] border border-[#1e2d45] rounded-lg text-xs text-slate-400">
            <Cpu className="w-3 h-3" /> Swarms coordinated
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-[#0d1320] border border-[#1e2d45] rounded-lg text-xs text-slate-400">
            <TrendingUp className="w-3 h-3" /> Live market data
          </div>
        </div>
      </div>

      {/* Quick prompts */}
      <div className="px-6 py-3 border-b border-[#1e2d45] flex gap-2 overflow-x-auto flex-shrink-0 scrollbar-hide">
        {SUGGESTIONS.map((s, i) => (
          <button
            key={i}
            onClick={() => send(s)}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0d1320] border border-[#1e2d45] hover:border-[#00dc82]/40 rounded-lg text-xs text-slate-400 hover:text-slate-300 whitespace-nowrap transition-colors flex-shrink-0 disabled:opacity-40"
          >
            <Lightbulb className="w-3 h-3 text-yellow-400/60" />
            {s.length > 52 ? s.slice(0, 50) + "…" : s}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.map(msg => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-lg bg-[#00dc82]/15 border border-[#00dc82]/25 flex items-center justify-center flex-shrink-0 mt-1">
                <Bot className="w-3.5 h-3.5 text-[#00dc82]" />
              </div>
            )}
            <div className="max-w-2xl space-y-1">
              <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-[#1e2d45] text-slate-200"
                  : "bg-[#0d1320] border border-[#1e2d45] text-slate-300"
              }`}>
                {msg.role === "assistant"
                  ? <div className="space-y-0.5">{formatContent(msg.content)}</div>
                  : msg.content}
              </div>
              {msg.role === "assistant" && msg.model && msg.id !== "0" && (
                <div className="flex items-center gap-1.5 pl-1">
                  <ModelBadge model={msg.model} />
                  <span className="text-[10px] text-slate-700">
                    {msg.timestamp.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
              )}
            </div>
            {msg.role === "user" && (
              <div className="w-7 h-7 rounded-lg bg-[#1e2d45] flex items-center justify-center flex-shrink-0 mt-1">
                <User className="w-3.5 h-3.5 text-slate-400" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-lg bg-[#00dc82]/15 border border-[#00dc82]/25 flex items-center justify-center flex-shrink-0">
              <Bot className="w-3.5 h-3.5 text-[#00dc82]" />
            </div>
            <div className="bg-[#0d1320] border border-[#1e2d45] rounded-2xl px-4 py-3">
              <div className="flex gap-1.5 items-center">
                {[0, 1, 2].map(i => (
                  <div key={i} className="w-1.5 h-1.5 rounded-full bg-[#00dc82] animate-bounce" style={{ animationDelay: `${i * 150}ms` }} />
                ))}
                <span className="text-xs text-slate-600 ml-2">Hermes thinking…</span>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-[#1e2d45] flex-shrink-0">
        <div className="flex gap-3">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
            placeholder="Ask Hermes — evaluate a listing, plan an upgrade, analyse a flip…"
            className="flex-1 px-4 py-3 bg-[#0d1320] border border-[#1e2d45] rounded-xl text-sm text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50 transition-colors"
          />
          <Button variant="primary" onClick={() => send()} disabled={loading || !input.trim()}>
            <Send className="w-4 h-4" />
          </Button>
        </div>
        <p className="text-xs text-slate-700 mt-2 text-center">
          Powered by Gemma3:4b via Ollama · OpenRouter free models as fallback · Sarcasm is a feature, not a bug
        </p>
      </div>
    </div>
  );
}
