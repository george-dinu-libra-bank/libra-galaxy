"use client";

import { useMemo, useState } from "react";
import { Check, ChevronRight, Plus, Search, Star, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { ibanEsteValid } from "@/lib/iban";
import type { Beneficiar } from "@/lib/mock-data";
import { cn, formateazaIban } from "@/lib/utils";

function initiale(nume: string) {
  return nume
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((parte) => parte[0]?.toUpperCase())
    .join("");
}

export function AlegeBeneficiarDrawer({
  beneficiari,
  selectat,
  onSelect,
}: {
  beneficiari: Beneficiar[];
  selectat: Beneficiar | null;
  onSelect: (beneficiar: Beneficiar) => void;
}) {
  const [deschis, setDeschis] = useState(false);
  const [modNou, setModNou] = useState(false);
  const [cautare, setCautare] = useState("");
  const [numeNou, setNumeNou] = useState("");
  const [ibanNou, setIbanNou] = useState("");
  const [eroareNume, setEroareNume] = useState<string | null>(null);
  const [eroareIban, setEroareIban] = useState<string | null>(null);

  const filtrati = useMemo(() => {
    const q = cautare.trim().toLowerCase();
    if (!q) return beneficiari;
    return beneficiari.filter(
      (b) => b.nume.toLowerCase().includes(q) || b.iban.toLowerCase().includes(q.replace(/\s+/g, "")),
    );
  }, [beneficiari, cautare]);

  function reseteaza() {
    setModNou(false);
    setCautare("");
    setNumeNou("");
    setIbanNou("");
    setEroareNume(null);
    setEroareIban(null);
  }

  function alege(b: Beneficiar) {
    onSelect(b);
    setDeschis(false);
    reseteaza();
  }

  function adaugaSiContinua() {
    const iban = ibanNou.replace(/\s+/g, "").toUpperCase();
    setEroareNume(null);
    setEroareIban(null);

    if (numeNou.trim().length < 3) {
      setEroareNume("Introdu numele beneficiarului");
      return;
    }
    if (!ibanEsteValid(iban)) {
      setEroareIban("IBAN invalid");
      return;
    }
    alege({
      id: `nou-${Date.now()}`,
      nume: numeNou.trim(),
      iban,
      banca: "Cont extern",
      favorit: false,
    });
  }

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[13px] font-medium text-ink-soft">Către</span>

      <Drawer
        open={deschis}
        onOpenChange={(v) => {
          setDeschis(v);
          if (!v) reseteaza();
        }}
      >
        <DrawerTrigger className="flex h-[52px] w-full items-center gap-3 rounded-field border border-line bg-surface px-4 text-left transition-colors duration-150 ease-soft hover:border-primary-300 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/12">
          {selectat ? (
            <>
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 text-[12px] font-semibold text-primary-700">
                {initiale(selectat.nume)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] text-ink">{selectat.nume}</span>
                <span className="tabular block truncate text-[12.5px] text-ink-faint">
                  {formateazaIban(selectat.iban)}
                </span>
              </span>
            </>
          ) : (
            <>
              <User size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
              <span className="flex-1 text-[15px] text-ink-faint">Alege beneficiarul</span>
            </>
          )}
          <ChevronRight size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
        </DrawerTrigger>

        <DrawerContent
          title={modNou ? "Beneficiar nou" : "Alege beneficiarul"}
          description={
            modNou
              ? "Introdu datele contului catre care trimiti banii."
              : "Cauta in lista sau adauga un cont nou."
          }
          footer={
            modNou ? (
              <Button className="w-full" onClick={adaugaSiContinua}>
                Adauga si continua
              </Button>
            ) : undefined
          }
        >
          {modNou ? (
            <div className="flex flex-col gap-4">
              <Camp
                eticheta="Nume beneficiar"
                icoana={User}
                value={numeNou}
                onChange={(e) => setNumeNou(e.target.value)}
                placeholder="Ex. Andrei Popescu"
                autoComplete="off"
                eroare={eroareNume}
              />
              <Camp
                eticheta="IBAN"
                value={ibanNou}
                onChange={(e) => setIbanNou(e.target.value.toUpperCase())}
                placeholder="RO49 AAAA 1B31 0075 9384 0000"
                autoComplete="off"
                eroare={eroareIban}
              />
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <Camp
                eticheta="Cauta"
                icoana={Search}
                value={cautare}
                onChange={(e) => setCautare(e.target.value)}
                placeholder="Nume sau IBAN"
                autoComplete="off"
              />

              <button
                type="button"
                onClick={() => setModNou(true)}
                className="flex items-center gap-3 rounded-field border border-dashed border-primary-200 bg-primary-50 px-4 py-3 text-left transition-colors hover:bg-primary-100"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 text-primary-700">
                  <Plus size={16} strokeWidth={1.75} aria-hidden />
                </span>
                <span className="text-[15px] font-medium text-primary-700">Beneficiar nou</span>
              </button>

              <div className="flex flex-col gap-2">
                {filtrati.map((b) => (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() => alege(b)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-field border px-4 py-3 text-left transition-colors duration-150 ease-soft",
                      selectat?.id === b.id
                        ? "border-primary-500 bg-primary-50"
                        : "border-line bg-surface hover:bg-muted",
                    )}
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-100 text-[12px] font-semibold text-primary-700">
                      {initiale(b.nume)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-1.5">
                        <span className="truncate text-[15px] text-ink">{b.nume}</span>
                        {b.favorit ? (
                          <Star
                            size={13}
                            strokeWidth={1.75}
                            aria-hidden
                            className="shrink-0 fill-warning text-warning"
                          />
                        ) : null}
                      </span>
                      <span className="block truncate text-[12.5px] text-ink-faint">{b.banca}</span>
                    </span>
                    {selectat?.id === b.id ? (
                      <Check size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-primary-600" />
                    ) : null}
                  </button>
                ))}

                {filtrati.length === 0 ? (
                  <p className="py-4 text-center text-[13px] text-ink-faint">
                    Niciun beneficiar gasit.
                  </p>
                ) : null}
              </div>
            </div>
          )}
        </DrawerContent>
      </Drawer>
    </div>
  );
}
