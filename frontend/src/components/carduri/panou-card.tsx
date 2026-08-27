"use client";

import { Eye, EyeOff, Lock, Unlock } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import type { DateSensibileCard } from "@/lib/actions/carduri";
import type { CardAfisat } from "@/lib/data/carduri";
import { cn, formateazaSuma } from "@/lib/utils";

/**
 * Ce se stie despre cardul din centrul caruselului, sub el, permanent.
 *
 * Tot ce scrie AICI se poate citi oricand, fara sa ceri nimic: cont, sold,
 * expirare, tip, limita, stare. Numarul complet si CCV-ul nu sunt pe lista —
 * ele apar doar pe spatele cardului, dupa confirmare, si tot de acolo se
 * copiaza. Asa datele sensibile au un singur loc in care pot fi vazute, iar
 * acela e chiar cel pe care omul il intoarce cu mana lui.
 *
 * Inainte, informatiile astea stateau intr-un drawer care se deschidea apasand
 * cardul. Doua lucruri nu mergeau: apasarea cardului te ducea in ALTA parte,
 * desi obiectul pe care vrei sa-l vezi e chiar cardul; si nimic din ce scrie
 * aici nu era vizibil fara sa deschizi ceva. Acum apasarea intoarce cardul, iar
 * detaliile sunt mereu pe ecran — n-am pierdut niciun rand din vechiul drawer.
 *
 * Blocarea a coborat si ea aici, langa restul. In drawer statea in subsol si se
 * vedea doar cat era drawerul deschis.
 *
 * Butonul „Arata datele" e SINGURUL drum catre numarul complet si CCV. Apasarea
 * pe card nu-l ocoleste: aceea doar intoarce cardul, in ambele sensuri. Butonul
 * cere confirmarea intr-un drawer (DESIGN.md #8.1), iar dupa ea cardul se
 * intoarce singur, cu datele deja pe spate.
 */
export function PanouCard({
  card,
  dateSensibile,
  seDezvaluie,
  seBlocheaza,
  onDezvaluie,
  onAscunde,
  onComutaBlocare,
}: {
  card: CardAfisat;
  dateSensibile: DateSensibileCard | null;
  seDezvaluie: boolean;
  seBlocheaza: boolean;
  onDezvaluie: () => void;
  onAscunde: () => void;
  onComutaBlocare: () => void;
}) {
  return (
    <section className="mx-6 mt-2 rounded-card bg-surface p-4 shadow-sm">
      <div className="min-w-0">
        <p className="truncate text-[11px] uppercase tracking-wide text-ink-faint">
          {card.numeCont ?? "Fără cont"}
        </p>
        <p className="tabular truncate text-[19px] font-semibold text-ink">
          {formateazaSuma(card.sold, card.valuta)}
        </p>
      </div>

      {/* Butonul sta imediat sub sold, inaintea randurilor de detalii — nu in
          subsolul panoului. E singurul drum catre numarul complet si CCV, deci
          n-are ce cauta dupa o lista pe care omul trebuie sa o parcurga intai;
          iar pe ecran mic, in subsol, cadea sub marginea de jos. */}
      <Button
        varianta="secondary"
        className="mt-4 w-full"
        loading={seDezvaluie}
        aria-busy={seDezvaluie}
        iconaStanga={
          dateSensibile ? (
            <EyeOff size={18} strokeWidth={1.75} aria-hidden />
          ) : (
            <Eye size={18} strokeWidth={1.75} aria-hidden />
          )
        }
        onClick={dateSensibile ? onAscunde : onDezvaluie}
      >
        {dateSensibile ? "Ascunde datele" : "Arată datele"}
      </Button>

      <div className="mt-3 border-t border-line">
        <Rand eticheta="Expiră" valoare={card.dataExpirare} mono />
        <Rand eticheta="Tip" valoare={card.tip === "virtual" ? "Virtual" : "Fizic"} />
        <Rand
          eticheta="Limită zilnică"
          valoare={
            card.limitaZilnica === null
              ? "Fără limită"
              : formateazaSuma(card.limitaZilnica, card.valuta)
          }
          mono
        />
        <Rand
          eticheta="Stare"
          valoare={
            card.blocatDeBanca ? "Blocat de bancă" : card.blocat ? "Blocat de tine" : "Activ"
          }
        />
      </div>

      {card.blocatDeBanca ? (
        <div className="mt-4">
          <Banda ton="eroare">
            Cardul a fost blocat de bancă. Nu poate fi deblocat din aplicație — contactează
            suportul pentru a afla motivul.
          </Banda>
        </div>
      ) : null}

      <div className="mt-4">
        <Button
          varianta={card.blocat ? "primary" : "danger"}
          className="w-full"
          loading={seBlocheaza}
          aria-busy={seBlocheaza}
          iconaStanga={
            card.blocat ? (
              <Unlock size={18} strokeWidth={1.75} aria-hidden />
            ) : (
              <Lock size={18} strokeWidth={1.75} aria-hidden />
            )
          }
          disabled={card.blocatDeBanca}
          onClick={onComutaBlocare}
        >
          {card.blocat ? "Deblochează cardul" : "Blochează cardul"}
        </Button>
      </div>
    </section>
  );
}

/**
 * Un rand de detaliu. Nu mai are buton de copiere: singurele valori pe care
 * cineva chiar le copiaza — numarul si CCV-ul — nu mai trec pe aici, ci se
 * copiaza de pe spatele cardului, de langa cifrele pe care omul le vede.
 */
function Rand({
  eticheta,
  valoare,
  mono,
}: {
  eticheta: string;
  valoare: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line py-2.5 last:border-0">
      <span className="text-[13px] text-ink-faint">{eticheta}</span>
      <span className={cn("text-right text-[15px] text-ink", mono && "tabular")}>{valoare}</span>
    </div>
  );
}
