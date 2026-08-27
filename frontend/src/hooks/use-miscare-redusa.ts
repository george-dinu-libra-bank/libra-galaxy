"use client";

import { useEffect, useState } from "react";

/**
 * Spune daca utilizatorul a cerut mai putina miscare.
 *
 * Regula din `globals.css` (`@media (prefers-reduced-motion: reduce)`) taie doar
 * animatiile si tranzitiile CSS. Componentele aduse din React Bits animeaza din
 * JavaScript si tin un `requestAnimationFrame` pornit la nesfarsit (fundalul
 * WebGL din hero, scanteile de la click) — pe acelea nu le opreste nicio regula
 * CSS, deci trebuie sa nu le montam deloc.
 *
 * Porneste pe `false` si pe server si la prima randare din browser: asa HTML-ul
 * trimis de server e identic cu ce randeaza React initial, deci nu apare
 * mismatch de hidratare. Valoarea reala vine imediat dupa montare.
 */
export function useMiscareRedusa(): boolean {
  const [redusa, setRedusa] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setRedusa(query.matches);

    const asculta = (e: MediaQueryListEvent) => setRedusa(e.matches);
    query.addEventListener("change", asculta);
    return () => query.removeEventListener("change", asculta);
  }, []);

  return redusa;
}
