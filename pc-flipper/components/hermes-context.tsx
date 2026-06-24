"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";

export interface SearchResult {
  id: number;
  title: string;
  price: number;
  classification: string;
  score: number;
  source: string;
  url: string;
  gpu: string | null;
  cpu: string | null;
  ram_gb: number | null;
}

export interface QuickReply {
  label: string;
  action: "show_super_gems" | "show_gems" | "show_playbooks" | "show_builds" | "show_components" | "show_cases" | "flip_listing" | "keep_looking" | "free_text";
  payload?: string | number;
}

export interface ListingCard {
  id: number;
  title: string;
  price: number;
  estimated_profit: number;
  cpu?: string;
  gpu?: string;
  url?: string;
  image_url?: string;
}

export interface HermesMessage {
  role: "user" | "assistant";
  content: string;
  searchResults?: SearchResult[];
  listingCards?: ListingCard[];
  quickReplies?: QuickReply[];
  isStreaming?: boolean;
}

interface HermesContextValue {
  isOpen: boolean;
  setOpen: (open: boolean) => void;
  hasGreeted: boolean;
  setHasGreeted: (v: boolean) => void;
  messages: HermesMessage[];
  setMessages: (msgs: HermesMessage[] | ((prev: HermesMessage[]) => HermesMessage[])) => void;
  addUserMessage: (content: string) => void;
  addAssistantMessage: (msg: Omit<HermesMessage, "role">) => void;
  startAssistantMessage: () => void;
  appendToken: (token: string) => void;
  appendSearchResults: (results: SearchResult[]) => void;
  finaliseAssistantMessage: () => void;
}

const HermesContext = createContext<HermesContextValue | null>(null);

export function HermesProvider({ children }: { children: ReactNode }) {
  const [isOpen, setOpen] = useState(false);
  const [hasGreeted, setHasGreeted] = useState(false);
  const [messages, setMessages] = useState<HermesMessage[]>([]);

  const addUserMessage = useCallback((content: string) => {
    setMessages(prev => [...prev, { role: "user", content }]);
  }, []);

  const addAssistantMessage = useCallback((msg: Omit<HermesMessage, "role">) => {
    setMessages(prev => [...prev, { role: "assistant", ...msg }]);
  }, []);

  const startAssistantMessage = useCallback(() => {
    setMessages(prev => [...prev, { role: "assistant", content: "", isStreaming: true }]);
  }, []);

  const appendToken = useCallback((token: string) => {
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant" && last.isStreaming) {
        return [...prev.slice(0, -1), { ...last, content: last.content + token }];
      }
      return prev;
    });
  }, []);

  const appendSearchResults = useCallback((results: SearchResult[]) => {
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant" && last.isStreaming) {
        return [...prev.slice(0, -1), { ...last, searchResults: results }];
      }
      return prev;
    });
  }, []);

  const finaliseAssistantMessage = useCallback(() => {
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant") {
        return [...prev.slice(0, -1), { ...last, isStreaming: false }];
      }
      return prev;
    });
  }, []);

  return (
    <HermesContext.Provider value={{
      isOpen, setOpen, hasGreeted, setHasGreeted,
      messages, setMessages,
      addUserMessage, addAssistantMessage,
      startAssistantMessage, appendToken, appendSearchResults, finaliseAssistantMessage,
    }}>
      {children}
    </HermesContext.Provider>
  );
}

export function useHermes() {
  const ctx = useContext(HermesContext);
  if (!ctx) throw new Error("useHermes must be used inside HermesProvider");
  return ctx;
}
