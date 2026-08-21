"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Clock, FileSearch, PenLine } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { acceptaOferta } from "@/lib/actions/credite";
import type { ContBancar } from "@/lib/data/conturi";
import type { CerereCredit } from "@/lib/data/credite";
import { formateazaSuma } from "@/lib/utils";

/**
 * Cererile care nu s-au terminat încă: ofertele de semnat și dosarele în analiză.
 *
 * Fără ecranul ăsta, o ofertă emisă după ce clientul a închis wizard-ul era
 * pierdută. Wizard-ul ținea oferta în starea lui de React și o arăta pe loc, dar
 * o cerere care trece prin analiză manuală primește oferta *mai târziu* — ore
 * sau zile după. Nu exista nicio cale înapoi la ea: `/credite` lista doar
 * creditele deja acordate.
 *
 * Se vede mai des de când o cerere fără venit confirmat nu se mai aprobă
 * automat: aproape orice ofertă ajunge acum să fie emisă în afara sesiunii.
 */
export function CereriInCurs({
  cereri,
  conturi,
}: {
  cereri: CerereCredit[];
  conturi: ContBancar[];
}) {
  const oferte = cereri.filter((cerere) => cerere.status === "oferta");
  const inAnaliza = cereri.filter(
    (cerere) => cerere.status === "analiza_manuala" || cerere.status === "in_analiza",
  );

  if (oferte.length === 0 && inAnaliza.length === 0) return null;

  return (
    <div className="mt-6 space-y-3">
      {oferte.map((cerere) => (
        <Oferta key={cerere.id} cerere={cerere} conturi={conturi} />
      ))}
      {inAnaliza.map((cerere) => (
        <InAnaliza key={cerere.id} cerere={cerere} />
      ))}
    </div>
  );
}

function Oferta({ cerere, conturi }: { cerere: CerereCredit; conturi: ContBancar[] }) {
  const router = useRouter();
  const [idCont, setIdCont] = useState(conturi[0]?.id ?? "");
  const [eroare, setEroare] = useState<string | null>(null);
  const [gata, setGata] = useState(false);
  const [seTrimite, startTransition] = useTransition();

  // Conturile pot fi in valute diferite, dar creditul se acorda in RON: un
  // disbursement intr-un cont in EUR ar cere o conversie pe care nimeni n-a
  // cerut-o si la un curs pe care nimeni n-a vazut-o.
  const conturiRon = conturi.filter((cont) => cont.valuta === "RON");
  const expira = cerere.ofertaExpiraLa ? new Date(cerere.ofertaExpiraLa) : null;
  const expirata = expira !== null && expira.getTime() < Date.now();

  function semneaza() {
    if (!idCont) {
      setEroare("Alege contul în care intră banii.");
      return;
    }
    setEroare(null);

    startTransition(async () => {
      const rezultat = await acceptaOferta(cerere.id, idCont);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setGata(true);
      router.refresh();
    });
  }

  if (gata) {
    return (
      <section className="rounded-card bg-surface p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <CheckCircle2 size={22} strokeWidth={1.75} aria-hidden className="text-success" />
          <p className="text-[15px] font-semibold text-ink">
            {formateazaSuma(cerere.sumaCeruta)} au intrat în cont
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-card border border-primary-600/30 bg-surface p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <span className="rounded-full bg-success/10 px-2 py-0.5 text-[11px] font-medium text-success">
          Ofertă aprobată
        </span>
        <span className="text-[13px] text-ink-faint">{cerere.luni} luni</span>
      </div>

      <p className="tabular mt-2 text-[22px] font-bold leading-[28px] text-ink">
        {formateazaSuma(cerere.sumaCeruta)}
      </p>
      <p className="text-[13px] text-ink-faint">
        rată {cerere.rataLunara ? formateazaSuma(cerere.rataLunara) : "—"}
        {cerere.dae ? ` · DAE ${(cerere.dae * 100).toFixed(2).replace(".", ",")}%` : ""}
      </p>

      {expira ? (
        <p className={`mt-2 text-[12.5px] ${expirata ? "text-danger" : "text-ink-faint"}`}>
          {expirata
            ? "Oferta a expirat. Depune o cerere nouă."
            : `Valabilă până pe ${expira.toLocaleDateString("ro-RO", {
                day: "numeric",
                month: "long",
              })}`}
        </p>
      ) : null}

      {cerere.explicatie ? (
        <p className="mt-3 whitespace-pre-line text-[13px] leading-[19px] text-ink-soft">
          {cerere.explicatie}
        </p>
      ) : null}

      {eroare ? (
        <div className="mt-4">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      {!expirata ? (
        <>
          <label className="mt-4 block text-[13px] text-ink-faint" htmlFor={`cont-${cerere.id}`}>
            Banii intră în
          </label>
          <select
            id={`cont-${cerere.id}`}
            value={idCont}
            onChange={(eveniment) => setIdCont(eveniment.target.value)}
            className="mt-1.5 h-12 w-full rounded-field border border-line bg-bg px-3 text-[15px] text-ink focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            {(conturiRon.length > 0 ? conturiRon : conturi).map((cont) => (
              <option key={cont.id} value={cont.id}>
                {cont.nume} · {cont.ibanMascat}
              </option>
            ))}
          </select>

          <Button
            className="mt-4 w-full"
            loading={seTrimite}
            onClick={semneaza}
            iconaStanga={<PenLine size={18} strokeWidth={1.75} aria-hidden />}
          >
            Semnează și primește {formateazaSuma(cerere.sumaCeruta)}
          </Button>
        </>
      ) : null}
    </section>
  );
}

function InAnaliza({ cerere }: { cerere: CerereCredit }) {
  const manuala = cerere.status === "analiza_manuala";

  return (
    <section className="rounded-card bg-surface p-5 shadow-sm">
      <div className="flex items-start gap-3">
        {manuala ? (
          <FileSearch size={20} strokeWidth={1.75} aria-hidden className="mt-0.5 text-warning" />
        ) : (
          <Clock size={20} strokeWidth={1.75} aria-hidden className="mt-0.5 text-ink-faint" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold text-ink">
            Cerere de {formateazaSuma(cerere.sumaCeruta)} · {cerere.luni} luni
          </p>
          <p className="mt-1 text-[13px] leading-[19px] text-ink-soft">
            {manuala
              ? "Un coleg se uită peste dosar. Primești răspunsul în cel mult două zile lucrătoare."
              : "Se verifică."}
          </p>
        </div>
      </div>
    </section>
  );
}
