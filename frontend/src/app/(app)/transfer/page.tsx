import type { Metadata } from "next";
import { TransferForm } from "@/components/transfer/transfer-form";
import {
  cautaContDupaIban,
  obtineBeneficiariRecenti,
  obtineConturiTransfer,
  type BeneficiarTransfer,
} from "@/lib/data/transfer";
import { ibanEsteValid } from "@/lib/iban";
import { citesteCerereDePlata } from "@/lib/qr-plata";

export const metadata: Metadata = {
  title: "Transfer · Galaxy Bank",
};

export default async function TransferPage({
  searchParams,
}: {
  searchParams: Promise<{
    beneficiar?: string;
    cont?: string;
    /** Cele trei vin dintr-un cod QR (lib/qr-plata.ts). */
    iban?: string;
    suma?: string;
    detalii?: string;
  }>;
}) {
  const [params, conturi, beneficiari] = await Promise.all([
    searchParams,
    obtineConturiTransfer(),
    obtineBeneficiariRecenti(),
  ]);

  let beneficiarInitial: BeneficiarTransfer | null =
    beneficiari.find((b) => b.id === params.beneficiar || b.iban === params.beneficiar) ?? null;

  // Cererea dintr-un cod QR. Beneficiarul poate fi cineva cu care n-ai mai avut
  // de-a face, deci nu e de ajuns sa-l cautam printre cei recenti — daca IBAN-ul
  // trece de cifrele de control, se cauta contul in baza.
  const cerere = citesteCerereDePlata(params);
  let dinCodQr = false;

  if (cerere) {
    const beneficiarQr =
      beneficiari.find((b) => b.iban === cerere.iban) ??
      (ibanEsteValid(cerere.iban)
        ? // Un link stricat nu trebuie sa darame ecranul: ramai pe formularul gol.
          await cautaContDupaIban(cerere.iban).catch(() => null)
        : null);

    if (beneficiarQr) {
      beneficiarInitial = beneficiarQr;
      dinCodQr = true;
    }
  }

  // Vine din cardul de transfer al asistentului (?cont=<id>) — transferul
  // porneste direct din contul ales acolo, nu dintr-unul default.
  const contCerut = conturi.find((c) => c.id === params.cont) ?? null;

  // Cand cineva isi scaneaza propriul cod, contul-tinta e chiar unul de-al lui:
  // preselectarea implicita (primul cont) ar duce la un transfer in acelasi
  // cont, refuzat de core_banking. Se porneste deci din alt cont.
  const beneficiarAles = beneficiarInitial;
  const contInitial =
    contCerut ??
    (beneficiarAles
      ? (conturi.find((c) => c.tip === "cont" && c.id !== beneficiarAles.id) ?? null)
      : null);

  return (
    <TransferForm
      conturi={conturi}
      beneficiari={beneficiari}
      beneficiarInitial={beneficiarInitial}
      contInitial={contInitial}
      // Virgula, ca peste tot in aplicatie; formularul stie sa citeasca ambele.
      sumaInitiala={dinCodQr && cerere?.suma ? String(cerere.suma).replace(".", ",") : ""}
      detaliiInitiale={dinCodQr ? (cerere?.detalii ?? "") : ""}
      // Codul QR a spus deja tot: se deschide direct confirmarea, ca omul sa nu
      // reintroduca datele pe care tocmai le-a scanat.
      confirmaDirect={dinCodQr && Boolean(cerere?.suma)}
    />
  );
}
