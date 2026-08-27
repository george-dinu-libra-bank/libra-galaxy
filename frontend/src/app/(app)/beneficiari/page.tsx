import type { Metadata } from "next";
import { ListaBeneficiari } from "@/components/beneficiari/lista-beneficiari";
import { obtineBeneficiariiMei } from "@/lib/data/beneficiari";

export const metadata: Metadata = {
  title: "Beneficiari · Galaxy Bank",
};

export default async function BeneficiariPage() {
  const beneficiari = await obtineBeneficiariiMei();

  return <ListaBeneficiari beneficiari={beneficiari} />;
}
