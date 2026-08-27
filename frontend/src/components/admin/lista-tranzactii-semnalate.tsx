"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { ArrowRight, ShieldCheck, Users } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { decideTranzactieSemnalata } from "@/lib/actions/admin-securitate";
import type { TranzactieSemnalata } from "@/lib/data/admin-securitate";
import { formateazaSuma } from "@/lib/utils";

type Decizie = "accepta" | "anuleaza";

/**
 * Coada transferurilor oprite de scanerul de cuvinte.
 *
 * Fiecare rand e o suma care sta pe loc: expeditorul a fost debitat, iar
 * beneficiarul n-a primit nimic. De aceea nu exista „mai vedem" — cele doua
 * butoane sunt singurele iesiri, si amandoua trec printr-o confirmare.
 */
export function ListaTranzactiiSemnalate({
  tranzactii,
}: {
  tranzactii: TranzactieSemnalata[];
}) {
  const router = useRouter();
  const [deDecis, setDeDecis] = useState<{
    tranzactie: TranzactieSemnalata;
    decizie: Decizie;
  } | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  function confirma() {
    if (!deDecis) return;
    setEroare(null);

    startTransition(async () => {
      const rezultat = await decideTranzactieSemnalata(
        deDecis.tranzactie.id,
        deDecis.decizie,
      );

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      setDeDecis(null);
      router.refresh();
    });
  }

  if (tranzactii.length === 0) {
    return (
      <section className="flex flex-col items-center gap-3 rounded-card border border-dashed border-line bg-surface p-10 text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-full bg-success/10">
          <ShieldCheck size={26} strokeWidth={1.75} aria-hidden className="text-success" />
        </span>
        <p className="text-[15px] font-semibold text-ink">Niciun transfer oprit</p>
        <p className="max-w-sm text-[13px] leading-[19px] text-ink-faint">
          Nicio descriere nu s-a potrivit cu lista de cuvinte sensibile.
        </p>
      </section>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-[13px] text-ink-faint">
        {tranzactii.length}{" "}
        {tranzactii.length === 1 ? "transfer așteaptă" : "transferuri așteaptă"} o decizie.
      </p>

      {tranzactii.map((tranzactie) => (
        <CardSemnalare
          key={tranzactie.id}
          tranzactie={tranzactie}
          onDecide={(decizie) => {
            setEroare(null);
            setDeDecis({ tranzactie, decizie });
          }}
        />
      ))}

      <Drawer
        open={deDecis !== null}
        onOpenChange={(deschis) => {
          if (!deschis && !seTrimite) {
            setDeDecis(null);
            setEroare(null);
          }
        }}
        dismissible={!seTrimite}
      >
        <DrawerContent
          title={deDecis?.decizie === "accepta" ? "Eliberezi banii?" : "Anulezi transferul?"}
          description={
            deDecis
              ? deDecis.decizie === "accepta"
                ? `${formateazaSuma(deDecis.tranzactie.suma, deDecis.tranzactie.valuta)} ajung acum la ${deDecis.tranzactie.beneficiar?.nume ?? "beneficiar"}. Decizia nu mai poate fi întoarsă din aplicație.`
                : `${formateazaSuma(deDecis.tranzactie.suma, deDecis.tranzactie.valuta)} se întorc acolo de unde au plecat, iar ${deDecis.tranzactie.expeditor?.nume ?? "expeditorul"} primește o notificare.`
              : ""
          }
          cuInchidere={!seTrimite}
          footer={
            <Button
              varianta={deDecis?.decizie === "accepta" ? "primary" : "danger"}
              className="w-full"
              loading={seTrimite}
              onClick={confirma}
            >
              {deDecis?.decizie === "accepta" ? "Da, eliberează banii" : "Da, anulează transferul"}
            </Button>
          }
        >
          {eroare ? (
            <div className="mb-4">
              <Banda ton="eroare">{eroare}</Banda>
            </div>
          ) : null}

          {deDecis?.tranzactie.descriere ? (
            <p className="text-[13px] leading-[19px] text-ink-soft">
              Descrierea transferului: „{deDecis.tranzactie.descriere}"
            </p>
          ) : null}
        </DrawerContent>
      </Drawer>
    </div>
  );
}

function CardSemnalare({
  tranzactie,
  onDecide,
}: {
  tranzactie: TranzactieSemnalata;
  onDecide: (decizie: Decizie) => void;
}) {
  const cuvinte = (tranzactie.motiv ?? "")
    .split(", ")
    .map((cuvant) => cuvant.trim())
    .filter(Boolean);

  return (
    <article className="flex flex-col gap-4 rounded-card border border-line bg-surface p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 text-[15px] text-ink">
            <span className="font-semibold">
              {tranzactie.expeditor?.nume ?? "Cont șters"}
            </span>
            <ArrowRight size={15} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
            <span className="font-semibold">
              {tranzactie.beneficiar?.nume ?? "Cont șters"}
            </span>
          </p>
          <p className="mt-1 text-[12.5px] text-ink-faint">
            {tranzactie.grup ? (
              <span className="inline-flex items-center gap-1">
                <Users size={13} strokeWidth={1.75} aria-hidden />
                din grupul {tranzactie.grup.nume} ·{" "}
              </span>
            ) : null}
            {tranzactie.ibanBeneficiar ? `${tranzactie.ibanBeneficiar} · ` : ""}
            {new Date(tranzactie.creatLa).toLocaleString("ro-RO", {
              day: "numeric",
              month: "long",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        </div>

        <span className="tabular shrink-0 text-[17px] font-bold text-ink">
          {formateazaSuma(tranzactie.suma, tranzactie.valuta)}
        </span>
      </div>

      <div className="rounded-field bg-muted px-4 py-3">
        <p className="text-[13px] leading-[19px] text-ink-soft">
          {tranzactie.descriere ? `„${tranzactie.descriere}"` : "Fără descriere."}
        </p>
        {cuvinte.length > 0 ? (
          <p className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="text-[12px] text-ink-faint">Potrivit cu:</span>
            {cuvinte.map((cuvant) => (
              <span
                key={cuvant}
                className="rounded-full bg-warning/10 px-2.5 py-0.5 text-[12px] font-medium text-warning"
              >
                {cuvant}
              </span>
            ))}
          </p>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button marime="sm" onClick={() => onDecide("accepta")}>
          Eliberează banii
        </Button>
        <Button varianta="danger" marime="sm" onClick={() => onDecide("anuleaza")}>
          Anulează transferul
        </Button>
      </div>
    </article>
  );
}
