"use client";

import { SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerTrigger,
} from "@/components/ui/drawer";
import { cn } from "@/lib/utils";

export type Perioada = "7z" | "30z" | "3l" | "tot";
export type TipFiltru = "toate" | "incasare" | "plata";

export type Filtre = { perioada: Perioada; tip: TipFiltru };

const PERIOADE: { valoare: Perioada; eticheta: string }[] = [
  { valoare: "7z", eticheta: "7 zile" },
  { valoare: "30z", eticheta: "30 zile" },
  { valoare: "3l", eticheta: "3 luni" },
  { valoare: "tot", eticheta: "Tot" },
];

const TIPURI: { valoare: TipFiltru; eticheta: string }[] = [
  { valoare: "toate", eticheta: "Toate" },
  { valoare: "incasare", eticheta: "Incasari" },
  { valoare: "plata", eticheta: "Plati" },
];

function Chip({
  activ,
  onClick,
  children,
}: {
  activ: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={activ}
      className={cn(
        "rounded-full border px-4 py-2 text-[13px] font-medium transition-colors duration-150 ease-soft",
        activ
          ? "border-primary-600 bg-primary-600 text-white"
          : "border-line bg-surface text-ink-soft hover:bg-primary-50",
      )}
    >
      {children}
    </button>
  );
}

export function FiltreDrawer({
  filtre,
  onFiltreChange,
  numarRezultate,
}: {
  filtre: Filtre;
  onFiltreChange: (filtre: Filtre) => void;
  numarRezultate: number;
}) {
  return (
    <Drawer>
      <DrawerTrigger
        aria-label="Filtreaza istoricul"
        className="flex h-11 w-11 items-center justify-center rounded-full bg-surface text-ink-soft shadow-sm transition-colors hover:text-primary-600 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <SlidersHorizontal size={18} strokeWidth={1.75} aria-hidden />
      </DrawerTrigger>

      <DrawerContent
        title="Filtreaza istoricul"
        description="Alege perioada si tipul tranzactiilor afisate."
        footer={
          <DrawerClose asChild>
            <Button className="w-full">
              Vezi {numarRezultate} {numarRezultate === 1 ? "rezultat" : "rezultate"}
            </Button>
          </DrawerClose>
        }
      >
        <div className="flex flex-col gap-6">
          <div>
            <p className="mb-3 text-[13px] font-medium text-ink-soft">Perioada</p>
            <div className="flex flex-wrap gap-2">
              {PERIOADE.map(({ valoare, eticheta }) => (
                <Chip
                  key={valoare}
                  activ={filtre.perioada === valoare}
                  onClick={() => onFiltreChange({ ...filtre, perioada: valoare })}
                >
                  {eticheta}
                </Chip>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-3 text-[13px] font-medium text-ink-soft">Tip</p>
            <div className="flex flex-wrap gap-2">
              {TIPURI.map(({ valoare, eticheta }) => (
                <Chip
                  key={valoare}
                  activ={filtre.tip === valoare}
                  onClick={() => onFiltreChange({ ...filtre, tip: valoare })}
                >
                  {eticheta}
                </Chip>
              ))}
            </div>
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}

