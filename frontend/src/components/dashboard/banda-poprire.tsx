import { Scale } from "lucide-react";
import type { PoprireClient } from "@/lib/data/popriri";
import { formateazaSuma } from "@/lib/utils";

/**
 * „O parte din bani sunt indisponibili, si de ce."
 *
 * Sta deasupra listei de conturi, nu pe fiecare rand: poprirea e pe OM, nu pe
 * cont (0047), si repetata pe patru conturi ar sugera patru popriri.
 *
 * Rostul ei e ca omul sa afle INAINTE, nu cand incearca un transfer si primeste
 * POPRIRE_ACTIVA. Aceeasi lectie ca la cardul si contul blocate, scrisa in
 * `lista-carduri.tsx`: un cont oprit arata pana atunci exact ca unul normal, iar
 * clientul afla abia la plata.
 *
 * Textul spune si ce NU se opreste — incasarile intra normal, iar banii peste
 * suma poprita raman ai lui. Fara asta, eticheta se citeste „mi-au blocat tot".
 */
export function BandaPoprire({ poprire }: { poprire: PoprireClient }) {
  return (
    <section
      className="mt-6 flex gap-3 rounded-card border border-warning/30 bg-warning/5 p-4"
      aria-label="Poprire pe conturi"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-warning/15">
        <Scale size={18} strokeWidth={1.75} aria-hidden className="text-warning" />
      </span>

      <div className="min-w-0">
        <p className="text-[15px] font-semibold text-ink">
          {formateazaSuma(poprire.restDePlata, "RON")} indisponibili
        </p>
        <p className="mt-1 text-[13.5px] leading-[19px] text-ink-soft">
          {poprire.numar === 1 ? (
            <>
              Am primit o poprire de la <strong className="font-medium">{poprire.creditor}</strong>.
            </>
          ) : (
            <>
              Ai {poprire.numar} popriri pe conturi, prima de la{" "}
              <strong className="font-medium">{poprire.creditor}</strong>.
            </>
          )}{" "}
          Suma de mai sus nu poate fi folosită până la stingerea ei. Restul banilor rămân la
          dispoziția ta, iar încasările intră normal. Pentru contestații te adresezi creditorului.
        </p>
      </div>
    </section>
  );
}
