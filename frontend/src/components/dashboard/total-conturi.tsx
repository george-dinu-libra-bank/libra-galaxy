"use client";

import { Check, ChevronDown } from "lucide-react";
import { useState } from "react";
import { SoldAnimat } from "@/components/dashboard/sold-animat";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import type { ContBancar } from "@/lib/data/conturi";
import { cn } from "@/lib/utils";
import { DESPRE_VALUTA, VALUTE, totalSoldIn, type Curs, type Valuta } from "@/lib/valute";

/**
 * Totalul din conturi, cu un buton de alegere a valutei pe acelasi rand
 * (`items-baseline`) — conversia se face client-side cu cursurile deja
 * aduse pe server, fara cerere noua la fiecare schimbare.
 */
export function TotalConturi({
  conturi,
  cursuri,
}: {
  conturi: ContBancar[];
  cursuri: Curs[];
}) {
  const [valutaAleasa, setValutaAleasa] = useState<Valuta>("RON");
  const [deschis, setDeschis] = useState(false);
  const total = totalSoldIn(conturi, cursuri, valutaAleasa);

  return (
    <div className="flex items-baseline gap-2">
      <SoldAnimat
        sold={total}
        arataValuta={false}
        className="tabular text-[30px] font-bold leading-[36px] text-ink"
      />

      <Drawer open={deschis} onOpenChange={setDeschis}>
        <DrawerTrigger
          aria-label="Alege valuta pentru total"
          className="flex shrink-0 items-center gap-0.5 rounded-full bg-muted px-2 py-1 text-[12px] font-semibold text-ink-soft transition-colors hover:bg-white/10 hover:text-primary-400"
        >
          {valutaAleasa}
          <ChevronDown size={12} strokeWidth={2} aria-hidden />
        </DrawerTrigger>

        <DrawerContent
          title="Alege valuta"
          description="Totalul din conturi se recalculează în valuta aleasă."
        >
          <div className="flex flex-col gap-2">
            {VALUTE.map((valuta) => {
              const ales = valuta === valutaAleasa;
              return (
                <button
                  key={valuta}
                  type="button"
                  aria-pressed={ales}
                  onClick={() => {
                    setValutaAleasa(valuta);
                    setDeschis(false);
                  }}
                  className={cn(
                    "flex items-center justify-between gap-3 rounded-field border bg-surface px-4 py-3 text-left transition-colors",
                    "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                    // Contur, nu fundal deschis: bg-primary-50 pe tema intunecata facea
                    // textul (text-ink, deschis la culoare) invizibil pe fundal deschis
                    // — aceeasi lectie ca la lista-conversatii-drawer.tsx.
                    ales ? "border-white/70" : "border-line hover:border-primary-400",
                  )}
                >
                  <span className="text-[15px] font-medium text-ink">
                    {valuta} · {DESPRE_VALUTA[valuta].nume}
                  </span>
                  {ales ? <Check size={18} strokeWidth={2} className="text-primary-600" aria-hidden /> : null}
                </button>
              );
            })}
          </div>
        </DrawerContent>
      </Drawer>
    </div>
  );
}
