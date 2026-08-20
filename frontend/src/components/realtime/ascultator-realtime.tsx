"use client";

import { useState } from "react";
import { toast } from "sonner";
import { PloaieConfetti } from "@/components/realtime/ploaie-confetti";
import { ToastIncasare } from "@/components/realtime/toast-incasare";
import {
  useCanalUtilizator,
  type EvenimentTranzactie,
} from "@/hooks/use-canal-utilizator";

/**
 * Tine ecranele autentificate la zi: asculta canalul privat, cere re-randarea
 * Server Components si, cand intra bani, scoate notificarea si porneste ploaia
 * de confetti.
 */
export function AscultatorRealtime({ idUtilizator }: { idUtilizator: string }) {
  // Marca de timp a ultimei incasari, folosita si ca `key`: doua incasari la
  // rand repornesc ploaia de la capat in loc sa o lase pe prima sa se termine.
  const [ploaie, setPloaie] = useState<number | null>(null);

  useCanalUtilizator(idUtilizator, (eveniment: EvenimentTranzactie) => {
    toast.custom(
      (idToast) => <ToastIncasare eveniment={eveniment} idToast={idToast} />,
      {
        // Acelasi id ca tranzactia: daca mesajul e livrat de doua ori (dupa o
        // reconectare), notificarea se inlocuieste, nu se dubleaza.
        id: eveniment.id,
        duration: 6000,
      },
    );

    setPloaie(Date.now());
  });

  if (ploaie === null) return null;

  return <PloaieConfetti key={ploaie} laFinal={() => setPloaie(null)} />;
}
