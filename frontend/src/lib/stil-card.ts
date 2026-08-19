import type { StilCard } from "@/lib/data/carduri";

/** Gradientul vizual pentru fiecare tematica de card. Doar tokeni din DESIGN.md. */
export const GRADIENTE_STIL_CARD: Record<StilCard, string> = {
  standard:
    "linear-gradient(160deg, var(--color-primary-500) 0%, var(--color-primary-600) 55%, var(--color-primary-700) 100%)",
  silver: "linear-gradient(160deg, var(--color-ink-soft) 0%, var(--color-ink) 100%)",
  gold: "linear-gradient(160deg, color-mix(in srgb, var(--color-warning) 55%, white) 0%, var(--color-warning) 55%, color-mix(in srgb, var(--color-warning) 65%, black) 100%)",
};

export const ETICHETE_STIL_CARD: Record<StilCard, string> = {
  standard: "Standard",
  silver: "Silver",
  gold: "Gold",
};
