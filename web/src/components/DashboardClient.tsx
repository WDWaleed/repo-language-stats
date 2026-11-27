"use client";

import { useState } from "react";
import { CardPreview, type CardOptions } from "@/components/CardPreview";
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
    </div>
  );
}
