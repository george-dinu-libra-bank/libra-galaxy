"use client";

import { SoldAnimat } from "@/components/dashboard/sold-animat";
import { useValutaDashboard } from "@/components/dashboard/context-valuta";
import { SelectorValuta } from "@/components/ui/selector-valuta";
import type { ContBancar } from "@/lib/data/conturi";
import { totalSoldIn, type Curs } from "@/lib/valute";

/**
 * Totalul din conturi, cu un buton de alegere a valutei pe acelasi rand
 * (`items-baseline`) — conversia se face client-side cu cursurile deja
 * aduse pe server, fara cerere noua la fiecare schimbare.
 *
 * Valuta aleasa aici vine din ValutaDashboardContext, nu dintr-un state local:
 * CategoriiCheltuieli, mai jos in pagina, trebuie sa se recalculeze cu aceeasi
 * alegere, iar cele doua componente nu sunt adiacente in dashboard/page.tsx.
 */
export function TotalConturi({
  conturi,
  cursuri,
}: {
  conturi: ContBancar[];
  cursuri: Curs[];
}) {
  const { valuta, seteazaValuta } = useValutaDashboard();
  const total = totalSoldIn(conturi, cursuri, valuta);

  return (
    <div className="flex items-baseline gap-2">
      <SoldAnimat
        sold={total}
        arataValuta={false}
        className="tabular text-[30px] font-bold leading-[36px] text-ink"
      />

      <SelectorValuta
        valutaAleasa={valuta}
        onAlege={seteazaValuta}
        ariaLabel="Alege valuta pentru total"
        descriere="Totalul din conturi și cheltuielile pe categorii se recalculează în valuta aleasă."
      />
    </div>
  );
}
