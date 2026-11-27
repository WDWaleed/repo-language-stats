import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Repo Language Stats",
  description:
    "Dynamic SVG language cards and analytics across your public and private GitHub repositories.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}
