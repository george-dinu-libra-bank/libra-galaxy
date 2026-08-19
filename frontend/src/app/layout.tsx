import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { FundalSpatial } from "@/components/shell/fundal-spatial";
import { SCRIPT_INITIALIZARE_TEMA } from "@/lib/tema";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Libra · Mobile banking",
  description: "Cont curent cu IBAN romanesc, deschis online in cateva minute.",
};

export const viewport: Viewport = {
  themeColor: "#2f6fed",
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // suppressHydrationWarning: scriptul din <head> adauga clasa "dark" pe
    // <html> inainte de hidratare (vezi lib/tema.ts) — server-ul nu o poate
    // sti dinainte, deci un mismatch pe acest atribut e asteptat, nu un bug.
    <html lang="ro" suppressHydrationWarning>
      <head>
        {/* Aplica tema salvata inainte de primul paint, ca sa evitam flash-ul de light theme. */}
        <script dangerouslySetInnerHTML={{ __html: SCRIPT_INITIALIZARE_TEMA }} />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <FundalSpatial />
        {children}
      </body>
    </html>
  );
}
