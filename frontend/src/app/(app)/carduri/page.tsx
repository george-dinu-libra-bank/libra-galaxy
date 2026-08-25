import type { Metadata } from "next";
import { ListaCarduri } from "@/components/carduri/lista-carduri";
import { obtineCarduriUtilizator } from "@/lib/data/carduri";
import { obtineConturiUtilizator } from "@/lib/data/conturi";

export const metadata: Metadata = {
  title: "Carduri · Galaxy Bank",
};

export default async function CarduriPage() {
  // Conturile se aduc si ele: fara ele nu se poate emite un card nou, fiindca
  // fiecare card apartine unui cont anume.
  const [carduri, conturi] = await Promise.all([
    obtineCarduriUtilizator(),
    obtineConturiUtilizator(),
  ]);

  return <ListaCarduri carduri={carduri} conturi={conturi} />;
}
