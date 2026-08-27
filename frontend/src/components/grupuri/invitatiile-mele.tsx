"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { raspundeLaInvitatie } from "@/lib/actions/grupuri";
import type { InvitatieGrup } from "@/lib/data/grupuri";

/**
 * Invitatiile primite intr-un grup, in asteptare. Doar afisare cand exista
 * ceva de decis — la fel ca CereriStergere/CereriInchidere din panoul de
 * admin: lista + o actiune determinista per rand, `router.refresh()` la
 * succes.
 */
export function InvitatiileMele({ invitatii }: { invitatii: InvitatieGrup[] }) {
  if (invitatii.length === 0) return null;

  return (
    <section className="mb-5">
      <h2 className="text-[13px] font-semibold text-ink-soft">Invitații primite</h2>

      <div className="mt-2 flex flex-col gap-2">
        {invitatii.map((invitatie) => (
          <Invitatie key={invitatie.id} invitatie={invitatie} />
        ))}
      </div>
    </section>
  );
}

function Invitatie({ invitatie }: { invitatie: InvitatieGrup }) {
  const router = useRouter();
  const [eroare, setEroare] = useState<string | null>(null);
  const [seLucreaza, startTransition] = useTransition();

  function raspunde(accepta: boolean) {
    setEroare(null);

    startTransition(async () => {
      const rezultat = await raspundeLaInvitatie(invitatie.id, accepta);

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      router.refresh();
    });
  }

  return (
    <article className="rounded-card border border-line bg-surface p-3.5">
      <p className="text-[14px] text-ink">
        <span className="font-semibold">{invitatie.numeInvitator}</span> te-a invitat în grupul{" "}
        <span className="font-semibold">{invitatie.numeGrup}</span>
      </p>

      {eroare ? (
        <div className="mt-2">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      <div className="mt-3 flex gap-2">
        <Button marime="sm" loading={seLucreaza} onClick={() => raspunde(true)}>
          Acceptă
        </Button>
        <Button
          varianta="secondary"
          marime="sm"
          loading={seLucreaza}
          onClick={() => raspunde(false)}
        >
          Refuză
        </Button>
      </div>
    </article>
  );
}
