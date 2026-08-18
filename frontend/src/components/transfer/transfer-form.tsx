"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Check, FileText } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { AlegeBeneficiarDrawer } from "@/components/transfer/alege-beneficiar-drawer";
import { AlegeContDrawer } from "@/components/transfer/alege-cont-drawer";
import { ConfirmaTransferDrawer } from "@/components/transfer/confirma-transfer-drawer";
import type { Beneficiar, Cont } from "@/lib/mock-data";
import { formateazaSuma } from "@/lib/utils";

export function TransferForm({
  conturi,
  beneficiari,
  beneficiarInitial = null,
}: {
  conturi: Cont[];
  beneficiari: Beneficiar[];
  beneficiarInitial?: Beneficiar | null;
}) {
  const router = useRouter();
  const [contSursa, setContSursa] = useState<Cont>(conturi[0]);
  const [beneficiar, setBeneficiar] = useState<Beneficiar | null>(beneficiarInitial);
  const [suma, setSuma] = useState("");
  const [detalii, setDetalii] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [confirmDeschis, setConfirmDeschis] = useState(false);
  const [trimis, setTrimis] = useState(false);

  const sumaNumerica = Number(suma.replace(",", "."));

  function continua() {
    if (!beneficiar) {
      setEroare("Alege beneficiarul catre care trimiti banii.");
      return;
    }
    if (!suma || Number.isNaN(sumaNumerica) || sumaNumerica <= 0) {
      setEroare("Introdu o suma valida.");
      return;
    }
    if (sumaNumerica > contSursa.sold) {
      setEroare("Nu ai fonduri suficiente in contul selectat.");
      return;
    }
    setEroare(null);
    setConfirmDeschis(true);
  }

  if (trimis && beneficiar) {
    return (
      <div className="mx-auto flex w-full max-w-[440px] flex-col items-center px-6 pb-6 pt-16 text-center sm:max-w-2xl">
        <span className="flex h-16 w-16 animate-pop items-center justify-center rounded-full bg-success/10">
          <Check size={30} strokeWidth={1.75} aria-hidden className="text-success" />
        </span>
        <h1 className="mt-5 text-xl font-bold tracking-[-0.02em] text-ink">Transfer trimis</h1>
        <p className="mt-2 text-[15px] leading-[22px] text-ink-soft">
          Ai trimis {formateazaSuma(sumaNumerica)} catre {beneficiar.nume}.
        </p>

        <div className="mt-8 flex w-full flex-col gap-3">
          <Button className="w-full" onClick={() => router.push("/istoric")}>
            Vezi in istoric
          </Button>
          <Button
            varianta="ghost"
            className="w-full"
            onClick={() => {
              setTrimis(false);
              setBeneficiar(null);
              setSuma("");
              setDetalii("");
            }}
          >
            Fa un alt transfer
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Transfer</h1>
      <p className="mt-1 text-[15px] text-ink-soft">Trimite bani catre un cont din Romania.</p>

      <div className="mt-6 flex flex-col gap-4">
        <AlegeContDrawer conturi={conturi} selectat={contSursa} onSelect={setContSursa} />
        <AlegeBeneficiarDrawer
          beneficiari={beneficiari}
          selectat={beneficiar}
          onSelect={setBeneficiar}
        />

        <Camp
          eticheta="Sumă (RON)"
          inputMode="decimal"
          placeholder="0,00"
          value={suma}
          onChange={(e) => setSuma(e.target.value.replace(/[^0-9,.]/g, ""))}
          ajutor={`Disponibil: ${formateazaSuma(contSursa.sold, contSursa.valuta)}`}
        />

        <Camp
          eticheta="Detalii (opțional)"
          icoana={FileText}
          placeholder="Ex. Chirie august"
          value={detalii}
          onChange={(e) => setDetalii(e.target.value)}
          maxLength={140}
        />

        {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

        <Button className="mt-2 w-full" onClick={continua}>
          Continuă
        </Button>
      </div>

      {beneficiar ? (
        <ConfirmaTransferDrawer
          deschis={confirmDeschis}
          onOpenChange={setConfirmDeschis}
          contSursa={contSursa}
          beneficiar={beneficiar}
          suma={sumaNumerica}
          detalii={detalii}
          onConfirmat={() => setTrimis(true)}
        />
      ) : null}
    </div>
  );
}
