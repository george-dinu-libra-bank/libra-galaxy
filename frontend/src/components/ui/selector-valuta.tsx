"use client";

import { Check, ChevronDown } from "lucide-react";
import { useState } from "react";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { DESPRE_VALUTA, VALUTE, type Valuta } from "@/lib/valute";
import { cn } from "@/lib/utils";

/**
 * Pilula "RON ⌄" + drawer de alegere — extrasa din TotalConturi, ca sa fie
 * folosita identic oriunde apare un total recalculat in alta valuta (dashboard,
 * pagina /categorii). Un singur loc de intretinut vizualul, nu o copie per ecran.
 */
export function SelectorValuta({
  valutaAleasa,
  onAlege,
  ariaLabel,
  descriere,
  className,
}: {
  valutaAleasa: Valuta;
  onAlege: (valuta: Valuta) => void;
  ariaLabel: string;
  descriere: string;
  className?: string;
}) {
  const [deschis, setDeschis] = useState(false);

  return (
    <Drawer open={deschis} onOpenChange={setDeschis}>
      <DrawerTrigger
        aria-label={ariaLabel}
        className={cn(
          "flex shrink-0 items-center gap-0.5 rounded-full bg-muted px-2 py-1 text-[12px] font-semibold text-ink-soft transition-colors hover:bg-white/10 hover:text-primary-400",
          className,
        )}
      >
        {valutaAleasa}
        <ChevronDown size={12} strokeWidth={2} aria-hidden />
      </DrawerTrigger>

      <DrawerContent title="Alege valuta" description={descriere}>
        <div className="flex flex-col gap-2">
          {VALUTE.map((valuta) => {
            const ales = valuta === valutaAleasa;
            return (
              <button
                key={valuta}
                type="button"
                aria-pressed={ales}
                onClick={() => {
                  onAlege(valuta);
                  setDeschis(false);
                }}
                className={cn(
                  "flex items-center justify-between gap-3 rounded-field border bg-surface px-4 py-3 text-left transition-colors",
                  "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                  // Contur, nu fundal deschis: bg-primary-50 pe tema intunecata facea
                  // textul (text-ink, deschis la culoare) invizibil pe fundal deschis.
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
  );
}
