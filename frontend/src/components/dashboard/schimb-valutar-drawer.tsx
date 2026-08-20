"use client";

import { useRouter } from "next/navigation";
import { ArrowRight, Check, ChevronLeft, Repeat } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import type { ContBancar } from "@/lib/data/conturi";
import { DESPRE_VALUTA, VALUTE, converteste, type Curs, type Valuta } from "@/lib/valute";
import { schimbaValuta } from "@/lib/actions/schimb-valutar";
import { cn, formateazaSuma } from "@/lib/utils";

/**
 * Schimbul valutar: alegi contul, apoi valuta in care il vrei.
 *
 * Sumele aratate aici sunt orientative — le calculam cu aceleasi cursuri, dar
 * cifra care conteaza o face public.schimba_valuta_cont in momentul schimbului,
 * la cursul din baza de date. Asa nu se poate intampla ca un ecran ramas
 * deschis de dimineata sa converteasca la cursul de dimineata.
 */
export function SchimbValutarDrawer({
  conturi,
  cursuri,
  className,
}: {
  conturi: ContBancar[];
  cursuri: Curs[];
  /** Stilul dalei din „Actiuni rapide", dat de ecran ca sa arate ca surorile ei. */
  className?: string;
}) {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [idCont, setIdCont] = useState<string | null>(null);
  const [valuta, setValuta] = useState<Valuta | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const contAles = conturi.find((cont) => cont.id === idCont) ?? null;

  // Randul de RON e mereu 1, pus la migrare — data si sursa reale sunt pe
  // valutele straine. Nu scriem „curs BNR" cand cursul a venit din alta parte.
  const referinta = cursuri.find((curs) => curs.valuta !== "RON") ?? null;

  function inchide() {
    setDeschis(false);
    setIdCont(null);
    setValuta(null);
    setEroare(null);
  }

  function trimite() {
    if (!contAles || !valuta) return;

    setEroare(null);

    startTransition(async () => {
      const rezultat = await schimbaValuta(contAles.id, valuta);

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      inchide();
      router.refresh();
    });
  }

  return (
    <Drawer
      open={deschis}
      onOpenChange={(valoare) => (valoare ? setDeschis(true) : inchide())}
    >
      <DrawerTrigger aria-label="Schimb valutar" className={className}>
        <Repeat size={22} strokeWidth={1.75} aria-hidden className="text-primary-600" />
        <span className="text-center text-xs leading-4 text-ink-soft">Schimb valutar</span>
      </DrawerTrigger>

      <DrawerContent
        title="Schimb valutar"
        description={
          referinta
            ? `Cursuri de referință ${referinta.sursa}, ${new Date(
                referinta.dataCurs,
              ).toLocaleDateString("ro-RO", {
                day: "numeric",
                month: "long",
                year: "numeric",
                timeZone: "Europe/Bucharest",
              })}.`
            : "Cursurile nu sunt disponibile momentan."
        }
        // Drawerul cere 90vh: are de tinut o lista de conturi si una de valute,
        // fara ca vreuna sa se citeasca printr-o fereastra ingusta.
        className="h-[90vh] max-h-[90vh]"
        footer={
          contAles && valuta ? (
            <Button className="w-full" loading={seTrimite} onClick={trimite}>
              Schimbă în {valuta}
            </Button>
          ) : null
        }
      >
        <div className="flex flex-col gap-4">
          {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

          {conturi.length === 0 ? (
            <p className="rounded-card bg-muted p-6 text-center text-[15px] text-ink-faint">
              Nu ai niciun cont de schimbat.
            </p>
          ) : !contAles ? (
            <PasCont conturi={conturi} laAlegere={setIdCont} />
          ) : (
            <PasValuta
              cont={contAles}
              cursuri={cursuri}
              valutaAleasa={valuta}
              laAlegere={setValuta}
              inapoi={() => {
                setIdCont(null);
                setValuta(null);
                setEroare(null);
              }}
            />
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}

/** Pasul 1: din ce cont schimbam. */
function PasCont({
  conturi,
  laAlegere,
}: {
  conturi: ContBancar[];
  laAlegere: (id: string) => void;
}) {
  return (
    <>
      <p className="text-[13px] text-ink-faint">Ce cont vrei să schimbi?</p>

      <ul className="flex flex-col gap-2">
        {conturi.map((cont) => (
          <li key={cont.id}>
            <button
              type="button"
              onClick={() => laAlegere(cont.id)}
              className="flex w-full items-center gap-3 rounded-field border border-line bg-surface px-4 py-3 text-left transition-colors hover:border-primary-300 hover:bg-primary-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] font-medium text-ink">
                  {cont.nume}
                </span>
                <span className="tabular block text-[12.5px] text-ink-faint">
                  {cont.ibanMascat}
                </span>
              </span>

              <span className="tabular shrink-0 text-[15px] font-semibold text-ink">
                {formateazaSuma(cont.sold, cont.valuta)}
              </span>

              <ArrowRight
                size={16}
                strokeWidth={2}
                aria-hidden
                className="shrink-0 text-ink-faint"
              />
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

/** Pasul 2: in ce valuta il trecem. */
function PasValuta({
  cont,
  cursuri,
  valutaAleasa,
  laAlegere,
  inapoi,
}: {
  cont: ContBancar;
  cursuri: Curs[];
  valutaAleasa: Valuta | null;
  laAlegere: (valuta: Valuta) => void;
  inapoi: () => void;
}) {
  return (
    <>
      <button
        type="button"
        onClick={inapoi}
        className="-ml-2 flex w-fit items-center gap-1 rounded-field px-2 py-1 text-[13px] font-semibold text-primary-600 transition-colors hover:bg-primary-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <ChevronLeft size={16} strokeWidth={2} aria-hidden />
        Alt cont
      </button>

      <div className="rounded-card bg-muted px-4 py-3">
        <p className="truncate text-[13px] text-ink-soft">{cont.nume}</p>
        <p className="tabular text-[20px] font-bold leading-7 text-ink">
          {formateazaSuma(cont.sold, cont.valuta)}
        </p>
      </div>

      <p className="text-[13px] text-ink-faint">În ce monedă îl vrei?</p>

      <ul className="flex flex-col gap-2">
        {VALUTE.filter((valuta) => valuta !== cont.valuta).map((valuta) => {
          const primesti = converteste(cont.sold, cont.valuta, valuta, cursuri);
          const ales = valuta === valutaAleasa;

          return (
            <li key={valuta}>
              <button
                type="button"
                // Fara curs nu putem promite nimic, deci nici nu lasam alegerea.
                disabled={primesti === null}
                onClick={() => laAlegere(valuta)}
                aria-pressed={ales}
                className={cn(
                  "flex w-full items-center gap-3 rounded-field border px-4 py-3 text-left transition-colors",
                  "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                  "disabled:cursor-not-allowed disabled:opacity-50",
                  ales
                    ? "border-primary-500 bg-primary-50"
                    : "border-line bg-surface hover:border-primary-300 hover:bg-primary-50",
                )}
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-[15px] font-medium text-ink">
                    {valuta} · {DESPRE_VALUTA[valuta].nume}
                  </span>
                  <span className="tabular block text-[12.5px] text-ink-faint">
                    {primesti === null
                      ? "Curs indisponibil"
                      : `Primești ≈ ${formateazaSuma(primesti, valuta)}`}
                  </span>
                </span>

                {ales ? (
                  <Check
                    size={18}
                    strokeWidth={2.5}
                    aria-hidden
                    className="shrink-0 text-primary-600"
                  />
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>

      <p className="text-[12.5px] leading-[18px] text-ink-faint">
        Sumele sunt orientative. Schimbul se face la cursul din momentul confirmării.
      </p>
    </>
  );
}
