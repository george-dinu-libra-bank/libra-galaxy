"use client";

import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useValutaDashboard } from "@/components/dashboard/context-valuta";
import type { CheltuieliPeCategorie } from "@/lib/data/analiza";
import { CATEGORIE_INFO, etichetaCategorie, totalizeazaPeCategorie } from "@/lib/categorii";
import { cn, formateazaSuma } from "@/lib/utils";
import type { Curs } from "@/lib/valute";

// Trebuie sa corespunda cu w-[152px] si gap-3 (12px) de mai jos — folosite si
// pentru calculul latimii vizibile, nu doar pentru stil.
const LATIME_CARD = 152;
const SPATIU = 12;
const PAS = LATIME_CARD + SPATIU;

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
 *
 * Latimea vizibila a benzii de carduri se rotunjeste la un numar intreg de
 * carduri (masurat cu ResizeObserver pe containerul din jur, nu pe banda
 * insasi — altfel dimensiunea s-ar masura pe ea insasi): raportat live,
 * fereastra glisanta arata mereu un card taiat pe muchia din dreapta, care
 * parea stricat, nu doar un indiciu ca mai sunt categorii de vazut.
 */
export function CategoriiCheltuieli({ date, cursuri }: { date: CheltuieliPeCategorie; cursuri: Curs[] }) {
  const container = useRef<HTMLDivElement>(null);
  const glisor = useRef<HTMLDivElement>(null);
  const { valuta } = useValutaDashboard();
  const categorii = totalizeazaPeCategorie(date.categorii, cursuri, valuta);
  const [latimeVizibila, setLatimeVizibila] = useState<number | null>(null);

  useEffect(() => {
    const nod = container.current;
    if (!nod) return;

    function recalculeaza(latimeDisponibila: number) {
      const numarCarduri = Math.max(1, Math.floor((latimeDisponibila + SPATIU) / PAS));
      setLatimeVizibila(numarCarduri * PAS - SPATIU);
    }

    recalculeaza(nod.clientWidth);

    const observator = new ResizeObserver(([intrare]) => {
      recalculeaza(intrare.contentRect.width);
    });
    observator.observe(nod);
    return () => observator.disconnect();
  }, [categorii.length]);

  function glisează(directie: 1 | -1) {
    glisor.current?.scrollBy({ left: directie * (latimeVizibila ?? PAS), behavior: "smooth" });
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

          {/* Masurat pentru latimea disponibila — banda de mai jos isi ia
              latimea vizibila de aici, rotunjita la un numar intreg de
              carduri, ca sa nu ramana niciodata unul taiat pe muchie. */}
          <div ref={container} className="min-w-0 flex-1">
            <div
              ref={glisor}
              style={latimeVizibila !== null ? { width: latimeVizibila } : undefined}
              className={cn(
                // mx-auto: latimea e fixa (calculata mai sus), deci banda poate
                // sta centrata in spatiul liber dintre cele doua sageti, in loc
                // sa ramana lipita de stanga cu un gol vizibil la dreapta.
                "mx-auto flex snap-x snap-mandatory gap-3 overflow-x-auto scroll-smooth",
                // Bara de derulare a browserului nu mai are ce cauta aici:
                // gestul de glisare si sagetile sunt deja un indiciu clar ca
                // se poate merge mai departe.
                "[-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
              )}
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
                      "hover:shadow-md active:scale-[0.98]",
                      "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                      // rand-hover: banda derulanta are overflow-x-auto, care taie orice
                      // inel se deseneaza in AFARA cardului. Regula globala de hover
                      // (globals.css) pune implicit un outline spre exterior pe orice
                      // element cu focus-visible:ring-4 — clasa asta o exclude si aplica
                      // in loc varianta ei spre interior (box-shadow inset), gandita
                      // exact pentru randuri/carduri din containere cu overflow.
                      "rand-hover",
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
