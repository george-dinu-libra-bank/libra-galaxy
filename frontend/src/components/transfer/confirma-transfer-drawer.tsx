"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import type { Beneficiar, Cont } from "@/lib/mock-data";
import { formateazaIban, formateazaSuma } from "@/lib/utils";

function Rand({ eticheta, valoare, mono }: { eticheta: string; valoare: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line py-3 last:border-0">
      <span className="text-[13px] text-ink-faint">{eticheta}</span>
      <span className={`text-right text-[15px] text-ink ${mono ? "tabular" : ""}`}>{valoare}</span>
    </div>
  );
}

export function ConfirmaTransferDrawer({
  deschis,
  onOpenChange,
  contSursa,
  beneficiar,
  suma,
  detalii,
  onConfirmat,
}: {
  deschis: boolean;
  onOpenChange: (deschis: boolean) => void;
  contSursa: Cont;
  beneficiar: Beneficiar;
  suma: number;
  detalii: string;
  onConfirmat: () => void;
}) {
  const [seTrimite, setSeTrimite] = useState(false);

  async function trimite() {
    setSeTrimite(true);
    await new Promise((resolve) => setTimeout(resolve, 900));
    setSeTrimite(false);
    onOpenChange(false);
    onConfirmat();
  }

  return (
    <Drawer
      open={deschis}
      onOpenChange={(v) => {
        if (!seTrimite) onOpenChange(v);
      }}
      dismissible={!seTrimite}
    >
      <DrawerContent
        title="Confirma transferul"
        description="Verifica datele inainte de a trimite banii."
        cuInchidere={!seTrimite}
        footer={
          <Button className="w-full" loading={seTrimite} onClick={trimite}>
            Trimite {formateazaSuma(suma)}
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          <div className="rounded-field bg-primary-50 p-4 text-center">
            <p className="text-[13px] text-primary-700">Sumă</p>
            <p className="tabular mt-1 text-[28px] font-bold leading-8 text-primary-900">
              {formateazaSuma(suma)}
            </p>
          </div>

          <div>
            <Rand eticheta="Din cont" valoare={contSursa.nume} />
            <Rand eticheta="IBAN sursă" valoare={formateazaIban(contSursa.iban)} mono />
            <Rand eticheta="Către" valoare={beneficiar.nume} />
            <Rand eticheta="IBAN beneficiar" valoare={formateazaIban(beneficiar.iban)} mono />
            {detalii ? <Rand eticheta="Detalii" valoare={detalii} /> : null}
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
