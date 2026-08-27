"use client";

import { ArrowRight, RotateCcw, TriangleAlert } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import {
  decideInchidereaContului,
  redeschideContul,
} from "@/lib/actions/admin-inchideri";
import {
  destinatiaImplicita,
  motiveleInchiderii,
  sePoateAproba,
  type CerereInchidere,
} from "@/lib/tipuri-admin";
import { etichetaStare } from "@/lib/stari-cerere";

/**
 * Cererile de inchidere a unui CONT BANCAR, pentru analist.
 *
 * Alta coada decat `cereri-stergere.tsx`, si se confunda usor: acolo pleaca omul
 * din banca, aici se inchide un singur cont si omul ramane client.
 *
 * Decizia se ia intr-un singur pas, spre deosebire de stergerea clientului:
 * aprobarea muta banii, inchide cardurile si inchide contul, toate in aceeasi
 * tranzactie (`public.inchide_cont_bancar`, 0040). Nu exista stare intermediara
 * din care cineva sa uite sa iasa — de-aia nu e nevoie de al doilea buton.
 *
 * Analistul alege destinatia banilor. Porneste de la propunerea clientului, dar
 * o poate schimba: „nimeni nu muta banii cuiva fara sa-l fi intrebat" nu inseamna
 * ca propunerea e obligatorie, ci ca e punctul de plecare.
 */

export function CereriInchidere({ cereri }: { cereri: CerereInchidere[] }) {
  if (cereri.length === 0) return null;

  return (
    <section className="mt-10">
      <h2 className="text-lg font-semibold text-ink">Cereri de închidere a unui cont bancar</h2>
      <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
        Aprobarea mută banii în contul ales, închide cardurile legate și închide contul —
        totul într-o singură operațiune. Contul rămâne în istoric cu numele lui.
      </p>

      <div className="mt-4 flex flex-col gap-3">
        {cereri.map((cerere) => (
          <Cerere key={cerere.id} cerere={cerere} />
        ))}
      </div>
    </section>
  );
}

