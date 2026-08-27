"use client";

import { useState } from "react";
import { Check, Copy, Eye, EyeOff, Lock, Unlock } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import type { DateSensibileCard } from "@/lib/actions/carduri";
import type { CardAfisat } from "@/lib/data/carduri";
import { cn, formateazaSuma } from "@/lib/utils";

/**
 * Tot ce se stie despre cardul din centrul caruselului, sub el, permanent.
 *
 * Inainte, informatiile astea stateau intr-un drawer care se deschidea apasand
 * cardul. Doua lucruri nu mergeau: apasarea cardului te ducea in ALTA parte,
 * desi obiectul pe care vrei sa-l vezi e chiar cardul; si nimic din ce scrie
 * aici nu era vizibil fara sa deschizi ceva. Acum apasarea intoarce cardul, iar
 * detaliile sunt mereu pe ecran — n-am pierdut niciun rand din vechiul drawer.
 *
 * Blocarea a coborat si ea aici, langa restul. In drawer statea in subsol si se
 * vedea doar cat era drawerul deschis.
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

      <div className="mt-3 border-t border-line">
        <Rand
          eticheta="Număr"
          valoare={dateSensibile?.numar ?? card.numarMascat}
          mono
          copiabil={Boolean(dateSensibile)}
        />
        <Rand eticheta="CCV" valoare={dateSensibile?.ccv ?? "•••"} mono copiabil={Boolean(dateSensibile)} />
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

      <div className="mt-4 flex flex-col gap-2">
        <Button
          varianta="secondary"
          className="w-full"
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
          {dateSensibile ? "Ascunde datele sensibile" : "Arată datele sensibile"}
        </Button>

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

function Rand({
  eticheta,
  valoare,
  mono,
  copiabil,
}: {
  eticheta: string;
  valoare: string;
  mono?: boolean;
  copiabil?: boolean;
}) {
  const [copiat, setCopiat] = useState(false);

  async function copiaza() {
    try {
      await navigator.clipboard.writeText(valoare.replace(/\s+/g, ""));
      setCopiat(true);
      setTimeout(() => setCopiat(false), 1500);
    } catch {
      // clipboard indisponibil (ex. context non-securizat) — nu blocam UI-ul
    }
  }

  return (
    <div className="flex items-center justify-between gap-4 border-b border-line py-2.5 last:border-0">
      <span className="text-[13px] text-ink-faint">{eticheta}</span>
      <span className="flex items-center gap-2">
        <span className={cn("text-right text-[15px] text-ink", mono && "tabular")}>{valoare}</span>
        {copiabil ? (
          <button
            type="button"
            onClick={copiaza}
            aria-label={copiat ? "Copiat" : `Copiază ${eticheta.toLowerCase()}`}
            // 28 px vizual, dar tinta de atingere ajunge la 44 px prin padding
            // negativ — cerinta din DESIGN.md #10, fara sa creasca iconita.
            className="-m-2 flex h-7 w-7 shrink-0 items-center justify-center rounded-full p-2 text-ink-faint transition-colors hover:bg-primary-50 hover:text-primary-600 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            {copiat ? (
              <Check size={14} strokeWidth={1.75} aria-hidden className="text-success" />
            ) : (
              <Copy size={14} strokeWidth={1.75} aria-hidden />
            )}
          </button>
        ) : null}
      </span>
    </div>
  );
}
