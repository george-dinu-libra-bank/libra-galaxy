import type { Metadata } from "next";
import { ListaTranzactii } from "@/components/istoric/lista-tranzactii";
import { obtineTranzactiiUtilizator } from "@/lib/data/tranzactii";

export const metadata: Metadata = {
  title: "Istoric · Libra",
};

export default async function IstoricPage() {
  const tranzactii = await obtineTranzactiiUtilizator();

  return <ListaTranzactii tranzactii={tranzactii} />;
}
