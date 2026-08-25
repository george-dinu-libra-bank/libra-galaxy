"use client";

import { useRouter } from "next/navigation";
import { ArrowRight, Check, ChevronLeft, Repeat } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import type { ContBancar } from "@/lib/data/conturi";
import { DESPRE_VALUTA, VALUTE, converteste, type Curs, type Valuta } from "@/lib/valute";
import { schimbaValutaSuma } from "@/lib/actions/schimb-valutar";
import { cn, formateazaIban, formateazaSuma } from "@/lib/utils";

/**
 * Schimbul valutar: alegi contul, apoi suma si valuta in care o vrei.
 *
 * Suma trece din contul sursa intr-un cont separat, in noua valuta — creat
 * automat daca nu ai deja unul, la fel ca la deschiderea manuala de cont, doar
 * fara pas de confirmare (0019_schimb_valutar_suma.sql). Sumele aratate aici
 * sunt orientative — cifra care conteaza o face public.schimba_valuta_suma in
 * momentul schimbului, la cursul din baza de date.
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
  const [suma, setSuma] = useState("");
  const [valuta, setValuta] = useState<Valuta | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const contAles = conturi.find((cont) => cont.id === idCont) ?? null;
  const sumaNumar = Number(suma.replace(",", "."));
  const sumaValida = Number.isFinite(sumaNumar) && sumaNumar > 0 && (contAles ? sumaNumar <= contAles.sold : false);

  // Randul de RON e mereu 1, pus la migrare — data si sursa reale sunt pe
  // valutele straine. Nu scriem „curs BNR" cand cursul a venit din alta parte.
  const referinta = cursuri.find((curs) => curs.valuta !== "RON") ?? null;

  function inchide() {
    setDeschis(false);
    setIdCont(null);
    setSuma("");
    setValuta(null);
    setEroare(null);
  }

  function trimite() {
    if (!contAles || !valuta || !sumaValida) return;

    setEroare(null);

    startTransition(async () => {
      const rezultat = await schimbaValutaSuma(contAles.id, sumaNumar, valuta);

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
            <Button className="w-full" loading={seTrimite} disabled={!sumaValida} onClick={trimite}>
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
              suma={suma}
              laSuma={setSuma}
              valutaAleasa={valuta}
              laAlegere={setValuta}
              inapoi={() => {
                setIdCont(null);
                setSuma("");
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
                <span className="tabular flex items-center gap-2 text-[12.5px] text-ink-faint">
                  {cont.ibanMascat}
                  <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10.5px] font-semibold text-ink-soft">
                    {cont.valuta}
                  </span>
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

/** Pasul 2: cat schimbam si in ce valuta. */
function PasValuta({
  cont,
  cursuri,
  suma,
  laSuma,
  valutaAleasa,
  laAlegere,
  inapoi,
}: {
  cont: ContBancar;
  cursuri: Curs[];
  suma: string;
  laSuma: (suma: string) => void;
  valutaAleasa: Valuta | null;
  laAlegere: (valuta: Valuta) => void;
  inapoi: () => void;
}) {
  const sumaNumar = Number(suma.replace(",", "."));
  const sumaValida = Number.isFinite(sumaNumar) && sumaNumar > 0;
  const depasesteSoldul = sumaValida && sumaNumar > cont.sold;

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
        <p className="tabular flex items-center gap-2 truncate text-[13px] text-ink-soft">
          {cont.nume} · {formateazaIban(cont.iban)}
          <span className="rounded-full bg-surface px-1.5 py-0.5 text-[10.5px] font-semibold text-ink-soft">
            {cont.valuta}
          </span>
        </p>
        <p className="tabular text-[20px] font-bold leading-7 text-ink">
          {formateazaSuma(cont.sold, cont.valuta)}
        </p>
      </div>

      <div>
        <label htmlFor="suma-schimb" className="text-[13px] text-ink-faint">
          Cât vrei să schimbi?
        </label>
        <div className="mt-1.5 flex items-center gap-2">
          <div className="relative flex-1">
            <input
              id="suma-schimb"
              type="text"
              inputMode="decimal"
              value={suma}
              onChange={(e) => laSuma(e.target.value)}
              placeholder="0,00"
              className={cn(
                "tabular w-full rounded-field border bg-surface px-4 py-3 pr-16 text-[17px] font-semibold text-ink outline-none transition-colors",
                "focus:border-primary-500 focus:ring-4 focus:ring-primary-500/12",
                depasesteSoldul ? "border-danger" : "border-line",
              )}
            />
            <span className="tabular absolute right-4 top-1/2 -translate-y-1/2 text-[13px] text-ink-faint">
              {cont.valuta}
            </span>
          </div>
          <button
            type="button"
            onClick={() => laSuma(String(cont.sold))}
            className="shrink-0 rounded-field border border-line bg-surface px-3 py-3 text-[12.5px] font-semibold text-primary-600 transition-colors hover:bg-primary-50"
          >
            Tot soldul
          </button>
        </div>
        {depasesteSoldul ? (
          <p className="mt-1.5 text-[12.5px] text-danger">Depășește soldul disponibil.</p>
        ) : null}
      </div>

      <p className="text-[13px] text-ink-faint">În ce monedă o vrei?</p>

      <ul className="flex flex-col gap-2">
        {VALUTE.filter((valuta) => valuta !== cont.valuta).map((valuta) => {
          const primesti = sumaValida ? converteste(sumaNumar, cont.valuta, valuta, cursuri) : null;
          const ales = valuta === valutaAleasa;

          return (
            <li key={valuta}>
              <button
                type="button"
                // Fara curs sau fara suma introdusa nu putem promite nimic.
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
                    {!sumaValida
                      ? "Introdu o sumă"
                      : primesti === null
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
        Sumele sunt orientative. Schimbul se face la cursul din momentul confirmării. Dacă nu ai
        deja un cont în moneda aleasă, îți deschidem unul automat.
      </p>
    </>
  );
}
