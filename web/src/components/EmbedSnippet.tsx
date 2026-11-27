"use client";

import { Check, Copy } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { CardOptions } from "@/components/CardPreview";

interface EmbedSnippetProps {
  username: string;
  options: CardOptions;
}

type SnippetTab = "markdown" | "html" | "picture";

export function EmbedSnippet({ username, options }: EmbedSnippetProps) {
  const [tab, setTab] = useState<SnippetTab>("markdown");
  const [copied, setCopied] = useState(false);
  const [origin, setOrigin] = useState("https://your-deployment.vercel.app");

  useEffect(() => {
    if (typeof window !== "undefined" && window.location.origin) {
      setOrigin(window.location.origin);
    }
  }, []);

  const buildUrl = (themeOverride?: string) => {
    const params = new URLSearchParams();
    params.set("theme", themeOverride ?? options.theme);
    if (options.metric !== "bytes") params.set("metric", options.metric);
    params.set("langs_count", String(options.langsCount));
    if (options.cardType === "breakdown" && options.showFiles) {
      params.set("show_files", "true");
    }
    if (options.cardType !== "compact" && options.hideTitle) {
      params.set("hide_title", "true");
    }
    return `${origin}/api/svg/${encodeURIComponent(username)}/${options.cardType}?${params.toString()}`;
  };

  const snippet = useMemo(() => {
    const url = buildUrl();
    const alt = `${username}'s Language Stats`;

    if (tab === "markdown") {
      return `![${alt}](${url})`;
    }
    if (tab === "html") {
      return `<img src="${url}" alt="${alt}" />`;
    }
    const darkUrl = buildUrl("dark");
    const lightUrl = buildUrl("light");
    return [
      "<picture>",
      `  <source media="(prefers-color-scheme: dark)" srcset="${darkUrl}" />`,
      `  <source media="(prefers-color-scheme: light)" srcset="${lightUrl}" />`,
      `  <img alt="${alt}" src="${lightUrl}" />`,
      "</picture>",
    ].join("\n");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, origin, username, options]);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for non-HTTPS contexts
      const textarea = document.createElement("textarea");
      textarea.value = snippet;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6 dark:border-slate-800 dark:bg-slate-900/70">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
            Embed in GitHub README
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Copy a live snippet reflecting your current card customization.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-xl border border-slate-200 bg-slate-100 p-1 dark:border-slate-800 dark:bg-slate-950">
            {(
              [
                { id: "markdown", label: "Markdown" },
                { id: "html", label: "HTML" },
                { id: "picture", label: "<picture>" },
              ] as const
            ).map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                className={`rounded-lg px-3 py-1 text-xs font-semibold transition ${
                  tab === item.id
                    ? "bg-white text-indigo-600 shadow-sm dark:bg-slate-800 dark:text-indigo-400"
                    : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-indigo-500"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5" />
                <span>Copied!</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                <span>{tab === "markdown" ? "Copy Markdown" : "Copy Snippet"}</span>
              </>
            )}
          </button>
        </div>
      </div>

      <pre className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-slate-950 p-4 font-mono text-xs leading-relaxed text-slate-100 dark:border-slate-800">
        <code>{snippet}</code>
      </pre>
    </section>
  );
}
