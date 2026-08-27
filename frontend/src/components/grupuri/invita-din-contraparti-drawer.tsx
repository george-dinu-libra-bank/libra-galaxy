"use client";

import { UserPlus } from "lucide-react";
import { InviteazaDinContraparti } from "@/components/grupuri/invita-din-contraparti";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import type { Contraparte } from "@/lib/data/tranzactii";

/**
 * Invitatul din contraparti, disponibil oricand din pagina grupului — nu doar
 * imediat dupa creare. Doar creatorul o vede (decis de parinte, GrupPage).
 */
export function InviteazaDinContrapartiDrawer({
  idGrup,
  contraparti,
}: {
  idGrup: number;
  contraparti: Contraparte[];
}) {
  return (
    <Drawer>
      <DrawerTrigger
        aria-label="Invită dintre persoanele cu care ai mai făcut tranzacții"
        className="flex h-9 items-center gap-1.5 rounded-full bg-primary-50 px-3 text-[13px] font-semibold text-primary-700 transition-colors hover:bg-primary-100 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <UserPlus size={16} strokeWidth={2} aria-hidden />
        Invită
      </DrawerTrigger>

      <DrawerContent
        title="Invită direct"
        description="Primesc o invitație pe care o acceptă sau o refuză singuri."
      >
        <InviteazaDinContraparti idGrup={idGrup} contraparti={contraparti} />
      </DrawerContent>
    </Drawer>
  );
}
