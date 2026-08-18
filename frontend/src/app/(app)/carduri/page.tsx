import type { Metadata } from "next";
import { ListaCarduri } from "@/components/carduri/lista-carduri";
import { obtineCarduri } from "@/lib/mock-data";

export const metadata: Metadata = {
  title: "Carduri · Libra",
};

export default async function CarduriPage() {
  const carduri = await obtineCarduri();

  return <ListaCarduri carduri={carduri} />;
}
