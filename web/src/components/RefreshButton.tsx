"use client";

import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

interface RefreshButtonProps {
  username: string;
}

export function RefreshButton({ username }: RefreshButtonProps) {
  const [loading, setLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [toast, setToast] = useState<{ type: "ok" | "err"; text: string } | null>(
    null
  );

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((prev) => (prev > 1 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(timer);
  }, [toast]);

  async function handleRefresh() {
    if (loading || cooldown > 0) return;
    setLoading(true);
    setToast(null);

    try {
      const res = await fetch(
        `/api/stats/${encodeURIComponent(username)}/refresh`,
        { method: "POST" }
      );
      const data = await res.json().catch(() => ({}));

      if (res.status === 202) {
        setCooldown(Number(data.retryAfter ?? 600));
        setToast({
          type: "ok",
          text: data.message ?? "Scan triggered! Stats will update in ~1–2 minutes.",
        });
      } else if (res.status === 429) {
        const wait = Number(data.retryAfter ?? 600);
        setCooldown(wait);
        setToast({
          type: "err",
          text: data.error ?? `Cooldown active. Retry in ${wait}s.`,
        });
      } else {
        setToast({
          type: "err",
          text: data.error ?? `Refresh failed (${res.status}).`,
        });
      }
    } catch {
      setToast({ type: "err", text: "Network error while triggering refresh." });
    } finally {
      setLoading(false);
    }
  }

  const mins = Math.floor(cooldown / 60);
  const secs = String(cooldown % 60).padStart(2, "0");

  return (
    <div className="relative flex flex-col items-end gap-2">
      <button
        type="button"
        onClick={handleRefresh}
        disabled={loading || cooldown > 0}
        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-indigo-400 hover:text-indigo-600 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-indigo-500 dark:hover:text-indigo-400"
      >
        <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        {loading ? (
          <span>Dispatching...</span>
        ) : cooldown > 0 ? (
          <span className="font-mono">Cooldown {mins}:{secs}</span>
        ) : (
          <span>Refresh Stats</span>
        )}
      </button>

      {toast && (
        <div
          role="status"
          className={`rounded-lg border px-3 py-1.5 text-xs font-medium shadow-sm ${
            toast.type === "ok"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
              : "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300"
          }`}
        >
          {toast.text}
        </div>
      )}
    </div>
  );
}
