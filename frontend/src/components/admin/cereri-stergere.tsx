"use client";

import { Trash2, TriangleAlert } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { etichetaStare } from "@/lib/stari-cerere";
import { decideCerereStergere, stergeClientul } from "@/lib/actions/admin-stergeri";
import {
  motiveleStergerii,
  sePoateSterge,
  type CerereStergere,
} from "@/lib/tipuri-admin";

/**
 * Cererile de inchidere a contului, pentru analist.
 *
 * Doua actiuni, in doi pasi separati:
 *   1. **Decizia** — aproba sau respinge. La aprobare, RPC-ul consolideaza intai
 *      conturile secundare in cel principal, si scrie notificarea catre client.
 *   2. **Stergerea** — abia dupa aprobare, si doar daca toate conturile sunt pe
 *      zero. Poarta sta in `public.sterge_client` (0038), nu in butonul de aici:
 *      un buton dezactivat e o sugestie, o exceptie din RPC e o regula.
 *
 * Butonul dezactivat nu e mut: scrie exact ce mai e de facut. Un „Șterge" gri
 * fara explicatie e cel mai bun mod de a face un analist sa deschida un tichet.
 */

export function CereriStergere({ cereri }: { cereri: CerereStergere[] }) {
  if (cereri.length === 0) return null;

  return (
    <section className="mt-10">
      <h2 className="text-lg font-semibold text-ink">Cereri de închidere a contului</h2>
      <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
        Aprobarea mută banii din conturile secundare în cel principal și anunță clientul.
        Ștergerea e un pas separat, permis doar când toate conturile sunt pe zero.
      </p>

      <div className="mt-4 flex flex-col gap-3">
        {cereri.map((cerere) => (
          <Cerere key={cerere.id} cerere={cerere} />
        ))}
      </div>
    </section>
  );
}

function Cerere({ cerere }: { cerere: CerereStergere }) {
  const [motiv, setMotiv] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seLucreaza, startTransition] = useTransition();

  const status = etichetaStare(cerere.status);
  const blocaje = motiveleStergerii(cerere);
  const poate = sePoateSterge(cerere);

  function ruleaza(actiune: () => Promise<{ eroare?: string }>) {
    startTransition(async () => {
      setEroare(null);
      const rezultat = await actiune();
      if (rezultat.eroare) setEroare(rezultat.eroare);
    });
  }

  return (
    <article className="rounded-card border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[15px] font-semibold text-ink">
            {cerere.nume ?? "Client fără nume"}
          </p>
          <p className="truncate text-[12.5px] text-ink-faint">{cerere.email ?? "—"}</p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-[11.5px] font-medium ${status.clasa}`}>
          {status.text}
        </span>
      </div>

      {cerere.motiv ? (
        <p className="mt-3 rounded-field bg-muted px-3 py-2 text-[13px] italic leading-[19px] text-ink-soft">
          „{cerere.motiv}"
        </p>
      ) : null}

      {cerere.conturi.length > 0 ? (
        <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-[12.5px]">
          {cerere.conturi.map((cont, indice) => (
            <div key={`${cont.nume}-${indice}`} className="flex items-center gap-1.5">
              <dt className="text-ink-faint">{cont.nume ?? "Cont"}</dt>
              <dd
                className={`tabular font-medium ${
                  Number(cont.sold) === 0 ? "text-ink-faint" : "text-ink"
                }`}
              >
                {cont.sold} {cont.valuta}
              </dd>
              {cont.blocat ? (
                <span className="rounded-full bg-danger/10 px-1.5 py-0.5 text-[10.5px] font-medium text-danger">
                  blocat
                </span>
              ) : null}
            </div>
          ))}
        </dl>
      ) : null}

      {cerere.motiv_refuz ? (
        <p className="mt-3 text-[12.5px] leading-[18px] text-ink-faint">
          Motiv refuz: {cerere.motiv_refuz}
        </p>
      ) : null}

      {eroare ? (
        <div className="mt-3">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      {cerere.status === "in_asteptare" ? (
        <div className="mt-4 flex flex-col gap-3">
          <Camp
            eticheta="Motiv (doar la respingere)"
            value={motiv}
            onChange={(e) => setMotiv(e.target.value)}
            maxLength={500}
            placeholder="Îl vede clientul, în notificare"
          />
          <div className="flex flex-wrap gap-2">
            <Button
              marime="sm"
              loading={seLucreaza}
              onClick={() => ruleaza(() => decideCerereStergere(cerere.id, true))}
            >
              Aprobă și consolidează
            </Button>
            <Button
              varianta="secondary"
              marime="sm"
              loading={seLucreaza}
              onClick={() => ruleaza(() => decideCerereStergere(cerere.id, false, motiv))}
            >
              Respinge
            </Button>
          </div>
        </div>
      ) : null}

      {cerere.status === "aprobata" ? (
        <div className="mt-4 flex flex-col gap-2">
          {blocaje.length > 0 ? (
            <div className="flex items-start gap-2 rounded-field bg-warning/10 px-3 py-2.5 text-[12.5px] leading-[18px] text-warning">
              <TriangleAlert size={14} strokeWidth={2} aria-hidden className="mt-0.5 shrink-0" />
              <span>
                Nu se poate șterge încă: {blocaje.join(" ")}
              </span>
            </div>
          ) : null}

          <div>
            <Button
              varianta="danger"
              marime="sm"
              disabled={!poate}
              loading={seLucreaza}
              iconaStanga={
                !seLucreaza ? <Trash2 size={16} strokeWidth={1.75} aria-hidden /> : undefined
              }
              onClick={() => ruleaza(() => stergeClientul(cerere.id))}
            >
              Șterge clientul definitiv
            </Button>
          </div>
        </div>
      ) : null}
    </article>
  );
}
