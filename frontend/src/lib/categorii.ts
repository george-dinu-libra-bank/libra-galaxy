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
