import type { Metadata } from "next";
import Link from "next/link";
import { Code2 } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Repo Language Stats — Dynamic GitHub Language Cards",
    template: "%s | Repo Language Stats",
  },
  description:
    "Generate crisp, customizable SVG language cards and analytics across your public and private GitHub repositories.",
  openGraph: {
    title: "Repo Language Stats",
    description:
      "Dynamic SVG language cards and analytics across your public and private GitHub repositories.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-slate-50 font-sans text-slate-900 antialiased transition-colors dark:bg-slate-950 dark:text-slate-100">
        <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/80 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-950/80">
          <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
            <Link
              href="/"
              className="flex items-center gap-2 font-semibold tracking-tight text-slate-900 dark:text-white"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-sm">
                <Code2 className="h-4 w-4" />
              </span>
              <span>Repo Language Stats</span>
            </Link>
            <div className="flex items-center gap-3">
              <Link
                href="/WDWaleed"
                className="hidden text-sm font-medium text-slate-600 transition hover:text-slate-900 sm:inline-block dark:text-slate-400 dark:hover:text-white"
              >
                Demo: @WDWaleed
              </Link>
              <ThemeToggle />
            </div>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
