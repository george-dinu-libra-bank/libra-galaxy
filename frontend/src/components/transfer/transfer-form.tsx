"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";
import { Check, FileText, ShieldAlert, Wallet } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { AlegeBeneficiarDrawer } from "@/components/transfer/alege-beneficiar-drawer";
import { AlegeContDrawer } from "@/components/transfer/alege-cont-drawer";
import { ConfirmaTransferDrawer } from "@/components/transfer/confirma-transfer-drawer";
import { trimiteTransfer } from "@/lib/actions/transfer";
import type { BeneficiarTransfer, ContSursa } from "@/lib/data/transfer";
import { cn, formateazaSuma } from "@/lib/utils";

export function TransferForm({
  conturi,
  beneficiari,
  beneficiarInitial = null,
  contInitial = null,
  sumaInitiala = "",
  detaliiInitiale = "",
  confirmaDirect = false,
}: {
  conturi: ContSursa[];
  beneficiari: BeneficiarTransfer[];
  beneficiarInitial?: BeneficiarTransfer | null;
  /** Cont preselectat (ex. venit din cardul de transfer al asistentului, ?cont=<id>). */
  contInitial?: ContSursa | null;
  /** Cele trei vin dintr-un cod QR scanat (lib/qr-plata.ts). */
  sumaInitiala?: string;
  detaliiInitiale?: string;
  /** Sare peste formular si deschide direct confirmarea, cu datele din cod. */
  confirmaDirect?: boolean;
}) {
  const router = useRouter();
  const [contSursa, setContSursa] = useState<ContSursa | null>(
    contInitial ?? conturi.find((c) => !c.blocat) ?? conturi[0] ?? null,
  );
  const [beneficiar, setBeneficiar] = useState<BeneficiarTransfer | null>(beneficiarInitial);
  const [suma, setSuma] = useState(sumaInitiala);
  const [detalii, setDetalii] = useState(detaliiInitiale);
  const [eroare, setEroare] = useState<string | null>(null);
  const [eroareTrimitere, setEroareTrimitere] = useState<string | null>(null);
  const [confirmDeschis, setConfirmDeschis] = useState(false);
  const [trimis, setTrimis] = useState(false);
  /** Transferul a fost oprit de banca pentru verificare, nu a plecat. */
  const [semnalat, setSemnalat] = useState(false);
  const [seTrimite, startTransition] = useTransition();

  const sumaNumerica = Number(suma.replace(",", "."));

  function continua() {
    if (!contSursa) {
      setEroare("Contul tau nu a fost gasit.");
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
      setEroare(
        contSursa.tip === "grup"
          ? "Grupul nu are fonduri suficiente."
          : "Nu ai fonduri suficiente in cont.",
      );
      return;
    }
    setEroare(null);
    setEroareTrimitere(null);
    setConfirmDeschis(true);
  }

  // Datele venite dintr-un cod QR au trecut deja prin ochii omului, pe ecranul
  // celui care cerea banii: confirmarea se deschide singura, o data, la intrarea
  // in pagina. Trece tot prin `continua`, deci verificarile (cont, sold, suma)
  // raman aceleasi — un cod cu o suma mai mare decat soldul se opreste in
  // formular, cu acelasi mesaj ca la scrierea de mana.
  const pornit = useRef(false);

  useEffect(() => {
    if (!confirmaDirect || pornit.current) return;
    pornit.current = true;
    continua();
    // Se ruleaza o singura data, la montare: `continua` citeste starea initiala.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function trimite() {
    if (!contSursa || !beneficiar) return;

    setEroareTrimitere(null);
    startTransition(async () => {
      const rezultat = await trimiteTransfer({
        ibanDestinatar: beneficiar.iban,
        suma: sumaNumerica,
        detalii,
        // Din grup banii pleaca prin core_banking_groups; din cont, prin
        // core_banking. Actiunea alege dupa care dintre id-uri primeste.
        ...(contSursa.tip === "grup"
          ? { idGrupSursa: Number(contSursa.id) }
          : { idContSursa: contSursa.id }),
      });

      if (rezultat.eroare) {
        setEroareTrimitere(rezultat.eroare);
        return;
      }

      setConfirmDeschis(false);
      setSemnalat(Boolean(rezultat.semnalat));
      setTrimis(true);
      // Solduri, istoric si beneficiari recenti — reincarcate din Supabase.
      router.refresh();
    });
  }

  if (conturi.length === 0) {
    return (
      <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
        <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Transfer</h1>
        <p className="mt-1 text-[15px] text-ink-soft">Trimite bani catre un cont Galaxy Bank.</p>

        <section className="mt-6 flex flex-col items-center gap-4 rounded-card border border-dashed border-line bg-surface p-6 text-center shadow-sm">
          <p className="text-[15px] leading-[22px] text-ink-soft">
            Contul tau nu a fost gasit. Reincarca pagina sau autentifica-te din nou.
          </p>
          <Link
            href="/dashboard"
            className="flex h-[52px] w-full items-center justify-center gap-2 rounded-field bg-primary-600 text-[15px] font-semibold text-white shadow-btn transition-colors hover:bg-primary-700"
          >
            <Wallet size={18} strokeWidth={1.75} aria-hidden />
            Mergi la cont
          </Link>
        </section>
      </div>
    );
  }

  if (trimis && beneficiar) {
    return (
      <div className="mx-auto flex w-full max-w-[440px] flex-col items-center px-6 pb-6 pt-16 text-center sm:max-w-2xl">
        <span
          className={cn(
            "flex h-16 w-16 animate-pop items-center justify-center rounded-full",
            semnalat ? "bg-warning/10" : "bg-success/10",
          )}
        >
          {semnalat ? (
            <ShieldAlert size={30} strokeWidth={1.75} aria-hidden className="text-warning" />
          ) : (
            <Check size={30} strokeWidth={1.75} aria-hidden className="text-success" />
          )}
        </span>
        <h1 className="mt-5 text-xl font-bold tracking-[-0.02em] text-ink">
          {semnalat ? "Transfer în verificare" : "Transfer trimis"}
        </h1>
        <p className="mt-2 text-[15px] leading-[22px] text-ink-soft">
          {semnalat ? (
            <>
              Suma de {formateazaSuma(sumaNumerica)} a fost reținută și nu a ajuns încă la{" "}
              {beneficiar.nume}. Un coleg de la bancă verifică transferul și vei primi o
              notificare cu decizia.
            </>
          ) : (
            <>
              Ai trimis {formateazaSuma(sumaNumerica)} catre {beneficiar.nume}.
            </>
          )}
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
              setSemnalat(false);
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
      <p className="mt-1 text-[15px] text-ink-soft">Trimite bani catre un cont Galaxy Bank.</p>

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
          eticheta={contSursa ? `Sumă (${contSursa.valuta})` : "Sumă"}
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
