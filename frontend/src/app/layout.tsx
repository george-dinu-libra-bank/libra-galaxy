import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { Geist, Geist_Mono } from "next/font/google";
import { FundalSpatial } from "@/components/shell/fundal-spatial";
import { TEMA_COOKIE, temaDinCookie } from "@/lib/tema";
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
  title: "Galaxy Bank · Mobile banking",
  description: "Cont curent cu IBAN romanesc, deschis online in cateva minute.",
};

export const viewport: Viewport = {
  themeColor: "#2f6fed",
  viewportFit: "cover",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Tema vine din cookie, deci clasa "dark" e deja in HTML-ul trimis de server:
  // fara flash de light theme si fara mismatch la hidratare.
  const tema = temaDinCookie((await cookies()).get(TEMA_COOKIE)?.value);

  return (
    <html lang="ro" className={tema === "dark" ? "dark" : undefined}>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <FundalSpatial />
        {children}
      </body>
    </html>
  );
}
