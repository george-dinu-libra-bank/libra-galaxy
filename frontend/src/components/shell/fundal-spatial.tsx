import Image from "next/image";

/**
 * Cerul instelat din spatele aplicatiei — vizibil doar in tema intunecata
 * (vezi .fundal-spatial in globals.css). Pur decorativ si static din punct de
 * vedere React: intreaga animatie (stele + racheta) e in CSS, deci componenta
 * nu are nevoie de "use client".
 *
 * Sigla e in acelasi strat, intre fundal si continut (z-index -10): un
 * filigran mare, centrat, sub tot ce se citeste pe ecran.
 */
export function FundalSpatial() {
  return (
    <div className="fundal-spatial" aria-hidden>
      <Image src="/logo.png" alt="" width={400} height={400} priority className="fundal-spatial__sigla" />
      <span className="fundal-spatial__racheta">🚀</span>
    </div>
  );
}
