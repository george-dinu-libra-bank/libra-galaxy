"use client";

import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import type { BeneficiarTransfer, ContSursa } from "@/lib/data/transfer";
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
  seTrimite,
  eroare,
  onConfirma,
}: {
  deschis: boolean;
  onOpenChange: (deschis: boolean) => void;
  contSursa: ContSursa;
  beneficiar: BeneficiarTransfer;
  suma: number;
  detalii: string;
  seTrimite: boolean;
  eroare: string | null;
  onConfirma: () => void;
}) {
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
          <Button className="w-full" loading={seTrimite} onClick={onConfirma}>
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

          {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

          <div>
            <Rand eticheta="Din cont" valoare={contSursa.nume} />
            <Rand eticheta="IBAN" valoare={contSursa.numarMascat} mono />
            <Rand eticheta="Către" valoare={beneficiar.nume} />
            <Rand eticheta="IBAN beneficiar" valoare={formateazaIban(beneficiar.iban)} mono />
            {detalii ? <Rand eticheta="Detalii" valoare={detalii} /> : null}
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
