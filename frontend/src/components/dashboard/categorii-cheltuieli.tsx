"use client";

import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useRef } from "react";
import { useValutaDashboard } from "@/components/dashboard/context-valuta";
import type { CheltuieliPeCategorie } from "@/lib/data/analiza";
import { CATEGORIE_INFO, etichetaCategorie, totalizeazaPeCategorie } from "@/lib/categorii";
import { cn, formateazaSuma } from "@/lib/utils";
import type { Curs } from "@/lib/valute";

const LATIME_GLISARE = 240;

/** "2026-08" -> "August" */
function numeLuna(luna: string) {
  if (!luna) return "";
  const data = new Date(`${luna}-01T00:00:00`);
  const text = data.toLocaleDateString("ro-RO", { month: "long" });
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * Cheltuielile lunii curente, pe categorie (stil George/BCR) — carusel
 * orizontal, glisabil cu săgeți sau direct cu degetul (`overflow-x-auto`).
 * Categoria vine determinist din backend (tools/categorii_tranzactii.py),
 * niciodată calculată aici.
 *
 * Backend-ul intoarce o suma pe (categorie, valuta), nu un total gata
 * convertit — se recalculeaza aici cu valuta aleasa de pe dashboard
 * (ValutaDashboardContext, aceeasi cu butonul de pe TotalConturi), la fel cum
 * totalul din conturi foloseste cursurile fara cerere noua la server.
 */
export function CategoriiCheltuieli({ date, cursuri }: { date: CheltuieliPeCategorie; cursuri: Curs[] }) {
  const glisor = useRef<HTMLDivElement>(null);
  const { valuta } = useValutaDashboard();
  const categorii = totalizeazaPeCategorie(date.categorii, cursuri, valuta);

  function glisează(directie: 1 | -1) {
    glisor.current?.scrollBy({ left: directie * LATIME_GLISARE, behavior: "smooth" });
  }

  return (
    <section className="mt-8">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ink">
          Cheltuieli {numeLuna(date.luna)}
        </h2>

        {categorii.length > 0 ? (
          <Link
            href="/categorii"
            className="rounded-field px-2 py-1 text-[13px] font-semibold text-primary-600 transition-colors hover:bg-primary-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            Vezi toate
          </Link>
        ) : null}
      </div>

      {categorii.length === 0 ? (
        <p className="mt-4 rounded-card bg-surface p-6 text-center text-[15px] text-ink-faint shadow-sm">
          Nu ai nicio cheltuială luna asta.
        </p>
      ) : (
        <div className="mt-4 flex items-center gap-1">
          <button
            type="button"
            aria-label="Glisează spre categoriile anterioare"
            onClick={() => glisează(-1)}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface text-ink-soft shadow-sm transition-colors hover:bg-primary-50 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            <ChevronLeft size={18} strokeWidth={1.75} aria-hidden />
          </button>

          <div
            ref={glisor}
            className="flex flex-1 snap-x snap-mandatory gap-3 overflow-x-auto scroll-smooth pb-1"
          >
            {categorii.map((c) => {
              const info = CATEGORIE_INFO[c.categorie];
              const Icona = info?.icona ?? CATEGORIE_INFO.altele.icona;
              return (
                <Link
                  key={c.categorie}
                  href={`/categorii/${c.categorie}`}
                  className={cn(
                    "flex shrink-0 snap-start flex-col gap-2 rounded-card bg-surface p-4 shadow-sm",
                    "w-[152px] transition-[transform,box-shadow] duration-150 ease-soft",
                    "hover:shadow-md active:scale-[0.98] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                  )}
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-50 text-primary-600">
                    <Icona size={18} strokeWidth={1.75} aria-hidden />
                  </span>
                  <span className="truncate text-[13px] font-medium text-ink">
                    {etichetaCategorie(c.categorie)}
                  </span>
                  <span className="tabular truncate text-[15px] font-semibold text-ink">
                    {formateazaSuma(c.total, valuta)}
                  </span>
                </Link>
              );
            })}
          </div>

          <button
            type="button"
            aria-label="Glisează spre categoriile următoare"
            onClick={() => glisează(1)}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface text-ink-soft shadow-sm transition-colors hover:bg-primary-50 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            <ChevronRight size={18} strokeWidth={1.75} aria-hidden />
          </button>
        </div>
      )}
    </section>
  );
}
