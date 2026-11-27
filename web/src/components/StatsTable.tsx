"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { useMemo, useState } from "react";
import type { LanguageEntry } from "@/lib/svg/types";
import { formatBytes, resolveLanguageColor } from "@/lib/svg/utils";

interface StatsTableProps {
  languages: LanguageEntry[];
  totalBytes: number;
  totalLines: number;
}

type SortKey = "language" | "bytes" | "lines" | "files";
type SortDir = "asc" | "desc";

export function StatsTable({ languages, totalBytes, totalLines }: StatsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("bytes");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir(key === "language" ? "asc" : "desc");
    }
  }

  const sorted = useMemo(() => {
    return [...languages].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "language") {
        cmp = a.language.localeCompare(b.language);
      } else if (sortKey === "bytes") {
        cmp = a.bytes - b.bytes;
      } else if (sortKey === "lines") {
        cmp = a.lines - b.lines;
      } else {
        cmp = (a.files ?? 0) - (b.files ?? 0);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [languages, sortKey, sortDir]);

  function SortIcon({ col }: { col: SortKey }) {
    if (sortKey !== col) return <ArrowUpDown className="h-3.5 w-3.5 opacity-40" />;
    return sortDir === "asc" ? (
      <ArrowUp className="h-3.5 w-3.5 text-indigo-500" />
    ) : (
      <ArrowDown className="h-3.5 w-3.5 text-indigo-500" />
    );
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6 dark:border-slate-800 dark:bg-slate-900/70">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
            Language Breakdown
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Click column headers to sort across all {languages.length} detected languages.
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:border-slate-800 dark:text-slate-400">
              <th className="py-3 pr-4">
                <button
                  type="button"
                  onClick={() => handleSort("language")}
                  className="inline-flex items-center gap-1.5 hover:text-slate-900 dark:hover:text-white"
                >
                  Language <SortIcon col="language" />
                </button>
              </th>
              <th className="px-4 py-3 text-right">
                <button
                  type="button"
                  onClick={() => handleSort("bytes")}
                  className="inline-flex items-center justify-end gap-1.5 hover:text-slate-900 dark:hover:text-white"
                >
                  Bytes <SortIcon col="bytes" />
                </button>
              </th>
              <th className="hidden px-4 py-3 sm:table-cell">Share</th>
              <th className="px-4 py-3 text-right">
                <button
                  type="button"
                  onClick={() => handleSort("lines")}
                  className="inline-flex items-center justify-end gap-1.5 hover:text-slate-900 dark:hover:text-white"
                >
                  Lines <SortIcon col="lines" />
                </button>
              </th>
              <th className="py-3 pl-4 text-right">
                <button
                  type="button"
                  onClick={() => handleSort("files")}
                  className="inline-flex items-center justify-end gap-1.5 hover:text-slate-900 dark:hover:text-white"
                >
                  Files <SortIcon col="files" />
                </button>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/70">
            {sorted.map((lang) => {
              const color = lang.color || resolveLanguageColor(lang.language);
              const bytePct =
                lang.byte_percent ??
                (totalBytes > 0 ? Math.round((lang.bytes / totalBytes) * 1000) / 10 : 0);
              const linePct =
                lang.line_percent ??
                (totalLines > 0 ? Math.round((lang.lines / totalLines) * 1000) / 10 : 0);

              return (
                <tr
                  key={lang.language}
                  className="transition hover:bg-slate-50/80 dark:hover:bg-slate-800/40"
                >
                  <td className="py-3 pr-4 font-medium text-slate-900 dark:text-white">
                    <span className="inline-flex items-center gap-2.5">
                      <span
                        className="h-3 w-3 shrink-0 rounded-full"
                        style={{ backgroundColor: color }}
                      />
                      {lang.language}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-slate-700 dark:text-slate-300">
                    {formatBytes(lang.bytes)}{" "}
                    <span className="text-slate-400">({bytePct}%)</span>
                  </td>
                  <td className="hidden w-40 px-4 py-3 sm:table-cell">
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.max(2, Math.min(100, bytePct))}%`,
                          backgroundColor: color,
                        }}
                      />
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-slate-700 dark:text-slate-300">
                    {lang.lines.toLocaleString("en-US")}{" "}
                    <span className="text-slate-400">({linePct}%)</span>
                  </td>
                  <td className="py-3 pl-4 text-right font-mono text-xs text-slate-700 dark:text-slate-300">
                    {(lang.files ?? 0).toLocaleString("en-US")}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
