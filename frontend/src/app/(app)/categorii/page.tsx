import type { Metadata } from "next";
import { ListaCategorii } from "@/components/categorii/lista-categorii";
import { obtineCheltuieliPeCategorie } from "@/lib/data/analiza";
import { obtineCursuri } from "@/lib/data/curs-valutar";

export const metadata: Metadata = {
  title: "Cheltuieli pe categorii · Galaxy Bank",
};

/** "2026-08" -> "August 2026" */
function numeLunaAnul(luna: string) {
  if (!luna) return "";
  const data = new Date(`${luna}-01T00:00:00`);
  const text = data.toLocaleDateString("ro-RO", { month: "long", year: "numeric" });
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export default async function CategoriiPage() {
  const [cheltuieli, cursuri] = await Promise.all([obtineCheltuieliPeCategorie(), obtineCursuri()]);

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Cheltuieli pe categorii</h1>
      <p className="mt-1 text-[13px] text-ink-faint">{numeLunaAnul(cheltuieli.luna)}</p>

      <ListaCategorii categoriiBrute={cheltuieli.categorii} cursuri={cursuri} />
    </div>
  );
}
