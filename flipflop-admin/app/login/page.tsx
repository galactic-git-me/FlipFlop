"use client";

import { useEffect, useState } from "react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const reason = new URLSearchParams(window.location.search).get("reason");
    if (reason === "session_invalid") setError("Your sign-in could not be verified. Please sign in again. If this keeps happening, contact support with this message.");
    if (reason === "session_missing") setError("Your sign-in session was not received by the admin site. Check that cookies are enabled, then sign in again.");
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await fetch("/api/session/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
        credentials: "same-origin",
        cache: "no-store",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.error ?? data.detail ?? "Invalid email or password");
        return;
      }

      // Force a fresh document request so proxy.ts verifies the cookie just issued
      // by the route handler before rendering any protected page.
      window.location.replace("/");
    } catch {
      setError("Could not reach the server. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-lg border border-white/10 bg-black/40 p-8 backdrop-blur"
      >
        <h1 className="mb-1 text-2xl font-semibold tracking-wide text-white">
          FlipFlop Admin
        </h1>
        <p className="mb-6 text-sm text-white/50">Sign in to continue</p>

        <label className="mb-1 block text-xs uppercase tracking-wide text-white/60">
          Email
        </label>
        <input
          type="email"
          required
          autoFocus
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 w-full rounded border border-white/15 bg-white/5 px-3 py-2 text-white outline-none focus:border-white/40"
        />

        <label className="mb-1 block text-xs uppercase tracking-wide text-white/60">
          Password
        </label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-4 w-full rounded border border-white/15 bg-white/5 px-3 py-2 text-white outline-none focus:border-white/40"
        />

        {error && (
          <p className="mb-4 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-white py-2 font-medium text-black transition hover:bg-white/90 disabled:opacity-50"
        >
          {loading ? "Signing in..." : "Sign in"}
        </button>
        <p aria-live="polite" className="mt-3 min-h-5 text-center text-xs text-white/45">
          {loading ? "Checking your account…" : error ? "Sign-in was not completed." : ""}
        </p>
      </form>
    </div>
  );
}
