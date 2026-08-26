"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Lock, Unlock } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { decideCont } from "@/lib/actions/admin-analiza";

/**
 * Blocarea si deblocarea conturilor, dintr-un rand din lista de conturi.
 *
 * Acelasi drum ca in raportul unui cont: aceeasi actiune de server, aceeasi
 * confirmare, aceeasi observatie obligatorie, si intra in acelasi istoric. Un
 * administrator nu trebuie sa aiba doua feluri de a bloca pe cineva, cu doua
 * urme diferite in urma lor.
 *
 * Blocarea opreste tot ce pleaca din conturile omului: si platile cu cardul, si
 * transferurile. Bariera e in baza de date (0030), deci tine si daca cineva
 * ocoleste aplicatia.
 */
export function BlocareCont({
  idUtilizator,
  nume,
  total,
  blocate,
}: {
  idUtilizator: string;
  nume: string;
  total: number;
  blocate: number;
}) {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [observatie, setObservatie] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const esteBlocat = blocate > 0;
  const observatieLipsa = observatie.trim().length === 0;

  function confirma() {
    if (observatieLipsa) return;
    setEroare(null);

    startTransition(async () => {
      const rezultat = await decideCont(
        idUtilizator,
        esteBlocat ? "deblocat" : "frauda",
        observatie,
        { aplicaBlocarea: !esteBlocat },
      );
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setDeschis(false);
      setObservatie("");
      router.refresh();
    });
  }

  if (total === 0) {
    return <span className="shrink-0 text-[12px] text-ink-faint">Fără conturi</span>;
  }

  return (
    <>
      <Button
        varianta={esteBlocat ? "secondary" : "danger"}
        marime="sm"
        className="shrink-0"
        iconaStanga={
          esteBlocat ? (
            <Unlock size={16} strokeWidth={1.75} aria-hidden />
          ) : (
            <Lock size={16} strokeWidth={1.75} aria-hidden />
          )
        }
        onClick={() => setDeschis(true)}
      >
        {esteBlocat ? "Deblochează" : "Blochează"}
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
          title={esteBlocat ? "Deblochezi conturile?" : "Blochezi conturile acestui client?"}
          description={
            esteBlocat
              ? `${nume} își va putea folosi din nou conturile și va fi anunțat.`
              : `Conturile lui ${nume} vor fi blocate imediat: nu mai pot pleca bani nici prin card, nici prin transfer. Banii care vin către el intră normal. Va primi o notificare cu motivul.`
          }
          cuInchidere={!seTrimite}
          footer={
            <Button
              varianta={esteBlocat ? "primary" : "danger"}
              className="w-full"
              loading={seTrimite}
              disabled={observatieLipsa}
              onClick={confirma}
            >
              {esteBlocat ? "Da, deblochează" : "Da, blochează conturile"}
            </Button>
          }
        >
          {eroare ? (
            <div className="mb-4">
              <Banda ton="eroare">{eroare}</Banda>
            </div>
          ) : null}

          <Camp
            eticheta="Observație"
            value={observatie}
            onChange={(e) => setObservatie(e.target.value)}
            placeholder={
              esteBlocat
                ? "Ex. clientul a confirmat plățile, documente verificate"
                : "Ex. blocat preventiv până la clarificarea plăților"
            }
            maxLength={2000}
            ajutor="Rămâne în istoricul contului și ajunge la client, în notificare."
            autoComplete="off"
          />
        </DrawerContent>
      </Drawer>
    </>
  );
}
