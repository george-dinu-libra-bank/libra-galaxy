"use client";

import Link from "next/link";
import { useState } from "react";
import { SelectorValuta } from "@/components/ui/selector-valuta";
import type { CategorieCheltuiala } from "@/lib/data/analiza";
import { CATEGORIE_INFO, etichetaCategorie, totalizeazaPeCategorie } from "@/lib/categorii";
import { cn, formateazaSuma } from "@/lib/utils";
import type { Curs, Valuta } from "@/lib/valute";

/**
 * Grila de categorii de pe /categorii, cu propriul buton de valuta — in
 * acelasi fel ca TotalConturi de pe dashboard, dar independent de acela:
 * paginile astea nu impart stare (ValutaDashboardContext traieste doar in
 * dashboard/page.tsx, care nu ramane montat cand navighezi aici).
 */
export function ListaCategorii({
  categoriiBrute,
  cursuri,
}: {
  categoriiBrute: CategorieCheltuiala[];
  cursuri: Curs[];
}) {
  const [valuta, setValuta] = useState<Valuta>("RON");
  const categorii = totalizeazaPeCategorie(categoriiBrute, cursuri, valuta);

  if (categorii.length === 0) {
    return (
      <p className="mt-16 text-center text-[15px] text-ink-faint">
        Nu ai nicio cheltuială luna asta.
      </p>
    );
  }

  return (
    <>
      <div className="mt-4 flex items-center justify-between">
        <p className="text-[13px] text-ink-faint">Convertit în valuta aleasă</p>
        <SelectorValuta
          valutaAleasa={valuta}
          onAlege={setValuta}
          ariaLabel="Alege valuta pentru cheltuielile pe categorii"
          descriere="Cheltuielile pe fiecare categorie se recalculează în valuta aleasă."
        />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3">
        {categorii.map((c) => {
          const info = CATEGORIE_INFO[c.categorie];
          const Icona = info?.icona ?? CATEGORIE_INFO.altele.icona;
          return (
            <Link
              key={c.categorie}
              href={`/categorii/${c.categorie}`}
              className={cn(
                "flex flex-col gap-2 rounded-card bg-surface p-4 shadow-sm",
                "transition-[transform,box-shadow] duration-150 ease-soft",
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
    </>
  );
}
