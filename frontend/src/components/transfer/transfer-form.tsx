"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Check, CreditCard, FileText } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { AlegeBeneficiarDrawer } from "@/components/transfer/alege-beneficiar-drawer";
import { AlegeContDrawer } from "@/components/transfer/alege-cont-drawer";
import { ConfirmaTransferDrawer } from "@/components/transfer/confirma-transfer-drawer";
import { trimiteTransfer } from "@/lib/actions/transfer";
import type { BeneficiarTransfer, ContSursa } from "@/lib/data/transfer";
import { formateazaSuma } from "@/lib/utils";

export function TransferForm({
  conturi,
  beneficiari,
  beneficiarInitial = null,
}: {
  conturi: ContSursa[];
  beneficiari: BeneficiarTransfer[];
  beneficiarInitial?: BeneficiarTransfer | null;
}) {
  const router = useRouter();
  const [contSursa, setContSursa] = useState<ContSursa | null>(
    conturi.find((c) => !c.blocat) ?? conturi[0] ?? null,
  );
  const [beneficiar, setBeneficiar] = useState<BeneficiarTransfer | null>(beneficiarInitial);
  const [suma, setSuma] = useState("");
  const [detalii, setDetalii] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [eroareTrimitere, setEroareTrimitere] = useState<string | null>(null);
  const [confirmDeschis, setConfirmDeschis] = useState(false);
  const [trimis, setTrimis] = useState(false);
  const [seTrimite, startTransition] = useTransition();

  const sumaNumerica = Number(suma.replace(",", "."));

  function continua() {
    if (!contSursa) {
      setEroare("Nu ai niciun card din care sa trimiti bani.");
      return;
    }
    if (contSursa.blocat) {
      setEroare("Cardul selectat este blocat. Deblocheaza-l sau alege alt card.");
      return;
    }
    if (!beneficiar) {
      setEroare("Alege beneficiarul catre care trimiti banii.");
      return;
    }
    if (!suma || Number.isNaN(sumaNumerica) || sumaNumerica <= 0) {
      setEroare("Introdu o suma valida.");
      return;
    }
    if (sumaNumerica > contSursa.sold) {
      setEroare("Nu ai fonduri suficiente in cardul selectat.");
      return;
    }
    setEroare(null);
    setEroareTrimitere(null);
    setConfirmDeschis(true);
  }

  function trimite() {
    if (!contSursa || !beneficiar) return;

    setEroareTrimitere(null);
    startTransition(async () => {
      const rezultat = await trimiteTransfer({
        idCardSursa: contSursa.id,
        ibanDestinatar: beneficiar.iban,
        suma: sumaNumerica,
        detalii,
      });

      if (rezultat.eroare) {
        setEroareTrimitere(rezultat.eroare);
        return;
      }

      setConfirmDeschis(false);
      setTrimis(true);
      // Solduri, istoric si beneficiari recenti — reincarcate din Supabase.
      router.refresh();
    });
  }

  if (conturi.length === 0) {
    return (
      <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
        <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Transfer</h1>
        <p className="mt-1 text-[15px] text-ink-soft">Trimite bani catre un cont Libra.</p>

        <section className="mt-6 flex flex-col items-center gap-4 rounded-card border border-dashed border-line bg-surface p-6 text-center shadow-sm">
          <p className="text-[15px] leading-[22px] text-ink-soft">
            Nu ai niciun card. Adauga unul ca sa poti trimite bani.
          </p>
          <Link
            href="/carduri"
            className="flex h-[52px] w-full items-center justify-center gap-2 rounded-field bg-primary-600 text-[15px] font-semibold text-white shadow-btn transition-colors hover:bg-primary-700"
          >
            <CreditCard size={18} strokeWidth={1.75} aria-hidden />
            Mergi la carduri
          </Link>
        </section>
      </div>
    );
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
      <p className="mt-1 text-[15px] text-ink-soft">Trimite bani catre un cont Libra.</p>

      <div className="mt-6 flex flex-col gap-4">
        {contSursa ? (
          <AlegeContDrawer conturi={conturi} selectat={contSursa} onSelect={setContSursa} />
        ) : null}
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
          ajutor={
            contSursa
              ? `Disponibil: ${formateazaSuma(contSursa.sold, contSursa.valuta)}`
              : undefined
          }
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

      {contSursa && beneficiar ? (
        <ConfirmaTransferDrawer
          deschis={confirmDeschis}
          onOpenChange={setConfirmDeschis}
          contSursa={contSursa}
          beneficiar={beneficiar}
          suma={sumaNumerica}
          detalii={detalii}
          seTrimite={seTrimite}
          eroare={eroareTrimitere}
          onConfirma={trimite}
        />
      ) : null}
    </div>
  );
}
