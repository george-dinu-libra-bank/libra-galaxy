"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Comutator } from "@/components/ui/comutator";
import { Drawer, DrawerClose, DrawerContent } from "@/components/ui/drawer";
import { seteazaDrepturiMembru } from "@/lib/actions/grupuri";
import type { MembruCuDrepturi } from "@/lib/data/grupuri";
import { formateazaSuma } from "@/lib/utils";

/**
 * Drepturile unui membru asupra soldului comun, asa cum le vede creatorul:
 * daca poate scoate bani din grup si, daca da, cat in total intr-o luna
 * calendaristica.
 *
 * Plafonul lasat gol inseamna „fara plafon", nu zero — la fel ca la limita
 * zilnica a unui card (0031_card_tip_limite.sql). Cat a cheltuit deja membrul
 * luna asta se arata sub camp, fiindca fara cifra aia un plafon nou e greu de
 * ales: 500 de lei pot fi generosi sau deja depasiti.
 *
 * Se monteaza cu `key={membru.idUser}` (vezi ListaMembriGrup), deci starea
 * porneste de fiecare data de la drepturile reale ale membrului deschis.
 *
 * Bariera reala e seteaza_drepturi_membru_grup (0053_drepturi_grup.sql), care
 * refuza pe oricine nu e creatorul; drawerul asta e doar forma ei omeneasca.
 */
export function DrepturiMembruDrawer({
  idGrup,
  membru,
  deschis,
  onOpenChange,
}: {
  idGrup: number;
  membru: MembruCuDrepturi;
  deschis: boolean;
  onOpenChange: (deschis: boolean) => void;
}) {
  const router = useRouter();
  const [poateCheltui, setPoateCheltui] = useState(membru.poateCheltui);
  const [limita, setLimita] = useState(
    membru.limitaLunara == null ? "" : String(membru.limitaLunara),
  );
  const [eroare, setEroare] = useState<string | null>(null);
  const [seSalveaza, startTransition] = useTransition();

  const limitaNumerica = limita.trim() ? Number(limita.replace(",", ".")) : null;
  const limitaValida =
    limitaNumerica === null || (Number.isFinite(limitaNumerica) && limitaNumerica > 0);

  function salveaza() {
    if (poateCheltui && !limitaValida) {
      setEroare("Plafonul lunar trebuie să fie un număr mai mare decât 0.");
      return;
    }

    setEroare(null);

    startTransition(async () => {
      const rezultat = await seteazaDrepturiMembru({
        idGrup,
        idMembru: membru.idUser,
        poateCheltui,
        limitaLunara: poateCheltui ? limitaNumerica : null,
      });

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      onOpenChange(false);
      router.refresh();
    });
  }

  return (
    <Drawer open={deschis} onOpenChange={onOpenChange}>
      <DrawerContent
        title={`Drepturile lui ${membru.nume}`}
        description="Ce poate face cu soldul comun al grupului."
        footer={
          <div className="flex flex-col gap-2">
            <Button className="w-full" loading={seSalveaza} onClick={salveaza}>
              Salvează drepturile
            </Button>
            <DrawerClose asChild>
              <Button varianta="ghost" className="w-full">
                Renunță
              </Button>
            </DrawerClose>
          </div>
        }
      >
        <div className="flex flex-col gap-4">
          {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

          <div className="flex items-center gap-4 rounded-field border border-line bg-surface px-4 py-3">
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-medium text-ink">Poate cheltui din grup</p>
              <p className="mt-0.5 text-[12.5px] leading-[18px] text-ink-faint">
                Oprit, poate în continuare să pună bani în soldul comun — doar să scoată nu
                mai poate.
              </p>
            </div>

            <Comutator
              activ={poateCheltui}
              onChange={() => {
                setEroare(null);
                setPoateCheltui((valoare) => !valoare);
              }}
              eticheta={`Permite-i lui ${membru.nume} să cheltuiască din grup`}
            />
          </div>

          {poateCheltui ? (
            <div className="flex flex-col gap-1.5">
              <Camp
                eticheta="Plafon lunar (RON)"
                inputMode="decimal"
                placeholder="Fără plafon"
                value={limita}
                onChange={(eveniment) => {
                  setEroare(null);
                  setLimita(eveniment.target.value);
                }}
                ajutor="Lasă gol pentru „fără plafon”. Se resetează la începutul fiecărei luni."
              />

              <p className="tabular text-[12.5px] leading-[18px] text-ink-faint">
                Cheltuit luna aceasta: {formateazaSuma(membru.cheltuitLuna)}
                {limitaNumerica !== null && limitaValida
                  ? ` din ${formateazaSuma(limitaNumerica)}`
                  : ""}
              </p>

              {limitaNumerica !== null && limitaValida && membru.cheltuitLuna > limitaNumerica ? (
                <Banda ton="info">
                  A scos deja mai mult decât plafonul pe care îl pui. Nu i se cer banii înapoi,
                  dar nu va mai putea scoate nimic din grup până luna viitoare.
                </Banda>
              ) : null}
            </div>
          ) : null}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
