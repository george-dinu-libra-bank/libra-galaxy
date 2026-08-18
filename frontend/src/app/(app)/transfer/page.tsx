import type { Metadata } from "next";
import { TransferForm } from "@/components/transfer/transfer-form";
import { obtineBeneficiari, obtineConturi } from "@/lib/mock-data";

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
    obtineConturi(),
    obtineBeneficiari(),
  ]);

  const beneficiarInitial = beneficiari.find((b) => b.id === beneficiarId) ?? null;

  return (
    <TransferForm conturi={conturi} beneficiari={beneficiari} beneficiarInitial={beneficiarInitial} />
  );
}
