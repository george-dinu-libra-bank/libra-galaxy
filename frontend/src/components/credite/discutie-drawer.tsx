"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { MessagesSquare } from "lucide-react";
import { Bulina } from "@/components/ui/bulina";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { ConversatieCerere } from "@/components/credite/conversatie-cerere";
import { marcheazaFirulCitit, trimiteMesajCerere } from "@/lib/actions/credite";
import type { MesajCerere } from "@/lib/data/credite";

/**
 * Firul, ca popup — nu inline in cardul cererii.
 *
 * Inline umfla cardul si impingea butonul de incarcare sub linia de plutire, pe
 * un ecran unde restul e scurt. Ca drawer, cardul ramane o privire de ansamblu,
 * iar discutia se deschide cand chiar te uiti la ea.
 *
 * Deschiderea marcheaza firul citit: bulina se stinge cand omul a citit, nu
 * cand a intrat pe ecran.
 */
export function DiscutieDrawer({
  idCerere,
  mesaje,
  necitite,
  deschisInitial = false,
}: {
  idCerere: string;
  mesaje: MesajCerere[];
  necitite: number;
  /** Deschis din start — folosit cand se vine dintr-o notificare. */
  deschisInitial?: boolean;
}) {
  const router = useRouter();
  const [deschis, setDeschis] = useState(deschisInitial);

  useEffect(() => {
    if (!deschis || necitite === 0) return;

    // Marcarea nu blocheaza afisarea: firul e deja pe ecran, iar un esec aici
    // inseamna doar ca bulina reapare la urmatoarea incarcare.
    void marcheazaFirulCitit(idCerere).then(() => router.refresh());
  }, [deschis, necitite, idCerere, router]);

  return (
    <>
      <button
        type="button"
        onClick={() => setDeschis(true)}
        className="flex w-full items-center justify-center gap-2 rounded-field border border-line bg-surface px-4 py-3 text-[14px] font-semibold text-ink-soft transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <MessagesSquare size={17} strokeWidth={1.75} aria-hidden />
        Discuție cu banca
        <Bulina numar={necitite} />
      </button>

      <Drawer open={deschis} onOpenChange={setDeschis}>
        <DrawerContent
          title="Discuție cu banca"
          description="Întreabă orice despre dosarul tău. Documentele încărcate apar tot aici."
          cuInchidere
        >
          <ConversatieCerere
            mesaje={mesaje}
            parteaMea="client"
            trimite={(text) => trimiteMesajCerere(idCerere, text)}
            eticheta="Fir"
          />
        </DrawerContent>
      </Drawer>
    </>
  );
}
