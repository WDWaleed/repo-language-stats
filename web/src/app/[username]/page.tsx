import Link from "next/link";
import { ArrowLeft, Code, FileCode2, FolderGit2, HardDrive } from "lucide-react";
import { DashboardClient } from "@/components/DashboardClient";
import { RefreshButton } from "@/components/RefreshButton";
import { redis } from "@/lib/redis";
import type { CachedUserStats, CardType } from "@/lib/svg/types";
import { formatBytes, formatNumber } from "@/lib/svg/utils";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ username: string }>;
  searchParams: Promise<{ card?: string }>;
}

const VALID_CARDS = new Set<CardType>(["bar", "breakdown", "donut", "compact"]);

export default async function UserDashboardPage({ params, searchParams }: PageProps) {
  const { username } = await params;
  const { card } = await searchParams;
  const initialCard: CardType =
    card && VALID_CARDS.has(card as CardType) ? (card as CardType) : "bar";

  let stats: CachedUserStats | null = null;
  try {
    stats = await redis.get<CachedUserStats>(`stats:${username}`);
  } catch {
    stats = null;
  }

  if (!stats) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-16 text-center sm:px-6">
        <div className="rounded-2xl border border-slate-200 bg-white p-10 shadow-sm dark:border-slate-800 dark:bg-slate-900/70">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            No cached stats for @{username}
          </h1>
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">
            This user hasn&apos;t been synced to Upstash Redis yet. Run the CLI sync
            script or trigger the GitHub Actions worker to populate{" "}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs dark:bg-slate-800">
              stats:{username}
            </code>
            .
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Search
            </Link>
            <Link
              href="/WDWaleed"
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500"
            >
              View Demo (@WDWaleed)
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const lastScannedLabel = stats.last_scanned
    ? new Date(stats.last_scanned).toLocaleString("en-US", {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "Unknown";

  const summaryCards = [
    {
      label: "Repositories Scanned",
      value: String(stats.repos_scanned),
      sub: stats.repos_skipped > 0 ? `${stats.repos_skipped} skipped` : "All active",
      icon: FolderGit2,
    },
    {
      label: "Total Code Size",
      value: formatBytes(stats.total_bytes),
      sub: `${stats.total_bytes.toLocaleString("en-US")} bytes`,
      icon: HardDrive,
    },
    {
      label: "Total Lines",
      value: formatNumber(stats.total_lines, true),
      sub: `${stats.total_lines.toLocaleString("en-US")} lines`,
      icon: Code,
    },
    {
      label: "Languages Detected",
      value: String(stats.languages.length),
      sub: `Updated ${lastScannedLabel}`,
      icon: FileCode2,
    },
  ];

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 transition hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Search another user
          </Link>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl dark:text-white">
            @{stats.username}
          </h1>
        </div>
        <RefreshButton username={stats.username} />
      </div>

      {/* KPI cards */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {summaryCards.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.label}
              className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900/70"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                  {item.label}
                </span>
                <Icon className="h-4 w-4 text-indigo-500" />
              </div>
              <div className="mt-2 text-2xl font-bold text-slate-900 dark:text-white">
                {item.value}
              </div>
              <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {item.sub}
              </div>
            </div>
          );
        })}
      </section>

      <DashboardClient stats={stats} initialCard={initialCard} />
    </main>
  );
}
