import type { Metadata } from "next";
import { ListaCarduri } from "@/components/carduri/lista-carduri";
import { obtineCarduriUtilizator } from "@/lib/data/carduri";

export const metadata: Metadata = {
  title: "Carduri · Galaxy Bank",
};

export default async function CarduriPage() {
  const carduri = await obtineCarduriUtilizator();

  return <ListaCarduri carduri={carduri} />;
}
