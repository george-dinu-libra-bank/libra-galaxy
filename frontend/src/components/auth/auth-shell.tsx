import Link from "next/link";
import { ChevronLeft, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Logo } from "@/components/ui/logo";

type Props = {
  /** Titlul mic din bara hero. */
  eyebrow: string;
  titlu: string;
  subtitlu: string;
  icoana: LucideIcon;
  /** Ruta pentru sageata de inapoi; lipsa => fara sageata. */
  inapoi?: string;
  children: ReactNode;
};

/**
 * Cadrul comun al ecranelor de autentificare: hero albastru + foaia alba
 * rotunjita care urca peste el, cu badge-ul circular la imbinare.
 * Vezi DESIGN.md, sectiunea 5.
 */
export function AuthShell({
  eyebrow,
  titlu,
  subtitlu,
  icoana: Icoana,
  inapoi,
  children,
}: Props) {
  return (
    <div className="min-h-dvh lg:flex lg:items-center lg:justify-center lg:gap-20 lg:p-10">
      {/* Panou de brand — doar pe ecrane mari */}
      <aside className="hidden max-w-sm lg:block">
        <div className="mb-6 flex items-center gap-3">
          <Logo size={64} />
          <span className="text-2xl font-bold tracking-[-0.02em] text-ink">Galaxy Bank</span>
        </div>

        <h2 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
          Banca ta, in buzunar.
        </h2>
        <p className="mt-3 text-[15px] leading-[22px] text-ink-soft">
          Deschide un cont curent in cateva minute, cu IBAN romanesc, si trimite
          bani instant catre orice cont din tara.
        </p>
      </aside>

      {/* Ecranul propriu-zis */}
      <div className="relative flex min-h-dvh w-full flex-col overflow-hidden bg-surface lg:min-h-[640px] lg:w-[440px] lg:shrink-0 lg:rounded-card lg:shadow-lg">
        <header className="hero-gradient relative min-h-[220px] overflow-hidden px-6 pt-6 pb-16">
          {/* cercuri decorative */}
          <span
            aria-hidden
            className="pointer-events-none absolute -top-24 -right-16 h-56 w-56 rounded-full bg-white/10 blur-2xl"
          />
          <span
            aria-hidden
            className="pointer-events-none absolute -bottom-20 -left-12 h-48 w-48 rounded-full bg-white/8 blur-2xl"
          />

          <div className="relative flex justify-center">
            <span className="flex h-16 w-16 items-center justify-center rounded-full bg-white shadow-md">
              <Logo size={42} />
            </span>
          </div>

          <div className="relative mt-5 flex items-center gap-3">
            {inapoi ? (
              <Link
                href={inapoi}
                aria-label="Inapoi"
                className="flex h-10 w-10 items-center justify-center rounded-full bg-white/15 text-white transition-colors hover:bg-white/25 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-white/40"
              >
                <ChevronLeft size={20} strokeWidth={1.75} aria-hidden />
              </Link>
            ) : null}
            <span className="text-[15px] font-semibold text-white">{eyebrow}</span>
          </div>

          <div className="relative mt-7">
            <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-white">
              {titlu}
            </h1>
            <p className="mt-1.5 text-[15px] leading-[22px] text-primary-100">
              {subtitlu}
            </p>
          </div>
        </header>

        <main className="relative -mt-8 flex flex-1 animate-sheet-in flex-col rounded-t-sheet bg-surface px-6 pb-10 shadow-lg sm:px-8">
          {/* Badge circular cu punctele de accent */}
          <div className="relative -mt-9 mb-6 self-center">
            <span className="flex h-[72px] w-[72px] items-center justify-center rounded-full bg-surface shadow-md">
              <Icoana size={30} strokeWidth={1.75} className="text-primary-600" aria-hidden />
            </span>
            <span
              aria-hidden
              className="absolute -top-0.5 right-0 h-2 w-2 rounded-full bg-danger"
            />
            <span
              aria-hidden
              className="absolute top-3 -left-1 h-2 w-2 rounded-full bg-success"
            />
            <span
              aria-hidden
              className="absolute -bottom-0.5 left-2 h-2 w-2 rounded-full bg-warning"
            />
          </div>

          {children}
        </main>
      </div>
    </div>
  );
}
