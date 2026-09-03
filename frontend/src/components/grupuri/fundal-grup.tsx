import { CLASA_FUNDAL_GRUP, type FundalGrup } from "@/lib/tema-grup";
import { cn } from "@/lib/utils";

/**
 * Tapetul din spatele paginii unui grup (0054_tema_grup.sql).
 *
 * Un singur strat fix, opac, asezat intre cerul aplicatiei (z-index -10, vezi
 * shell/fundal-spatial.tsx) si continut. Fiind opac, acopera cerul — de aceea
 * `implicit` nu randeaza nimic: atunci cerul TREBUIE sa ramana vizibil.
 *
 * Modelul se deseneaza din `--color-primary-*`, iar componenta se monteaza
 * INAUNTRU containerului cu clasa temei, deci culoarea grupului ajunge la el
 * prin mostenirea variabilelor CSS. `position: fixed` nu rupe asta: pozitionarea
 * tine de layout, mostenirea proprietatilor custom tine de arborele DOM.
 *
 * Static din punct de vedere React, ca FundalSpatial — nu are nevoie de
 * "use client".
 */
export function FundalGrupStrat({ fundal }: { fundal: FundalGrup }) {
  if (fundal === "implicit") return null;

  return (
    <div
      aria-hidden
      className={cn("fundal-grup-strat", CLASA_FUNDAL_GRUP[fundal])}
    />
  );
}