function Cerere({ cerere }: { cerere: CerereInchidere }) {
  const implicita = destinatiaImplicita(cerere);
  const [destinatia, setDestinatia] = useState<string | null>(implicita?.id ?? null);
  const [motiv, setMotiv] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seLucreaza, startTransition] = useTransition();

  const stare = etichetaStare(cerere.status);
  const blocaje = motiveleInchiderii(cerere);
  const poate = sePoateAproba(cerere);
  const cont = cerere.cont;
  const areBani = cont ? Number(cont.sold) > 0 : false;
  const propusaDeClient = cerere.id_cont_destinatie === destinatia && destinatia !== null;

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
        <span className={`rounded-full px-2.5 py-1 text-[11.5px] font-medium ${stare.clasa}`}>
          {stare.text}
        </span>
      </div>

      {/* Contul care se inchide, cu soldul lui — prima informatie de care are
          nevoie analistul, nu una pe care sa o caute intr-o lista. */}
      {cont ? (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-field bg-muted px-3 py-2.5">
          <span className="text-[13px] font-medium text-ink">{cont.nume ?? "Cont"}</span>
          <span className="tabular text-[13px] text-ink">
            {cont.sold} {cont.valuta}
          </span>
          {cont.este_principal ? (
            <span className="rounded-full bg-danger/10 px-1.5 py-0.5 text-[10.5px] font-medium text-danger">
              cont principal
            </span>
          ) : null}
          {cont.blocat ? (
            <span className="rounded-full bg-danger/10 px-1.5 py-0.5 text-[10.5px] font-medium text-danger">
              blocat
            </span>
          ) : null}
          {cont.inchis ? (
            <span className="rounded-full bg-ink-faint/15 px-1.5 py-0.5 text-[10.5px] font-medium text-ink-faint">
              închis
            </span>
          ) : null}
        </div>
      ) : null}

      {cerere.motiv ? (
        <p className="mt-3 rounded-field bg-muted px-3 py-2 text-[13px] italic leading-[19px] text-ink-soft">
          „{cerere.motiv}”
        </p>
      ) : null}

      {cerere.carduri.length > 0 ? (
        <p className="mt-3 text-[12.5px] leading-[18px] text-ink-faint">
          Se închid odată cu contul:{" "}
          {cerere.carduri
            .map((card) => `${card.tip ?? "Card"} ••••${card.ultimele4}`)
            .join(", ")}
        </p>
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
          {blocaje.length > 0 ? (
            <div className="flex items-start gap-2 rounded-field bg-warning/10 px-3 py-2.5 text-[12.5px] leading-[18px] text-warning">
              <TriangleAlert size={14} strokeWidth={2} aria-hidden className="mt-0.5 shrink-0" />
              <span>Nu se poate aproba: {blocaje.join(" ")}</span>
            </div>
          ) : null}

          {areBani && cerere.destinatii.length > 0 ? (
            <div>
              <p className="text-[13px] font-medium text-ink">
                Unde se duc {cont?.sold} {cont?.valuta}
              </p>
              <p className="mt-0.5 text-[12.5px] leading-[17px] text-ink-faint">
                {propusaDeClient
                  ? "Contul propus de client. Poți alege altul."
                  : "Ai schimbat propunerea clientului."}
              </p>

              <div className="mt-2 flex flex-col gap-1.5">
                {cerere.destinatii.map((tinta) => (
                  <button
                    key={tinta.id}
                    type="button"
                    onClick={() => setDestinatia(tinta.id)}
                    className={`flex items-center gap-2 rounded-field border px-3 py-2 text-left text-[13px] transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25 ${
                      destinatia === tinta.id
                        ? "border-primary-500 bg-primary-50"
                        : "border-line hover:bg-muted"
                    }`}
                  >
                    <span className="min-w-0 flex-1 truncate font-medium text-ink">
                      {tinta.nume}
                      {tinta.este_principal ? (
                        <span className="font-normal text-ink-faint"> · principal</span>
                      ) : null}
                      {tinta.id === cerere.id_cont_destinatie ? (
                        <span className="font-normal text-ink-faint"> · cerut de client</span>
                      ) : null}
                    </span>
                    <span className="tabular shrink-0 text-ink-faint">
                      {tinta.sold} {tinta.valuta}
                    </span>
                  </button>
                ))}
              </div>

              {cont && destinatia ? (
                <ConversieAvertisment
                  valutaSursa={cont.valuta}
                  valutaTinta={
                    cerere.destinatii.find((t) => t.id === destinatia)?.valuta ?? null
                  }
                />
              ) : null}
            </div>
          ) : null}

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
              disabled={!poate}
              loading={seLucreaza}
              iconaStanga={
                !seLucreaza ? <ArrowRight size={16} strokeWidth={1.75} aria-hidden /> : undefined
              }
              onClick={() =>
                ruleaza(() =>
                  decideInchidereaContului(cerere.id, true, { idContDestinatie: destinatia }),
                )
              }
            >
              {areBani ? "Aprobă și mută banii" : "Aprobă și închide contul"}
            </Button>
            <Button
              varianta="secondary"
              marime="sm"
              loading={seLucreaza}
              onClick={() =>
                ruleaza(() => decideInchidereaContului(cerere.id, false, { motiv }))
              }
            >
              Respinge
            </Button>
          </div>
        </div>
      ) : null}

      {/* „Inchis, nu sters" nu inseamna nimic daca nimeni nu poate da inapoi.
          Banii NU se intorc singuri — scrie si in notificarea catre client.

          Butonul se uita la CONT (`cont.inchis`, adica `conturi_bancare.inchis_la`),
          nu la statusul cererii: cererea ramane „aprobata" pentru totdeauna, dar
          contul poate fi redeschis intre timp — de altcineva, sau de tine. Cand cele
          doua nu mai spun acelasi lucru, adevarul e al contului. */}
      {cerere.status === "aprobata" && cont ? (
        cont.inchis ? (
          <div className="mt-4">
            <Button
              varianta="secondary"
              marime="sm"
              loading={seLucreaza}
              iconaStanga={
                !seLucreaza ? <RotateCcw size={15} strokeWidth={1.75} aria-hidden /> : undefined
              }
              onClick={() => ruleaza(() => redeschideContul(cerere.id_cont))}
            >
              Redeschide contul
            </Button>
            <p className="mt-1.5 text-[12px] leading-[17px] text-ink-faint">
              Banii mutați la închidere nu se întorc automat — se transferă înapoi separat.
            </p>
          </div>
        ) : (
          <p className="mt-4 text-[12.5px] leading-[18px] text-ink-faint">
            Contul a fost redeschis între timp.
          </p>
        )
      ) : null}
    </article>
  );
}

/** Conturile in valute diferite: suma se converteste, si asta trebuie spus. */
function ConversieAvertisment({
  valutaSursa,
  valutaTinta,
}: {
  valutaSursa: string | null;
  valutaTinta: string | null;
}) {
  if (!valutaSursa || !valutaTinta || valutaSursa === valutaTinta) return null;

  return (
    <p className="mt-2 text-[12.5px] leading-[18px] text-ink-faint">
      Conturile sunt în valute diferite; suma se convertește din {valutaSursa} în{" "}
      {valutaTinta} la cursul BNR de azi.
    </p>
  );
}
