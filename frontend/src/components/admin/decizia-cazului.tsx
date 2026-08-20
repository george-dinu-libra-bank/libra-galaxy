"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Check, X } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { decideVerificare } from "@/lib/actions/admin-verificari";

type Decizie = "verified" | "rejected";

/**
 * Aproba sau respinge.
 *
 * Amandoua trec printr-o confirmare: de o parte si de alta a butonului sta
 * contul unui om, care fie capata acces la bani, fie ramane blocat. O apasare
 * din greseala nu trebuie sa fie de ajuns.
 */
export function DeciziaCazului({
  verificationId,
  nume,
}: {
  verificationId: string;
  nume: string;
}) {
  const router = useRouter();
  const [decizie, setDecizie] = useState<Decizie | null>(null);
  const [nota, setNota] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  function confirma() {
    if (!decizie) return;
    setEroare(null);

    startTransition(async () => {
      const rezultat = await decideVerificare(verificationId, decizie, nota);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setDecizie(null);
      setNota("");
      router.push("/admin");
      router.refresh();
    });
  }

  const aproba = decizie === "verified";

  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold text-ink">Decizia ta</h2>
      <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
        Aprobarea deblochează contul. Respingerea îl lasă blocat până la o nouă încercare.
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
          onClick={() => setDecizie("verified")}
        >
          Aprobă contul
        </Button>
        <Button
          varianta="danger"
          className="flex-1"
          iconaStanga={<X size={18} strokeWidth={1.75} aria-hidden />}
          onClick={() => setDecizie("rejected")}
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
          title={aproba ? "Aprobi contul?" : "Respingi verificarea?"}
          description={
            aproba
              ? `${nume} va putea folosi contul normal.`
              : `${nume} rămâne cu contul blocat până trimite alte poze.`
          }
          cuInchidere={!seTrimite}
          footer={
            <Button
              varianta={aproba ? "primary" : "danger"}
              className="w-full"
              loading={seTrimite}
              onClick={confirma}
            >
              {aproba ? "Da, aprobă contul" : "Da, respinge"}
            </Button>
          }
        >
          <Camp
            eticheta="Notă (opțional)"
            value={nota}
            onChange={(e) => setNota(e.target.value)}
            placeholder={aproba ? "Ex. poze clare, date corecte" : "Ex. fața nu se potrivește"}
            maxLength={2000}
            ajutor="Rămâne în dosarul cazului, alături de numele tău."
            autoComplete="off"
          />
        </DrawerContent>
      </Drawer>
    </section>
  );
}
