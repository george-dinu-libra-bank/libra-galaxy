import type { Metadata } from "next";
import { TransferForm } from "@/components/transfer/transfer-form";
import { obtineBeneficiariRecenti, obtineConturiTransfer } from "@/lib/data/transfer";

export const metadata: Metadata = {
  title: "Transfer · Galaxy Bank",
};

export default async function TransferPage({
  searchParams,
}: {
  searchParams: Promise<{ beneficiar?: string; cont?: string }>;
}) {
  const [{ beneficiar: beneficiarId, cont: contId }, conturi, beneficiari] = await Promise.all([
    searchParams,
    obtineConturiTransfer(),
    obtineBeneficiariRecenti(),
  ]);

  const beneficiarInitial =
    beneficiari.find((b) => b.id === beneficiarId || b.iban === beneficiarId) ?? null;
  // Vine din cardul de transfer al asistentului (?cont=<id>) — transferul
  // porneste direct din contul ales acolo, nu dintr-unul default.
  const contInitial = conturi.find((c) => c.id === contId) ?? null;

  return (
    <TransferForm
      conturi={conturi}
      beneficiari={beneficiari}
      beneficiarInitial={beneficiarInitial}
      contInitial={contInitial}
    />
  );
}
