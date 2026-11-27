"use client";

import { ArrowRight, BarChart3, Lock, PieChart, Search, Sparkles, Table2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

const CARD_HIGHLIGHTS = [
  {
    name: "Stacked Bar",
    type: "bar",
    description: "Compact horizontal progress bar with a 2-column Linguist legend.",
    icon: BarChart3,
  },
  {
    name: "Breakdown Table",
    type: "breakdown",
    description: "Detailed tabular view with byte counts, line counts, and file totals.",
    icon: Table2,
  },
  {
    name: "Donut Chart",
    type: "donut",
    description: "Clean radial breakdown with total bytes or lines centered inside.",
    icon: PieChart,
  },
  {
    name: "Compact Pill",
    type: "compact",
    description: "Ultra-slim 32px badge bar ideal for tight README headers.",
    icon: Sparkles,
  },
];

export default function HomePage() {
  const router = useRouter();
  const [username, setUsername] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const cleaned = username.trim().replace(/^@/, "");
    if (!cleaned) return;
    router.push(`/${encodeURIComponent(cleaned)}`);
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-14 sm:px-6 sm:py-20">
      {/* Hero */}
      <section className="mx-auto max-w-3xl text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3.5 py-1 text-xs font-medium text-indigo-600 dark:text-indigo-300">
          <Lock className="h-3.5 w-3.5" />
          <span>Includes private repositories without leaking repo names</span>
        </div>

        <h1 className="mt-6 text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl dark:text-white">
          Accurate GitHub Language Cards,{" "}
          <span className="bg-gradient-to-r from-indigo-500 to-cyan-400 bg-clip-text text-transparent">
            Powered by Real Bytes &amp; Lines
          </span>
        </h1>

        <p className="mt-4 text-base text-slate-600 sm:text-lg dark:text-slate-400">
          Embed live, theme-aware SVG language cards in your GitHub profile README.
          Backed by Linguist classification, Upstash Redis caching, and scheduled scans.
        </p>

        {/* Search form */}
        <form
          onSubmit={handleSubmit}
          className="mx-auto mt-8 flex max-w-md flex-col gap-2.5 sm:flex-row"
        >
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter GitHub username (e.g. WDWaleed)"
              aria-label="GitHub username"
              className="h-11 w-full rounded-xl border border-slate-300 bg-white pr-4 pl-10 text-sm text-slate-900 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:placeholder-slate-500"
            />
          </div>
          <button
            type="submit"
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
          >
            <span>View Dashboard</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        </form>

        {/* Demo shortcut */}
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <span>Try live profile:</span>
          <Link
            href="/WDWaleed"
            className="rounded-md border border-slate-200 bg-white px-2.5 py-1 font-medium text-slate-700 transition hover:border-indigo-400 hover:text-indigo-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-indigo-500 dark:hover:text-indigo-400"
          >
            @WDWaleed
          </Link>
        </div>
      </section>

      {/* Card Highlights */}
      <section className="mt-16">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
            4 Serverless SVG Card Layouts
          </h2>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Light, Dark, and Auto (<code className="font-mono">prefers-color-scheme</code>)
          </span>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {CARD_HIGHLIGHTS.map((card) => {
            const Icon = card.icon;
            return (
              <Link
                key={card.type}
                href={`/WDWaleed?card=${card.type}`}
                className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-400/60 hover:shadow-md dark:border-slate-800 dark:bg-slate-900/70 dark:hover:border-indigo-500/50"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-600 transition group-hover:bg-indigo-600 group-hover:text-white dark:text-indigo-400">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 font-semibold text-slate-900 dark:text-white">
                  {card.name}
                </h3>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                  {card.description}
                </p>
              </Link>
            );
          })}
        </div>
      </section>
    </main>
  );
}
