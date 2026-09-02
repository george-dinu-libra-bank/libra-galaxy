"use client";

import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Comutator } from "@/components/ui/comutator";
import { seteazaVizibilitateaTranzactiilor } from "@/lib/actions/grupuri";

/**
 * Comutatorul creatorului pentru vizibilitatea miscarilor de bani in
 * conversatia grupului (0053_drepturi_grup.sql).
 *
 * Oprit, fiecare membru isi vede doar propriile incasari si plati, iar
 * creatorul le vede pe toate. Mesajele scrise de oameni nu sunt atinse:
 * comutatorul e despre bani, nu despre conversatie.
 *
 * Filtrarea o face politica de select de pe group_messages, nu componenta —
 * aici se schimba doar steagul.
 */
export function VizibilitateTranzactii({
  idGrup,
  vizibile,
}: {
  idGrup: number;
  vizibile: boolean;
}) {
  const router = useRouter();
  // Optimist: comutatorul se misca imediat, iar un refuz din baza il aduce
  // inapoi odata cu mesajul. Altfel ar parea inert cat tine dus-intorsul.
  const [pornit, setPornit] = useState(vizibile);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seSalveaza, startTransition] = useTransition();

  function comuta() {
    const nou = !pornit;

    setEroare(null);
    setPornit(nou);

    startTransition(async () => {
      const rezultat = await seteazaVizibilitateaTranzactiilor(idGrup, nou);

      if (rezultat.eroare) {
        setPornit(!nou);
        setEroare(rezultat.eroare);
        return;
      }

      router.refresh();
    });
  }

  const Icoana = pornit ? Eye : EyeOff;

  return (
    <div className="mt-4 flex flex-col gap-2">
      <div className="flex items-center gap-3 rounded-card bg-surface px-4 py-3 shadow-sm">
        <Icoana size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />

        <div className="min-w-0 flex-1">
          <p className="text-[15px] text-ink">Tranzacțiile se văd între membri</p>
          <p className="mt-0.5 text-[12.5px] leading-[18px] text-ink-faint">
            {pornit
              ? "Toată lumea vede cine a pus și cine a scos bani din grup."
              : "Fiecare își vede doar propriile mișcări. Tu le vezi pe toate."}
          </p>
        </div>

        <Comutator
          activ={pornit}
          onChange={comuta}
          dezactivat={seSalveaza}
          eticheta="Arată tranzacțiile grupului tuturor membrilor"
        />
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}
    </div>
  );
}
