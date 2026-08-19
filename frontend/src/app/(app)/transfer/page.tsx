import type { Metadata } from "next";
import { TransferForm } from "@/components/transfer/transfer-form";
import { obtineBeneficiariRecenti, obtineConturiTransfer } from "@/lib/data/transfer";

export const metadata: Metadata = {
  title: "Transfer · Libra",
};

export default async function TransferPage({
  searchParams,
}: {
  searchParams: Promise<{ beneficiar?: string }>;
}) {
  const [{ beneficiar: beneficiarId }, conturi, beneficiari] = await Promise.all([
    searchParams,
    obtineConturiTransfer(),
    obtineBeneficiariRecenti(),
  ]);

  const beneficiarInitial =
    beneficiari.find((b) => b.id === beneficiarId || b.iban === beneficiarId) ?? null;

  return (
    <TransferForm conturi={conturi} beneficiari={beneficiari} beneficiarInitial={beneficiarInitial} />
  );
}
