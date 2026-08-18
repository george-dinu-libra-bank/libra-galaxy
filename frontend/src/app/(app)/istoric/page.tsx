import type { Metadata } from "next";
import { ListaTranzactii } from "@/components/istoric/lista-tranzactii";
import { obtineTranzactii } from "@/lib/mock-data";

export const metadata: Metadata = {
  title: "Istoric · Libra",
};

export default async function IstoricPage() {
  const tranzactii = await obtineTranzactii();

  return <ListaTranzactii tranzactii={tranzactii} />;
}
