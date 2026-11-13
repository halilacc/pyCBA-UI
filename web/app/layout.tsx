import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PyCBA — Sürekli Kiriş Analizi",
  description: "Sürekli kirişlerde mesnet tepkileri, kesit tesirleri ve sehim.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
