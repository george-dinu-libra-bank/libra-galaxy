"use client";

import { UserPlus } from "lucide-react";
import { useState } from "react";
import { AvatarProfil } from "@/components/ui/avatar-profil";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { inviteazaInGrup } from "@/lib/actions/grupuri";
import type { Contraparte } from "@/lib/data/tranzactii";

/**
 * Persoanele cu care ai mai facut tranzactii (au, prin urmare, garantat un
 * cont Galaxy Bank — vezi lib/data/tranzactii.ts::obtineContrapartiRecente),
 * cu buton de invitat in grup. Folosita atat imediat dupa crearea unui grup
 * (CreeazaGrupDrawer), cat si oricand mai tarziu, din pagina grupului
 * (InviteazaDinContrapartiDrawer).
 */
export function InviteazaDinContraparti({
  idGrup,
  contraparti,
}: {
  idGrup: number;
  contraparti: Contraparte[];
}) {
  const [invitati, setInvitati] = useState<Set<string>>(new Set());
  const [seInvita, setSeInvita] = useState<string | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);

  async function inviteaza(contraparte: Contraparte) {
    setEroare(null);
    setSeInvita(contraparte.id);

    const rezultat = await inviteazaInGrup(idGrup, contraparte.id);

    setSeInvita(null);

    if (rezultat.eroare) {
      setEroare(rezultat.eroare);
      return;
    }

    setInvitati((precedent) => new Set(precedent).add(contraparte.id));
  }

  if (contraparti.length === 0) {
    return (
      <p className="text-[13px] leading-[19px] text-ink-faint">
        Nu ai făcut încă nicio tranzacție cu cineva care are cont Galaxy Bank.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      <div className="flex flex-col gap-1">
        {contraparti.map((contraparte) => {
          const invitat = invitati.has(contraparte.id);

          return (
            <div key={contraparte.id} className="flex items-center gap-2.5 rounded-field px-2 py-1.5">
              <span className="h-8 w-8 shrink-0">
                <AvatarProfil url={contraparte.avatarUrl} nume={contraparte.nume} marimeIcoana={16} />
              </span>
              <p className="min-w-0 flex-1 truncate text-[13.5px] text-ink">{contraparte.nume}</p>
              <Button
                varianta="secondary"
                marime="sm"
                disabled={invitat}
                loading={seInvita === contraparte.id}
                iconaStanga={
                  !invitat && seInvita !== contraparte.id ? (
                    <UserPlus size={14} strokeWidth={1.75} aria-hidden />
                  ) : undefined
                }
                onClick={() => inviteaza(contraparte)}
              >
                {invitat ? "Invitat ✓" : "Invită"}
              </Button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
