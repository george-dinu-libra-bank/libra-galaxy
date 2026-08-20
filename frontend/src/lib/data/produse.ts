import {
  Backpack,
  Headphones,
  Keyboard,
  Lamp,
  Speaker,
  Watch,
  type LucideIcon,
} from "lucide-react";

export type Produs = {
  slug: string;
  nume: string;
  pret: number;
  descriereScurta: string;
  descriere: string;
  icoana: LucideIcon;
  gradient: string;
};

/**
 * Catalog mock — doar UI pentru moment, fara comenzi/plati reale.
 * Vine backend-ul separat (produse + comenzi in Supabase).
 */
export const PRODUSE: Produs[] = [
  {
    slug: "casti-aurora",
    nume: "Căști wireless Aurora",
    pret: 449.99,
    descriereScurta: "Anulare activă a zgomotului, 30h autonomie.",
    descriere:
      "Căști over-ear cu anulare activă a zgomotului, 30 de ore de autonomie pe o singură încărcare și Bluetooth 5.3. Perechea perfectă pentru drumul spre birou sau pentru concentrare totală la lucru.",
    icoana: Headphones,
    gradient:
      "linear-gradient(160deg, var(--color-primary-500) 0%, var(--color-primary-600) 55%, var(--color-primary-700) 100%)",
  },
  {
    slug: "ceas-orbit",
    nume: "Ceas smart Orbit",
    pret: 899,
    descriereScurta: "GPS, monitorizare somn, rezistent la apă.",
    descriere:
      "Ceas inteligent cu GPS integrat, monitorizare a somnului și a pulsului, rezistență la apă 5ATM și baterie care ține până la 7 zile. Ecran AMOLED lizibil chiar și în plin soare.",
    icoana: Watch,
    gradient: "linear-gradient(160deg, var(--color-ink-soft) 0%, var(--color-ink) 100%)",
  },
  {
    slug: "boxa-nova",
    nume: "Boxă portabilă Nova",
    pret: 259.5,
    descriereScurta: "Sunet 360°, rezistentă la stropi.",
    descriere:
      "Boxă portabilă compactă cu sunet 360°, rezistență la stropi (IPX5) și până la 12 ore de redare. Se cuplează cu o a doua boxă Nova pentru sunet stereo.",
    icoana: Speaker,
    gradient:
      "linear-gradient(160deg, color-mix(in srgb, var(--color-success) 55%, white) 0%, var(--color-success) 100%)",
  },
  {
    slug: "tastatura-pulsar",
    nume: "Tastatură mecanică Pulsar",
    pret: 379,
    descriereScurta: "Switch-uri hot-swap, iluminare RGB.",
    descriere:
      "Tastatură mecanică compactă (75%) cu switch-uri hot-swap, iluminare RGB pe fiecare tastă și conectivitate dublă — cablu USB-C sau Bluetooth pentru până la 3 dispozitive.",
    icoana: Keyboard,
    gradient:
      "linear-gradient(160deg, color-mix(in srgb, var(--color-warning) 55%, white) 0%, var(--color-warning) 55%, color-mix(in srgb, var(--color-warning) 65%, black) 100%)",
  },
  {
    slug: "rucsac-voyager",
    nume: "Rucsac urban Voyager",
    pret: 329,
    descriereScurta: "Compartiment laptop 16\", material impermeabil.",
    descriere:
      "Rucsac urban din material impermeabil, cu compartiment matlasat pentru laptop de până la 16 inch, port USB extern de încărcare și buzunar ascuns anti-furt.",
    icoana: Backpack,
    gradient: "linear-gradient(160deg, var(--color-danger) 0%, var(--color-primary-900) 100%)",
  },
  {
    slug: "lampa-nebula",
    nume: "Lampă LED Nebula",
    pret: 189.9,
    descriereScurta: "Lumină reglabilă, control din aplicație.",
    descriere:
      "Lampă de birou cu LED-uri reglabile în intensitate și temperatură de culoare, control din aplicație sau de pe corpul lămpii, plus modul de lumină ambientală pentru seară.",
    icoana: Lamp,
    gradient:
      "linear-gradient(160deg, var(--color-primary-300) 0%, var(--color-primary-500) 45%, var(--color-primary-800) 100%)",
  },
];

export function obtineProdus(slug: string): Produs | undefined {
  return PRODUSE.find((p) => p.slug === slug);
}
