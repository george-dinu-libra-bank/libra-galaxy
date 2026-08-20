"use client";

import { Toaster } from "sonner";

/**
 * Zona de notificari. Culorile vin din tokenii Libra (globals.css), deci
 * urmeaza singure tema intunecata — de aceea nu ii dam prop-ul `theme`:
 * proiectul nu are next-themes, clasa „dark" se comuta manual pe <html>.
 */
export function Notificari() {
  return <Toaster position="top-center" offset={16} duration={5000} closeButton />;
}
