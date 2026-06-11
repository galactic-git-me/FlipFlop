"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { X, Send, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useHermes, SearchResult } from "@/components/hermes-context";
import { streamCompanion } from "@/lib/api";

function classificationColour(cls: string) {
  switch (cls) {
    case "gem": return "text-emerald-400 bg-emerald-400/10 border-emerald-400/30";
    case "watch": return "text-yellow-400 bg-yellow-400/10 border-yellow-400/30";
    case "overpriced": return "text-red-400 bg-red-400/10 border-red-400/30";
    default: return "text-slate-400 bg-slate-400/10 border-slate-400/30";
  }
}

function SearchResultCard({ result }: { result: SearchResult }) {
  return (
    <a
      href={result.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-[#0d0f1a] border border-[#2a2d3e] rounded-lg p-2.5 hover:border-[#7c85ff]/50 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs text-slate-200 leading-snug line-clamp-2">{result.title}</span>
        <span className="text-sm font-bold text-emerald-400 whitespace-nowrap">£{result.price.toFixed(0)}</span>
      </div>
      <div className="mt-1.5 flex items-center gap-1.5 flex-wrap">
        <span className={cn("text-[10px] px-1.5 py-0.5 rounded border font-medium uppercase", classificationColour(result.classification))}>
          {result.classification}
        </span>
        <span className="text-[10px] text-slate-500">{result.source}</span>
        {result.score > 0 && (
          <span className="text-[10px] text-amber-400">score {result.score.toFixed(0)}</span>
        )}
      </div>
    </a>
  );
}

function MessageBubble({ msg }: { msg: ReturnType<typeof useHermes>["messages"][number] }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex flex-col gap-1.5", isUser && "items-end")}>
      {msg.searchResults && msg.searchResults.length > 0 && (
        <div className="flex flex-col gap-1.5 w-full">
          {msg.searchResults.map(r => <SearchResultCard key={r.id} result={r} />)}
        </div>
      )}
      {(msg.content || msg.isStreaming) && (
        <div className={cn(
          "max-w-[90%] rounded-2xl px-3 py-2 text-xs leading-relaxed",
          isUser
            ? "bg-[#7c85ff]/20 border border-[#7c85ff]/30 text-slate-200 rounded-tr-sm"
            : "bg-[#1a1d2e] text-slate-200 rounded-tl-sm"
        )}>
          {msg.content}
          {msg.isStreaming && !msg.content && (
            <span className="inline-flex gap-0.5 ml-1">
              <span className="w-1 h-1 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-1 h-1 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-1 h-1 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export function HermesCompanion() {
  const { isOpen, setOpen, messages, addUserMessage, startAssistantMessage, appendToken, appendSearchResults, finaliseAssistantMessage } = useHermes();
  const pathname = usePathname();
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const pageContext = pathname?.split("/")[1] || "general";

  const send = useCallback(async () => {
    const text = input.trim();
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
      await streamCompanion(text, history, pageContext, (event) => {
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
  }, [input, isSending, messages, pageContext, addUserMessage, startAssistantMessage, appendToken, appendSearchResults, finaliseAssistantMessage]);

  return (
    <>
      {/* Chat panel */}
      {isOpen && (
        <div className="fixed bottom-24 right-5 z-50 w-[340px] flex flex-col bg-[#12151f] border border-[#2a2d3e] rounded-2xl shadow-2xl shadow-black/60 overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-2.5 px-3.5 py-2.5 bg-[#1a1d2e] border-b border-[#2a2d3e]">
            <div className="relative w-8 h-8 rounded-full overflow-hidden border border-[#7c85ff]/40 flex-shrink-0">
              <Image src="/pics/hermes.gif" alt="Hermes" fill sizes="32px" className="object-cover" unoptimized />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-slate-100">Hermes</p>
              <p className="text-[10px] text-emerald-400">● online · gemma4:e4b</p>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="ml-auto text-slate-500 hover:text-slate-300 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex flex-col gap-3 p-3 overflow-y-auto max-h-[400px] min-h-[200px]">
            {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="flex items-center gap-2 p-2.5 border-t border-[#2a2d3e]">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); } }}
              placeholder="Ask anything..."
              disabled={isSending}
              className="flex-1 bg-[#1a1d2e] border border-[#2a2d3e] rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-[#7c85ff]/50 disabled:opacity-50"
            />
            <button
              onClick={() => void send()}
              disabled={isSending || !input.trim()}
              className="flex-shrink-0 w-8 h-8 bg-[#7c85ff] hover:bg-[#9099ff] disabled:opacity-40 disabled:cursor-not-allowed rounded-lg flex items-center justify-center transition-colors"
            >
              {isSending
                ? <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
                : <Send className="w-3.5 h-3.5 text-white" />}
            </button>
          </div>
        </div>
      )}

      {/* Floating GIF button */}
      <button
        onClick={() => setOpen(!isOpen)}
        className={cn(
          "fixed bottom-5 right-5 z-50 w-14 h-14 rounded-full overflow-hidden",
          "border-2 shadow-lg shadow-[#7c85ff]/20 transition-all duration-200",
          "hover:scale-110 hover:shadow-[#7c85ff]/40",
          isOpen ? "border-[#7c85ff] scale-105" : "border-[#7c85ff]/50"
        )}
        title="Chat with Hermes"
      >
        <Image src="/pics/hermes.gif" alt="Hermes" fill sizes="56px" className="object-cover" unoptimized />
      </button>
    </>
  );
}
