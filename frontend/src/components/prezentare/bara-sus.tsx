"use client";

import { useState } from "react";
import Link from "next/link";
import { Moon, Sun } from "lucide-react";
import { Logo } from "@/components/ui/logo";
import { aplicaTema, type Tema } from "@/lib/tema";

const ANCORE = [
  { href: "#functii", text: "Funcții" },
  { href: "#pasi", text: "Cum începi" },
  { href: "#asistent", text: "Asistent" },
  { href: "#securitate", text: "Securitate" },
];

/**
 * Bara de sus a landing-ului. Tema se comuta din acelasi `aplicaTema` folosit in
 * /setari, deci alegerea se salveaza in cookie si tine si dupa autentificare.
 */
export function BaraSus({ tema }: { tema: Tema }) {
  const [intunecata, setIntunecata] = useState(tema === "dark");

  function comutaTema() {
    const noua: Tema = intunecata ? "light" : "dark";
    aplicaTema(noua);
    setIntunecata(noua === "dark");
  }

  const IconitaTema = intunecata ? Sun : Moon;

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center gap-4 px-5 sm:px-8">
        <Link
          href="/prezentare"
          className="flex items-center gap-2 rounded-field focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
        >
          <Logo size={32} />
          <span className="text-[15px] font-semibold tracking-[-0.01em] text-ink">Galaxy Bank</span>
        </Link>

        <nav className="ml-4 hidden items-center gap-1 lg:flex" aria-label="Secțiunile paginii">
          {ANCORE.map((ancora) => (
            <a
              key={ancora.href}
              href={ancora.href}
              className="flex h-11 items-center rounded-field px-3 text-[14px] text-ink-soft transition-colors hover:bg-primary-50 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
            >
              {ancora.text}
            </a>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={comutaTema}
            aria-label={intunecata ? "Treci pe tema deschisă" : "Treci pe tema întunecată"}
            className="flex h-11 w-11 items-center justify-center rounded-field text-ink-soft transition-colors hover:bg-primary-50 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            <IconitaTema size={18} strokeWidth={1.75} aria-hidden />
          </button>

          <Link
            href="/login"
            className="hidden h-11 items-center rounded-field px-4 text-[14px] font-semibold text-ink-soft transition-colors hover:bg-primary-50 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25 sm:flex"
          >
            Am cont
          </Link>

          <Link
            href="/register"
            className="flex h-11 items-center rounded-field bg-primary-600 px-4 text-[14px] font-semibold text-white shadow-btn transition-colors hover:bg-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            Deschide cont
          </Link>
        </div>
      </div>
    </header>
  );
}
