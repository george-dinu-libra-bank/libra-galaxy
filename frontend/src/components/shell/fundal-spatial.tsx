/**
 * Cerul instelat din spatele aplicatiei — vizibil doar in tema intunecata
 * (vezi .fundal-spatial in globals.css). Pur decorativ si static din punct de
 * vedere React: intreaga animatie (stele + racheta) e in CSS, deci componenta
 * nu are nevoie de "use client".
 */
export function FundalSpatial() {
  return (
    <div className="fundal-spatial" aria-hidden>
      <span className="fundal-spatial__racheta">🚀</span>
    </div>
  );
}
