"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { MessagesSquare } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { deschideInvestigatie } from "@/lib/actions/investigatii";
import { ETICHETE_TIP, type Constatare } from "@/lib/tipuri-admin";

/**
 * Deschide firul de discuție cu clientul, de pe ecranul contului semnalat.
 *
 * Stă lângă butoanele de blocare, dar nu face parte din ele: se poate deschide
 * o investigație fără să blochezi nimic, și se poate bloca un cont fără să
 * deschizi una. Sunt două decizii, cu două apăsări.
 *
 * Plățile semnalate pleacă odată cu investigația, nu se adaugă după. Din ele
 * scrie redactorul mesajul — fără sume și date concrete, ar produce un text
 * vag, iar clientul n-ar avea la ce să se raporteze când răspunde.
 */
export function DeschideInvestigatie({
  idUtilizator,
  nume,
  gravitate,
  numarSemnalari,
  constatari,
}: {
  idUtilizator: string;
  nume: string;
  gravitate: number;
  numarSemnalari: number;
  constatari: Constatare[];
}) {
  const router = useRouter();
  const [seLucreaza, porneste] = useTransition();
  const [eroare, setEroare] = useState<string | null>(null);

  const motiv =
    `Plăți semnalate pe contul lui ${nume}: ${numarSemnalari} ` +
    `${numarSemnalari === 1 ? "semnalare" : "semnalări"}, gravitate ${gravitate} din 100.`;

  function deschide() {
    setEroare(null);
    porneste(async () => {
      const { date, eroare: err } = await deschideInvestigatie(
        idUtilizator,
        motiv,
        gravitate,
        numarSemnalari,
        // Motivul fiecărei plăți e explicația detectorului, în cuvintele lui.
        // Ajunge în dosar lângă plată și în faptele pe care le vede redactorul.
        constatari.map((c) => ({
          id_tranzactie: c.id_tranzactie,
          motiv: ETICHETE_TIP[c.tip] ?? c.tip,
        })),
      );
      if (err) {
        setEroare(err);
        return;
      }
      // Dacă omul avea deja o investigație deschisă, backendul o întoarce pe
      // aceea — și atunci ajungem tot acolo, ceea ce e ce trebuie.
      if (date) router.push(`/admin/investigatii/${date.id}`);
    });
  }

  return (
    <section className="flex flex-col gap-3 rounded-card border border-line bg-surface p-5">
      <div>
        <h2 className="text-[15px] font-semibold text-ink">Întreabă clientul</h2>
        <p className="mt-1 max-w-2xl text-[13px] leading-[19px] text-ink-soft">
          Deschide un fir de discuție prin care îl întrebi direct dacă el a făcut plățile.
          Textul îl propune un agent, dar îl citești și îl trimiți tu.
          {constatari.length > 0 ? (
            <>
              {" "}
              Cele {constatari.length}{" "}
              {constatari.length === 1 ? "plată semnalată merge" : "plăți semnalate merg"} în
              dosar.
            </>
          ) : null}
        </p>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      <Button
        varianta="secondary"
        marime="sm"
        className="w-fit"
        loading={seLucreaza}
        onClick={deschide}
        iconaStanga={<MessagesSquare size={16} strokeWidth={1.75} aria-hidden />}
      >
        Deschide investigație
      </Button>
    </section>
  );
}
