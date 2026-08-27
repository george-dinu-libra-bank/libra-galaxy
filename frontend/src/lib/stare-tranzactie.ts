import type { StatusTranzactie } from "@/lib/data/tranzactii";

/**
 * Eticheta de stare a unei tranzactii, pentru listele din aplicatie.
 *
 * Sta separat de `lib/data/tranzactii.ts` fiindca acela e cod de server (aduce
 * clientii Supabase cu el), iar listele care afiseaza eticheta sunt componente
 * client. Din modulul de date se importa doar tipul, cu `import type`.
 *
 * `normala` si `acceptata` nu au eticheta: amandoua inseamna transfer dus la
 * capat, iar un istoric plin de „finalizat" n-ar spune nimic. Raman doar starile
 * in care banii NU sunt (inca) la beneficiar.
 */
export const ETICHETE_STARE: Partial<
  Record<StatusTranzactie, { text: string; stil: string }>
> = {
  flagged: { text: "În verificare", stil: "bg-warning/10 text-warning" },
  anulata: { text: "Anulată", stil: "bg-danger/8 text-danger" },
};

/**
 * Explicatia din spatele etichetei, pentru ecranele care au loc de o propozitie.
 */
export const EXPLICATII_STARE: Partial<Record<StatusTranzactie, string>> = {
  flagged:
    "Suma a fost reținută pentru verificare și nu a ajuns la beneficiar. Vei primi o notificare cu decizia.",
  anulata: "Banca a anulat transferul, iar suma s-a întors în contul din care a plecat.",
};
