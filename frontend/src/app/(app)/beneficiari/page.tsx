import type { Metadata } from "next";
import { ListaBeneficiari } from "@/components/beneficiari/lista-beneficiari";
import { obtineBeneficiari } from "@/lib/mock-data";

export const metadata: Metadata = {
  title: "Beneficiari · Libra",
};

export default async function BeneficiariPage() {
  const beneficiari = await obtineBeneficiari();

  return <ListaBeneficiari beneficiari={beneficiari} />;
}
