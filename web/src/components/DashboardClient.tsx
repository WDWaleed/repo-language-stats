"use client";

import { useState } from "react";
import { CardPreview, type CardOptions } from "@/components/CardPreview";
import { EmbedSnippet } from "@/components/EmbedSnippet";
import { StatsTable } from "@/components/StatsTable";
import type { CachedUserStats, CardType } from "@/lib/svg/types";

interface DashboardClientProps {
  stats: CachedUserStats;
  initialCard: CardType;
}

export function DashboardClient({ stats, initialCard }: DashboardClientProps) {
  const [options, setOptions] = useState<CardOptions>({
    cardType: initialCard,
    theme: "auto",
    metric: "bytes",
    langsCount: initialCard === "compact" ? 4 : initialCard === "donut" ? 6 : 8,
    showFiles: false,
    hideTitle: false,
  });

  return (
    <div className="space-y-6">
      <CardPreview stats={stats} options={options} onChange={setOptions} />
      <EmbedSnippet username={stats.username} options={options} />
      <StatsTable
        languages={stats.languages}
        totalBytes={stats.total_bytes}
        totalLines={stats.total_lines}
      />
    </div>
  );
}
