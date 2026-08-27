"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Scale } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { instituiePoprire } from "@/lib/actions/admin-popriri";

/**
 * Instituirea unei popriri, dintr-un rand din lista de conturi.
 *
 * Sta langa `BlocareCont` fiindca amandoua pornesc de la acelasi rand, dar NU
 * sunt acelasi lucru, si tocmai de-aia sunt doua butoane si nu unul cu optiuni:
 *
 *   blocarea (0030)  — opreste TOT ce pleaca din conturile omului, la nesfarsit,
 *                      pana o ridica banca. Unealta pentru frauda.
 *   poprirea (0047)  — indisponibilizeaza o SUMA, pe toate conturile lui, si se
 *                      stinge singura cand suma s-a adunat. Unealta pentru un
 *                      titlu executoriu.
 *
 * Pot fi si amandoua deodata pe acelasi om.
 *
 * Nu exista confirmare in doi pasi ca la blocare: poprirea nu e ireversibila —
 * se ridica dintr-un buton, iar banii nu pleaca nicaieri pana la incasare.
 */
export function PoprireCont({
  idUtilizator,
  nume,
  total,
}: {
  idUtilizator: string;
  nume: string;
  total: number;
}) {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [creditor, setCreditor] = useState("");
  const [dosar, setDosar] = useState("");
  const [suma, setSuma] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const sumaNumar = Number(suma.replace(",", "."));
  const gata = creditor.trim().length >= 2 && Number.isFinite(sumaNumar) && sumaNumar > 0;

  function confirma() {
    if (!gata) return;
    setEroare(null);

    startTransition(async () => {
      const rezultat = await instituiePoprire({
        idUtilizator,
        creditor,
        suma: sumaNumar,
        dosar,
      });
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setDeschis(false);
      setCreditor("");
      setDosar("");
      setSuma("");
      router.refresh();
    });
  }

  if (total === 0) return null;

  return (
    <>
      <Button
        varianta="secondary"
        marime="sm"
        className="shrink-0"
        iconaStanga={<Scale size={16} strokeWidth={1.75} aria-hidden />}
        onClick={() => setDeschis(true)}
      >
        Poprire
      </Button>

      <Drawer
        open={deschis}
        onOpenChange={(d) => {
          if (!d && !seTrimite) {
            setDeschis(false);
            setEroare(null);
          }
        }}
        dismissible={!seTrimite}
      >
        <DrawerContent
          title="Instituie o poprire"
          description={`Suma pe care o scrii mai jos devine indisponibilă pe toate conturile lui ${nume}. Restul banilor rămân ai lui, iar încasările intră normal. Va primi o notificare cu creditorul și dosarul.`}
          cuInchidere={!seTrimite}
          footer={
            <Button
              varianta="primary"
              className="w-full"
              loading={seTrimite}
              disabled={!gata}
              onClick={confirma}
            >
              Instituie poprirea
            </Button>
          }
        >
          {eroare ? (
            <div className="mb-4">
              <Banda ton="eroare">{eroare}</Banda>
            </div>
          ) : null}

          <div className="flex flex-col gap-4">
            <Camp
              eticheta="Creditor"
              value={creditor}
              onChange={(e) => setCreditor(e.target.value)}
              placeholder="Ex. ANAF — AJFP Cluj, BEJ Popescu"
              maxLength={200}
              ajutor="Ajunge în notificarea clientului: trebuie să știe de la cine să ceară lămuriri."
              autoComplete="off"
            />

            <Camp
              eticheta="Dosar de executare"
              value={dosar}
              onChange={(e) => setDosar(e.target.value)}
              placeholder="Ex. 123/2026"
              maxLength={100}
              ajutor="Opțional."
              autoComplete="off"
            />

            <Camp
              eticheta="Sumă (RON)"
              type="text"
              inputMode="decimal"
              value={suma}
              onChange={(e) => setSuma(e.target.value)}
              placeholder="Ex. 5000"
              ajutor="Dacă omul are mai puțin decât atât, tot ce are devine indisponibil, iar poprirea rămâne activă până se adună restul."
              autoComplete="off"
            />
          </div>
        </DrawerContent>
      </Drawer>
    </>
  );
}
