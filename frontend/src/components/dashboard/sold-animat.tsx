"use client";

import { useEffect, useRef, useState } from "react";
import { formateazaSuma } from "@/lib/utils";

const DURATA = 900;

/** easeOutCubic — porneste repede si se aseaza lin pe suma finala. */
function lin(t: number) {
  return 1 - (1 - t) ** 3;
}

/**
 * Soldul care „urca" pana la valoarea reala. Animatia porneste de la 0 la prima
 * randare si, dupa un transfer, de la suma afisata anterior catre cea noua.
 *
 * Cifra in miscare e ascunsa de cititoarele de ecran (aria-hidden); suma finala
 * e anuntata o singura data, din textul din sr-only.
 */
export function SoldAnimat({
  sold,
  valuta = "RON",
  className,
}: {
  sold: number;
  valuta?: string;
  className?: string;
}) {
  const [afisat, setAfisat] = useState(0);
  const dela = useRef(0);

  useEffect(() => {
    const redus = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const start = dela.current;
    const delta = sold - start;

    // DESIGN.md 7: cu prefers-reduced-motion nu numaram, sarim la valoare.
    if (redus || delta === 0) {
      dela.current = sold;
      setAfisat(sold);
      return;
    }

    let cadru = 0;
    let inceput: number | null = null;

    function pas(acum: number) {
      inceput ??= acum;
      const t = Math.min((acum - inceput) / DURATA, 1);
      const valoare = t < 1 ? start + delta * lin(t) : sold;

      dela.current = valoare;
      setAfisat(valoare);

      if (t < 1) cadru = requestAnimationFrame(pas);
    }

    cadru = requestAnimationFrame(pas);

    return () => cancelAnimationFrame(cadru);
  }, [sold]);

  return (
    <p className={className}>
      <span aria-hidden>{formateazaSuma(afisat, valuta)}</span>
      <span className="sr-only">{formateazaSuma(sold, valuta)}</span>
    </p>
  );
}
