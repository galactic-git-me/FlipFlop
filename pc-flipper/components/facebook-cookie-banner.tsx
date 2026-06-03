"use client";

import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import { Upload } from "lucide-react";

interface FbStatus {
  exists: boolean;
  valid: boolean;
  expired: boolean;
  expiry_warning: boolean;
  message: string;
  days_remaining?: number;
}

export function FacebookCookieBanner() {
  const [status, setStatus] = useState<FbStatus | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [cookieJson, setCookieJson] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{ ok: boolean; message: string } | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileLoad = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setCookieJson((ev.target?.result as string) ?? "");
    };
    reader.readAsText(file);
    // Reset so the same file can be re-selected if needed
    e.target.value = "";
  };

  useEffect(() => {
    api.facebook.status().then(setStatus).catch(() => null);
  }, []);

  // If cookies are fine, render nothing
  if (!status || (!status.expiry_warning && !status.expired)) {
    return null;
  }

  const isExpired = status.expired;

  const handleUpdate = async () => {
    if (!cookieJson.trim()) return;
    setSubmitting(true);
    setSubmitResult(null);
    try {
      const result = await api.facebook.updateCookies(cookieJson);
      setSubmitResult({ ok: true, message: result.message });
      // Refresh status
      const newStatus = await api.facebook.status();
      setStatus(newStatus);
      setTimeout(() => setModalOpen(false), 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update cookies";
      setSubmitResult({ ok: false, message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      {/* Banner */}
      <div
        className={`flex items-center gap-3 px-4 py-2 text-sm font-medium cursor-pointer transition-opacity hover:opacity-90 ${
          isExpired
            ? "bg-red-900/80 border-b border-red-700/50 text-red-200"
            : "bg-orange-900/80 border-b border-orange-700/50 text-orange-200"
        }`}
        onClick={() => !isExpired && setModalOpen(true)}
      >
        <span className="flex-shrink-0">{isExpired ? "❌" : "⚠️"}</span>
        <span className="flex-1">
          {isExpired
            ? "Facebook cookies expired — Marketplace scraping disabled"
            : status.days_remaining != null
              ? `Facebook cookies expiring in ${Math.round(status.days_remaining)} days — click to renew`
              : "Facebook cookies expiring soon — click to renew"}
        </span>
        {!isExpired && (
          <span className="text-xs opacity-70 flex-shrink-0">Click to renew →</span>
        )}
      </div>

      {/* Modal */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) setModalOpen(false); }}
        >
          <div className="bg-[#0d1320] border border-[#1e2d45] rounded-2xl p-6 w-full max-w-lg mx-4 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-slate-100">Renew Facebook Cookies</h2>
              <button
                onClick={() => setModalOpen(false)}
                className="text-slate-500 hover:text-slate-300 text-xl leading-none"
              >
                ×
              </button>
            </div>

            <div className="space-y-3 text-sm text-slate-400 mb-4">
              <p className="text-orange-300 text-xs font-semibold uppercase tracking-wider">Instructions</p>
              <ol className="space-y-1.5 list-decimal list-inside">
                <li>Open <span className="text-slate-200 font-medium">facebook.com</span> in Chrome and log in.</li>
                <li>Install the <span className="text-slate-200 font-medium">&quot;Cookie Editor&quot;</span> Chrome extension.</li>
                <li>Click the Cookie Editor icon → <span className="text-slate-200 font-medium">Export</span> → Copy to clipboard.</li>
                <li>Paste the JSON below and click <span className="text-slate-200 font-medium">Update Cookies</span>.</li>
              </ol>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept=".json,application/json"
              onChange={handleFileLoad}
              className="hidden"
            />

            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-slate-500">Paste JSON or load from file</span>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-slate-300 border border-[#1e2d45] hover:border-[#00dc82]/40 hover:text-[#00dc82] transition-colors"
              >
                <Upload className="w-3 h-3" />
                Load from file
              </button>
            </div>

            <textarea
              ref={textareaRef}
              value={cookieJson}
              onChange={(e) => setCookieJson(e.target.value)}
              placeholder='[{"name": "c_user", "value": "...", ...}]'
              rows={7}
              className="w-full bg-[#080c14] border border-[#1e2d45] rounded-xl px-3 py-2.5 text-xs font-mono text-slate-300 placeholder-slate-600 focus:outline-none focus:border-[#00dc82]/40 resize-none mb-3"
            />

            {submitResult && (
              <p className={`text-sm mb-3 ${submitResult.ok ? "text-[#00dc82]" : "text-red-400"}`}>
                {submitResult.ok ? "✓ " : "✗ "}{submitResult.message}
              </p>
            )}

            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setModalOpen(false)}
                className="px-4 py-2 rounded-lg text-sm text-slate-400 border border-[#1e2d45] hover:border-slate-600 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdate}
                disabled={submitting || !cookieJson.trim()}
                className="px-4 py-2 rounded-lg text-sm font-semibold bg-[#00dc82] text-[#080c14] hover:bg-[#00dc82]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {submitting ? "Updating…" : "Update Cookies"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
