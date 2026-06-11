"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";

export interface HermesMessage {
  role: "user" | "assistant";
  content: string;
  searchResults?: SearchResult[];
  isStreaming?: boolean;
}

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

interface HermesContextValue {
  isOpen: boolean;
  setOpen: (open: boolean) => void;
  messages: HermesMessage[];
  addUserMessage: (content: string) => void;
  appendToken: (token: string) => void;
  appendSearchResults: (results: SearchResult[]) => void;
  finaliseAssistantMessage: () => void;
  startAssistantMessage: () => void;
}

const HermesContext = createContext<HermesContextValue | null>(null);

export function HermesProvider({ children }: { children: ReactNode }) {
  const [isOpen, setOpen] = useState(false);
  const [messages, setMessages] = useState<HermesMessage[]>([
    {
      role: "assistant",
      content: "Hey! I'm Hermes. I can search your catalogue, evaluate listings, or just chat. What do you need?",
    },
  ]);

  const addUserMessage = useCallback((content: string) => {
    setMessages(prev => [...prev, { role: "user", content }]);
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
      isOpen, setOpen, messages,
      addUserMessage, startAssistantMessage,
      appendToken, appendSearchResults, finaliseAssistantMessage,
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
