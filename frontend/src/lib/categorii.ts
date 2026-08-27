import {
  ArrowLeftRight,
  Car,
  HeartPulse,
  Home,
  MoreHorizontal,
  Receipt,
  Repeat,
  ShoppingBag,
  UtensilsCrossed,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { converteste, type Curs, type Valuta } from "@/lib/valute";

/**
 * Etichete + iconițe pentru categoriile de cheltuieli — cheile trebuie să fie
 * EXACT cele din backend/app/tools/categorii_tranzactii.py::categorizeaza()
 * (RO81 LIBR fictiv, dar categoria e reală, calculată determinist de backend,
 * niciodată ghicită aici — CLAUDE.md #7/#25).
 */
export const CATEGORIE_INFO: Record<string, { eticheta: string; icona: LucideIcon }> = {
  transfer: { eticheta: "Transferuri", icona: ArrowLeftRight },
  masina: { eticheta: "Mașină", icona: Car },
  cumparaturi: { eticheta: "Cumpărături", icona: ShoppingBag },
  utilitati: { eticheta: "Utilități", icona: Receipt },
  restaurant: { eticheta: "Restaurant", icona: UtensilsCrossed },
  sanatate: { eticheta: "Sănătate", icona: HeartPulse },
  abonamente: { eticheta: "Abonamente", icona: Repeat },
  locuinta: { eticheta: "Locuință", icona: Home },
  salariu: { eticheta: "Salariu", icona: Wallet },
  altele: { eticheta: "Altele", icona: MoreHorizontal },
};

export function etichetaCategorie(categorie: string): string {
  return CATEGORIE_INFO[categorie]?.eticheta ?? categorie;
}

/**
 * Cheltuielile pe categorie, asa cum le intoarce backend-ul: o suma pe
 * (categorie, valuta), niciodata convertita — backend-ul (Python) n-are acces
 * la cursuri valutare, acelea traiesc doar in Supabase/Next.js
 * (lib/data/curs-valutar.ts).
 */
export type CategorieCheltuialaBruta = {
  categorie: string;
  valuta: string;
  total: number;
};

/**
 * Totalul pe categorie, in valuta ceruta — acelasi tipar ca `totalSoldIn`
 * (lib/valute.ts): fiecare suma se converteste inainte de adunare, iar o
 * categorie fara curs pentru valuta ei ramane afara din suma (mai bine o
 * cifra mai mica si corecta decat una inventata).
 */
export function totalizeazaPeCategorie(
  intrari: CategorieCheltuialaBruta[],
  cursuri: Curs[],
  spre: Valuta,
): { categorie: string; total: number }[] {
  const baniPeCategorie = new Map<string, number>();

  for (const intrare of intrari) {
    const convertit = converteste(intrare.total, intrare.valuta as Valuta, spre, cursuri);
    if (convertit === null) continue;

    const baniAnteriori = baniPeCategorie.get(intrare.categorie) ?? 0;
    baniPeCategorie.set(intrare.categorie, baniAnteriori + Math.round(convertit * 100));
  }

  return [...baniPeCategorie.entries()]
    .map(([categorie, bani]) => ({ categorie, total: bani / 100 }))
    .sort((a, b) => b.total - a.total);
}
