"use client";

import { useMemo } from "react";
import { renderSvg } from "@/lib/svg/renderer";
import type { CachedUserStats, CardTheme, CardType, MetricType } from "@/lib/svg/types";

export interface CardOptions {
  cardType: CardType;
  theme: CardTheme;
  metric: MetricType;
  langsCount: number;
  showFiles: boolean;
  hideTitle: boolean;
}

interface CardPreviewProps {
  stats: CachedUserStats;
  options: CardOptions;
  onChange: (next: CardOptions) => void;
}

const CARD_TABS: Array<{ id: CardType; label: string }> = [
  { id: "bar", label: "Bar" },
  { id: "breakdown", label: "Breakdown" },
  { id: "donut", label: "Donut" },
  { id: "compact", label: "Compact" },
];

const THEME_OPTIONS: Array<{ id: CardTheme; label: string }> = [
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
  { id: "auto", label: "Auto" },
];

export function CardPreview({ stats, options, onChange }: CardPreviewProps) {
  const svgMarkup = useMemo(
    () =>
      renderSvg(stats, {
        cardType: options.cardType,
        theme: options.theme,
        metric: options.metric,
        langsCount: options.langsCount,
        showFiles: options.showFiles,
        hideTitle: options.hideTitle,
      }),
    [stats, options]
  );

  const availableMetrics: MetricType[] =
    options.cardType === "breakdown" ? ["bytes", "lines", "both"] : ["bytes", "lines"];

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6 dark:border-slate-800 dark:bg-slate-900/70">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4 dark:border-slate-800">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
            Card Preview
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Customize layout, theme, and metrics in real time.
          </p>
        </div>

        {/* Card type tabs */}
        <div
          role="tablist"
          aria-label="Card layout"
          className="inline-flex rounded-xl border border-slate-200 bg-slate-100 p-1 dark:border-slate-800 dark:bg-slate-950"
        >
          {CARD_TABS.map((tab) => {
            const active = options.cardType === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => {
                  const nextMetric =
                    tab.id !== "breakdown" && options.metric === "both"
                      ? "bytes"
                      : options.metric;
                  onChange({ ...options, cardType: tab.id, metric: nextMetric });
                }}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  active
                    ? "bg-white text-indigo-600 shadow-sm dark:bg-slate-800 dark:text-indigo-400"
                    : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Controls */}
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Theme picker */}
        <div>
          <span className="block text-xs font-medium text-slate-600 dark:text-slate-400">
            Theme
          </span>
          <div className="mt-1.5 inline-flex w-full rounded-lg border border-slate-200 bg-slate-100 p-0.5 dark:border-slate-800 dark:bg-slate-950">
            {THEME_OPTIONS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => onChange({ ...options, theme: t.id })}
                className={`flex-1 rounded-md py-1.5 text-xs font-medium transition ${
                  options.theme === t.id
                    ? "bg-white text-slate-900 shadow-sm dark:bg-slate-800 dark:text-white"
                    : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Metric toggle */}
        <div>
          <span className="block text-xs font-medium text-slate-600 dark:text-slate-400">
            Metric
          </span>
          <div className="mt-1.5 inline-flex w-full rounded-lg border border-slate-200 bg-slate-100 p-0.5 dark:border-slate-800 dark:bg-slate-950">
            {availableMetrics.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => onChange({ ...options, metric: m })}
                className={`flex-1 rounded-md py-1.5 text-xs font-medium capitalize transition ${
                  options.metric === m
                    ? "bg-white text-slate-900 shadow-sm dark:bg-slate-800 dark:text-white"
                    : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        {/* Languages count slider */}
        <div>
          <div className="flex items-center justify-between text-xs font-medium text-slate-600 dark:text-slate-400">
            <label htmlFor="langs-count-slider">Languages</label>
            <span className="font-mono text-slate-900 dark:text-white">
              {options.langsCount}
            </span>
          </div>
          <input
            id="langs-count-slider"
            type="range"
            min={2}
            max={Math.max(2, Math.min(16, stats.languages.length || 12))}
            value={options.langsCount}
            onChange={(e) =>
              onChange({ ...options, langsCount: Number(e.target.value) })
            }
            className="mt-2.5 w-full accent-indigo-600"
          />
        </div>

        {/* Extra toggles */}
        <div className="flex flex-col justify-center gap-2">
          {options.cardType !== "compact" && (
            <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={options.hideTitle}
                onChange={(e) =>
                  onChange({ ...options, hideTitle: e.target.checked })
                }
                className="h-4 w-4 rounded border-slate-300 accent-indigo-600"
              />
              Hide card title
            </label>
          )}
          {options.cardType === "breakdown" && (
            <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={options.showFiles}
                onChange={(e) =>
                  onChange({ ...options, showFiles: e.target.checked })
                }
                className="h-4 w-4 rounded border-slate-300 accent-indigo-600"
              />
              Show file counts
            </label>
          )}
        </div>
      </div>

      {/* Live SVG canvas */}
      <div className="mt-6 flex min-h-[220px] items-center justify-center overflow-x-auto rounded-xl border border-dashed border-slate-300 bg-slate-100/70 p-6 dark:border-slate-700 dark:bg-slate-950/70">
        <div
          className="shrink-0"
          dangerouslySetInnerHTML={{ __html: svgMarkup }}
        />
      </div>
    </section>
  );
}
