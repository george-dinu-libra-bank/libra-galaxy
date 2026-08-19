"use client";

import { useRouter } from "next/navigation";
import { Check, FileText, Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { depuneInGrup } from "@/lib/actions/grupuri";
import type { ContBancar } from "@/lib/data/conturi";
import { cn, formateazaSuma } from "@/lib/utils";

/**
 * Punerea de bani in soldul comun al grupului: din ce cont si cat.
 *
 * Verificarea fondurilor se face si aici (ca sa nu plece un request inutil), si
 * in public.core_banking_groups — a doua e cea care conteaza.
 */
export function DepuneInGrupDrawer({
  idGrup,
  conturi,
}: {
  idGrup: number;
  conturi: ContBancar[];
}) {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [idCont, setIdCont] = useState(conturi[0]?.id ?? "");
  const [suma, setSuma] = useState("");
  const [detalii, setDetalii] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const contAles = conturi.find((cont) => cont.id === idCont) ?? null;
  const sumaNumerica = Number(suma.replace(",", "."));
  const sumaValida = Boolean(suma) && !Number.isNaN(sumaNumerica) && sumaNumerica > 0;

  function trimite() {
    if (!contAles) {
      setEroare("Alege contul din care pui banii.");
      return;
    }

    if (!sumaValida) {
      setEroare("Introdu o sumă validă.");
      return;
    }

    if (sumaNumerica > contAles.sold) {
      setEroare("Nu ai fonduri suficiente în cont.");
      return;
    }

    setEroare(null);

    startTransition(async () => {
      const rezultat = await depuneInGrup({
        idGrup,
        idCont: contAles.id,
        suma: sumaNumerica,
        detalii,
      });

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      setDeschis(false);
      setSuma("");
      setDetalii("");
      router.refresh();
    });
  }

  return (
    <Drawer
      open={deschis}
      onOpenChange={(valoare) => {
        setDeschis(valoare);
        if (valoare) setEroare(null);
      }}
    >
      <DrawerTrigger
        aria-label="Pune bani în grup"
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white/20 text-white transition-[background-color,transform] duration-150 ease-soft hover:bg-white/30 active:scale-[0.96] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-white/40"
      >
        <Plus size={22} strokeWidth={2} aria-hidden />
      </DrawerTrigger>

      <DrawerContent
        title="Pune bani în grup"
        description="Banii ies din contul tău și intră în soldul comun."
        footer={
          <Button className="w-full" loading={seTrimite} onClick={trimite}>
            {sumaValida ? `Pune ${formateazaSuma(sumaNumerica)}` : "Pune banii"}
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

          {conturi.length === 0 ? (
            <p className="text-[15px] leading-[22px] text-ink-soft">
              Nu ai niciun cont din care să pui bani. Deschide unul din ecranul principal.
            </p>
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <span className="text-[13px] font-medium text-ink-soft">Din cont</span>

                <div className="flex flex-col gap-2">
                  {conturi.map((cont) => (
                    <button
                      key={cont.id}
                      type="button"
                      onClick={() => setIdCont(cont.id)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-field border px-4 py-3 text-left transition-colors duration-150 ease-soft",
                        "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                        cont.id === idCont
                          ? "border-primary-500 bg-primary-500/12"
                          : "border-line bg-surface hover:bg-muted",
                      )}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[15px] text-ink">{cont.nume}</span>
                        <span className="tabular block truncate text-[12.5px] text-ink-faint">
                          {cont.ibanMascat}
                        </span>
                      </span>

                      <span className="tabular shrink-0 text-[13px] font-medium text-ink">
                        {formateazaSuma(cont.sold)}
                      </span>

                      {cont.id === idCont ? (
                        <Check
                          size={18}
                          strokeWidth={1.75}
                          aria-hidden
                          className="shrink-0 text-primary-600"
                        />
                      ) : null}
                    </button>
                  ))}
                </div>
              </div>

              <Camp
                eticheta="Sumă (RON)"
                inputMode="decimal"
                placeholder="0,00"
                value={suma}
                onChange={(e) => setSuma(e.target.value.replace(/[^0-9,.]/g, ""))}
                ajutor={
                  contAles ? `Disponibil: ${formateazaSuma(contAles.sold)}` : undefined
                }
              />

              <Camp
                eticheta="Detalii (opțional)"
                icoana={FileText}
                placeholder="Ex. Partea mea din chirie"
                value={detalii}
                onChange={(e) => setDetalii(e.target.value)}
                maxLength={140}
              />
            </>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
