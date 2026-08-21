"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Check, X } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { decideCerereCredit } from "@/lib/actions/admin-credite";
import { lei } from "@/lib/tipuri-admin";

/**
 * Decizia omului peste o cerere din zona gri.
 *
 * Amandoua trec printr-o confirmare: de o parte si de alta a butonului stau
 * banii cuiva. O apasare din greseala nu trebuie sa fie de ajuns.
 *
 * Formularea din drawer spune explicit ce se intampla mai departe, fiindca
 * lucrul cel mai usor de inteles gresit e ca „aproba" ar da banii. Nu da:
 * genereaza oferta, iar clientul o semneaza el.
 */
export function DeciziaCererii({
  idCerere,
  nume,
  suma,
  luni,
}: {
  idCerere: string;
  nume: string;
  suma: string;
  luni: number;
}) {
  const router = useRouter();
  const [decizie, setDecizie] = useState<"aproba" | "respinge" | null>(null);
  const [nota, setNota] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const aproba = decizie === "aproba";

  function confirma() {
    if (!decizie) return;
    setEroare(null);

    startTransition(async () => {
      const rezultat = await decideCerereCredit(idCerere, aproba, nota);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setDecizie(null);
      setNota("");
      router.push("/admin/credite");
      router.refresh();
    });
  }

  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold text-ink">Decizia ta</h2>
      <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
        Aprobarea nu acordă creditul — generează oferta, pe care clientul o semnează din
        aplicație. Respingerea închide dosarul.
      </p>

      {eroare ? (
        <div className="mt-4">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      <div className="mt-4 flex flex-col gap-3 sm:flex-row">
        <Button
          className="flex-1"
          iconaStanga={<Check size={18} strokeWidth={1.75} aria-hidden />}
          onClick={() => setDecizie("aproba")}
        >
          Aprobă cererea
        </Button>
        <Button
          varianta="danger"
          className="flex-1"
          iconaStanga={<X size={18} strokeWidth={1.75} aria-hidden />}
          onClick={() => setDecizie("respinge")}
        >
          Respinge
        </Button>
      </div>

      <Drawer
        open={decizie !== null}
        onOpenChange={(deschis) => {
          if (!deschis && !seTrimite) {
            setDecizie(null);
            setEroare(null);
          }
        }}
        dismissible={!seTrimite}
      >
        <DrawerContent
          title={aproba ? "Aprobi cererea?" : "Respingi cererea?"}
          description={
            aproba
              ? `${nume} va primi o ofertă de ${lei(suma)} RON pe ${luni} luni, valabilă 7 zile.`
              : `${nume} află că cererea nu a fost aprobată și poate depune alta oricând.`
          }
          cuInchidere={!seTrimite}
          footer={
            <Button
              varianta={aproba ? "primary" : "danger"}
              className="w-full"
              loading={seTrimite}
              onClick={confirma}
            >
              {aproba ? "Da, trimite oferta" : "Da, respinge"}
            </Button>
          }
        >
          <Camp
            eticheta="Motivarea deciziei (opțional)"
            value={nota}
            onChange={(eveniment) => setNota(eveniment.target.value)}
            maxLength={500}
            ajutor="Ajunge în explicația pe care o citește clientul, alături de punctajul automat."
            autoComplete="off"
          />
        </DrawerContent>
      </Drawer>
    </section>
  );
}
