"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import type { Valuta } from "@/lib/valute";

/**
 * Valuta aleasa pe dashboard, impartita intre TotalConturi (unde se alege) si
 * CategoriiCheltuieli (care doar o citeste) — cele doua nu sunt adiacente in
 * pagina, deci starea nu poate fi ridicata intr-un parinte comun fara sa
 * rearanjeze tot layout-ul dashboard/page.tsx. Contextul lasa fiecare
 * component la locul lui.
 */
const ValutaDashboardContext = createContext<{
  valuta: Valuta;
  seteazaValuta: (valuta: Valuta) => void;
} | null>(null);

export function ValutaDashboardProvider({ children }: { children: ReactNode }) {
  const [valuta, seteazaValuta] = useState<Valuta>("RON");
  return (
    <ValutaDashboardContext.Provider value={{ valuta, seteazaValuta }}>
      {children}
    </ValutaDashboardContext.Provider>
  );
}

export function useValutaDashboard() {
  const context = useContext(ValutaDashboardContext);
  if (!context) {
    throw new Error("useValutaDashboard trebuie folosit sub ValutaDashboardProvider.");
  }
  return context;
}
